"""Comprehensive test suite for the LSB steganography tool.

Covers:
  - Bit-manipulation primitives (inject_pixel, extract_pixel)
  - Preamble round-trip (depth and max_name_len survive embed→extract)
  - Round-trips across every supported image mode
  - Multiple depths (1, 2, 4, 8; 16 for I;16)
  - Edge cases: empty file, binary data, null bytes, exact-capacity payload
  - Filename storage: truncation, path-separator stripping, multi-file
  - Depth clamping warnings for mismatched modes
  - Status() accuracy after extraction
  - All eight error codes

Run with:
    pytest tests/ -v
"""

import os
import sys
import subprocess
from math import ceil, prod
from pathlib import Path

import pytest
import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Make project root importable regardless of how pytest is invoked
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from lsb_tool.util.container import Container
from lsb_tool.util.errors import E
from lsb_tool.util.utils import inject_pixel, extract_pixel


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path):
    """Each test runs with cwd = its own tmp_path so saved files never collide."""
    old = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(old)


def _make_image(mode, tmp_path, size=(80, 80), fill=0):
    """Create a small test PNG in *mode* and return its absolute Path."""
    safe = mode.replace(";", "_")
    path = tmp_path / f"img_{safe}.png"

    if mode == "I;16":
        # PIL cannot create I;16 directly; use a uint16 numpy array instead.
        arr = np.full(size[::-1], fill, dtype=np.uint16)
        img = Image.fromarray(arr)
    elif mode == "P":
        img = Image.new("P", size, fill)
        img.putpalette([i // 3 for i in range(768)])   # trivial greyscale palette
    else:
        img = Image.new(mode, size, fill)

    img.save(str(path))
    return path


def _make_file(tmp_path, name, content: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(content)
    return p


def _roundtrip(img_path, file_paths, *, password="testpw", depth=1, max_name_len=0):
    """
    Embed *file_paths* into *img_path*, save the result, then extract and
    return ``list[(filename_str, bytearray)]``.

    Relies on *isolated_cwd* directing all output to tmp_path.
    """
    c = Container(str(img_path), password)
    c.set_level(depth)
    c.set_max_name_len(max_name_len)
    for fp in file_paths:
        c.add_file(str(fp))
    c.embed()
    c.save()

    stem = Path(img_path).stem
    embedded = Path.cwd() / f"{stem}_embedded.png"

    c2 = Container(str(embedded), password)
    c2.extract()
    return list(zip(c2.filenames, c2.files)), c2


# ---------------------------------------------------------------------------
# 1. Bit-manipulation unit tests
# ---------------------------------------------------------------------------

class TestInjectExtract:

    def test_set_lsb(self):
        result = inject_pixel((0b11111110, 0b11111110), [1, 1], bit_pos=0)
        assert result == (0b11111111, 0b11111111)

    def test_clear_lsb(self):
        result = inject_pixel((0b11111111, 0b11111111), [0, 0], bit_pos=0)
        assert result == (0b11111110, 0b11111110)

    def test_set_high_bit(self):
        result = inject_pixel((0, 0), [1, 1], bit_pos=3)
        assert result == (8, 8)

    def test_clear_high_bit(self):
        result = inject_pixel((0xFF, 0xFF), [0, 0], bit_pos=3)
        assert result == (0xFF ^ 8, 0xFF ^ 8)

    def test_adder_not_mutated(self):
        adder = [1, 0, 1]
        inject_pixel((100, 200, 50), adder, bit_pos=0)
        assert adder == [1, 0, 1]

    def test_grayscale_pixel_as_int(self):
        """Single-channel pixels passed as plain int are handled."""
        result = inject_pixel(0b11111110, [1], bit_pos=0)
        assert result == (0b11111111,)

    def test_extract_lsb_set(self):
        assert extract_pixel((0b10101011,), 0, 0) == 1

    def test_extract_lsb_clear(self):
        assert extract_pixel((0b10101010,), 0, 0) == 0

    def test_extract_bit3(self):
        assert extract_pixel((0b00001000,), 0, 3) == 1
        assert extract_pixel((0b11110111,), 0, 3) == 0

    @pytest.mark.parametrize("bit_pos", range(8))
    @pytest.mark.parametrize("bit_val", [0, 1])
    def test_roundtrip_every_bit_position(self, bit_pos, bit_val):
        orig = (0b10110100, 0b01001011)
        modified = inject_pixel(orig, [bit_val, bit_val], bit_pos=bit_pos)
        assert extract_pixel(modified, 0, bit_pos) == bit_val
        assert extract_pixel(modified, 1, bit_pos) == bit_val


# ---------------------------------------------------------------------------
# 2. Round-trip tests across image modes
# ---------------------------------------------------------------------------

PAYLOAD = b"Round-trip payload \x00\xff\x7f"   # mix of text and binary

class TestRoundtripModes:

    @pytest.mark.parametrize("mode", ["RGB", "RGBA", "L", "LA", "P", "I;16"])
    def test_standard_modes(self, mode, tmp_path):
        img = _make_image(mode, tmp_path)
        f   = _make_file(tmp_path, "data.bin", PAYLOAD)
        results, _ = _roundtrip(img, [f])
        assert results[0][1] == bytearray(PAYLOAD)

    def test_mode_1_all_black(self, tmp_path):
        """Baseline: all-black source pixels — bug never triggered."""
        img = _make_image("1", tmp_path, fill=0)
        f   = _make_file(tmp_path, "d.bin", PAYLOAD)
        results, _ = _roundtrip(img, [f])
        assert results[0][1] == bytearray(PAYLOAD)

    def test_mode_1_all_white(self, tmp_path):
        """
        All-white source pixels: without the 254→255 normalisation fix,
        every 0-bit embedded into a white pixel reads back as 1.
        """
        img = _make_image("1", tmp_path, fill=1)   # PIL fill=1 → all white
        f   = _make_file(tmp_path, "d.bin", PAYLOAD)
        results, _ = _roundtrip(img, [f])
        assert results[0][1] == bytearray(PAYLOAD)

    def test_multiple_files(self, tmp_path):
        img = _make_image("RGB", tmp_path)
        files = [
            _make_file(tmp_path, "a.txt", b"File A"),
            _make_file(tmp_path, "b.bin", bytes(range(128))),
            _make_file(tmp_path, "c.txt", b"File C"),
        ]
        results, _ = _roundtrip(img, files)
        assert len(results) == 3
        assert results[0][1] == bytearray(b"File A")
        assert results[1][1] == bytearray(bytes(range(128)))
        assert results[2][1] == bytearray(b"File C")

    def test_empty_file(self, tmp_path):
        img = _make_image("RGB", tmp_path)
        f   = _make_file(tmp_path, "empty.bin", b"")
        results, _ = _roundtrip(img, [f])
        assert results[0][1] == bytearray(b"")

    def test_binary_with_null_bytes(self, tmp_path):
        """Null bytes inside file data must not truncate the payload."""
        data = b"\x00\x01\x00\xff\x00\x00"
        img  = _make_image("RGB", tmp_path)
        f    = _make_file(tmp_path, "nulls.bin", data)
        results, _ = _roundtrip(img, [f])
        assert results[0][1] == bytearray(data)

    def test_full_byte_range(self, tmp_path):
        """Every possible byte value (0–255) survives the round-trip."""
        data = bytes(range(256))
        img  = _make_image("RGB", tmp_path)
        f    = _make_file(tmp_path, "allbytes.bin", data)
        results, _ = _roundtrip(img, [f])
        assert results[0][1] == bytearray(data)


# ---------------------------------------------------------------------------
# 3. Depth round-trips
# ---------------------------------------------------------------------------

class TestDepthRoundtrip:

    @pytest.mark.parametrize("depth", [1, 2, 4, 8])
    def test_depths_rgb(self, depth, tmp_path):
        img  = _make_image("RGB", tmp_path)
        data = b"Depth test " * 5
        f    = _make_file(tmp_path, "d.bin", data)
        results, c2 = _roundtrip(img, [f], depth=depth)
        assert results[0][1] == bytearray(data)
        # Preamble must be recovered correctly
        assert c2.depth == depth

    def test_depth_16_i16(self, tmp_path):
        img  = _make_image("I;16", tmp_path)
        data = b"16-bit depth test data"
        f    = _make_file(tmp_path, "d.bin", data)
        results, c2 = _roundtrip(img, [f], depth=16)
        assert results[0][1] == bytearray(data)
        assert c2.depth == 16

    def test_depth_clamped_mode1_warns(self, tmp_path, capsys):
        img = _make_image("1", tmp_path)
        c   = Container(str(img), "pw")
        c.set_level(4)
        out = capsys.readouterr()
        assert c.depth == 1
        assert "Warning" in out.out

    def test_depth_clamped_rgb_warns(self, tmp_path, capsys):
        img = _make_image("RGB", tmp_path)
        c   = Container(str(img), "pw")
        c.set_level(9)
        out = capsys.readouterr()
        assert c.depth == 8
        assert "Warning" in out.out

    def test_depth_16_accepted_i16(self, tmp_path):
        img = _make_image("I;16", tmp_path)
        c   = Container(str(img), "pw")
        c.set_level(16)
        assert c.depth == 16

    def test_depth_below_1_clamped_to_1(self, tmp_path):
        img = _make_image("RGB", tmp_path)
        c   = Container(str(img), "pw")
        c.set_level(0)
        assert c.depth == 1


# ---------------------------------------------------------------------------
# 4. Filename storage
# ---------------------------------------------------------------------------

class TestFilenames:

    def test_no_filename_stored(self, tmp_path):
        img = _make_image("RGB", tmp_path)
        f   = _make_file(tmp_path, "secret.dat", b"data")
        results, _ = _roundtrip(img, [f], max_name_len=0)
        assert results[0][0] == "extracted_file_0"

    def test_filename_recovered(self, tmp_path):
        img = _make_image("RGB", tmp_path)
        f   = _make_file(tmp_path, "myfile.dat", b"data")
        results, _ = _roundtrip(img, [f], max_name_len=32)
        assert results[0][0] == "myfile.dat"

    def test_filename_truncated_to_max_name_len(self, tmp_path):
        """A filename longer than max_name_len is stored truncated (best-effort)."""
        img = _make_image("RGB", tmp_path)
        f   = _make_file(tmp_path, "verylongname.txt", b"data")
        results, _ = _roundtrip(img, [f], max_name_len=8)
        # "verylongname.txt"[:8] = b"verylong" → decoded "verylong" (no null)
        assert results[0][0] == "verylong"

    def test_path_separators_stripped(self, tmp_path):
        """A stored name containing '/' must not escape the output directory."""
        img = _make_image("RGB", tmp_path)
        c   = Container(str(img), "pw")
        c.set_max_name_len(64)
        c.files.append(b"payload")
        c.filenames.append("../../evil.sh")   # attacker-controlled name
        c.embed()
        c.save()

        embedded = tmp_path / "img_RGB_embedded.png"
        c2 = Container(str(embedded), "pw")
        c2.extract()
        assert c2.filenames[0] == "evil.sh"
        assert "/" not in c2.filenames[0]

    def test_max_name_len_255(self, tmp_path):
        """max_name_len=255 (the maximum) stores and recovers a long name."""
        img  = _make_image("RGB", tmp_path)
        name = "a" * 100 + ".bin"
        f    = _make_file(tmp_path, name, b"data")
        results, _ = _roundtrip(img, [f], max_name_len=255)
        assert results[0][0] == name

    def test_multiple_files_all_named(self, tmp_path):
        img = _make_image("RGB", tmp_path)
        f1  = _make_file(tmp_path, "alpha.txt", b"A")
        f2  = _make_file(tmp_path, "beta.bin",  b"B")
        results, _ = _roundtrip(img, [f1, f2], max_name_len=20)
        assert results[0][0] == "alpha.txt"
        assert results[1][0] == "beta.bin"

    def test_max_name_len_recovered_after_extract(self, tmp_path):
        """container.max_name_len is updated from the preamble after extraction."""
        img = _make_image("RGB", tmp_path)
        f   = _make_file(tmp_path, "f.txt", b"x")
        _, c2 = _roundtrip(img, [f], max_name_len=42)
        assert c2.max_name_len == 42


# ---------------------------------------------------------------------------
# 5. Capacity / boundary tests
# ---------------------------------------------------------------------------

class TestCapacity:

    def test_exact_capacity_fits(self, tmp_path):
        """A payload exactly filling the available space embeds without error."""
        size = (80, 80)
        img  = _make_image("RGB", tmp_path, size=size)
        channels = 3
        preamble_pixels = ceil(13 / channels)
        main_pixels     = prod(size) - preamble_pixels
        capacity_bits   = main_pixels * channels * 1
        # Overhead: 512 (hash) + 32 (num_files) + 32 (one file size) = 576 bits
        max_bytes = (capacity_bits - 576) // 8
        data = b"X" * max_bytes
        f    = _make_file(tmp_path, "max.bin", data)
        results, _ = _roundtrip(img, [f])
        assert results[0][1] == bytearray(data)

    def test_one_byte_over_capacity_exits_E05(self, tmp_path):
        size = (10, 10)
        img  = _make_image("RGB", tmp_path, size=size)
        channels = 3
        preamble_pixels = ceil(13 / channels)
        main_pixels     = prod(size) - preamble_pixels
        capacity_bits   = main_pixels * channels * 1
        max_bytes = (capacity_bits - 576) // 8
        data = b"X" * (max_bytes + 1)
        f    = _make_file(tmp_path, "over.bin", data)
        c = Container(str(img), "pw")
        c.add_file(str(f))
        with pytest.raises(SystemExit) as exc:
            c.embed()
        assert exc.value.code == E.IMAGE_TOO_SMALL

    def test_depth_doubles_capacity(self, tmp_path):
        """Embedding at depth=2 should hold ~twice as much data as depth=1."""
        size = (60, 60)
        # Create two distinct source images so their embedded outputs don't collide.
        img1 = tmp_path / "carrier_d1.png"
        img2 = tmp_path / "carrier_d2.png"
        Image.new("RGB", size, 0).save(str(img1))
        Image.new("RGB", size, 0).save(str(img2))

        channels = 3
        preamble_pixels = ceil(13 / channels)
        main_pixels     = prod(size) - preamble_pixels
        cap1 = (main_pixels * channels * 1 - 576) // 8
        cap2 = (main_pixels * channels * 2 - 576) // 8

        # cap2 should comfortably exceed cap1
        assert cap2 > cap1

        data = b"Y" * cap1   # fits at depth=1
        f    = _make_file(tmp_path, "d1.bin", data)
        results, _ = _roundtrip(img1, [f], depth=1)
        assert results[0][1] == bytearray(data)

        data2 = b"Z" * cap2  # would overflow depth=1 but fits depth=2
        f2    = _make_file(tmp_path, "d2.bin", data2)
        results2, _ = _roundtrip(img2, [f2], depth=2)
        assert results2[0][1] == bytearray(data2)


# ---------------------------------------------------------------------------
# 6. Status() accuracy
# ---------------------------------------------------------------------------

class TestStatus:

    def test_depth_updated_after_extract(self, tmp_path):
        img = _make_image("RGB", tmp_path)
        f   = _make_file(tmp_path, "f.txt", b"hello")
        _, c2 = _roundtrip(img, [f], depth=4, max_name_len=20)
        assert c2.depth == 4

    def test_files_populated_after_extract(self, tmp_path):
        img = _make_image("RGB", tmp_path)
        f   = _make_file(tmp_path, "f.txt", b"content")
        _, c2 = _roundtrip(img, [f])
        assert len(c2.files) == 1
        assert len(c2.files[0]) == len(b"content")


# ---------------------------------------------------------------------------
# 7. Error conditions
# ---------------------------------------------------------------------------

class TestErrors:

    # --- Library-level errors (catch SystemExit directly) ---

    def test_E05_payload_too_large(self, tmp_path):
        img = _make_image("RGB", tmp_path, size=(5, 5))
        f   = _make_file(tmp_path, "big.bin", b"X" * 5000)
        c   = Container(str(img), "pw")
        c.add_file(str(f))
        with pytest.raises(SystemExit) as exc:
            c.embed()
        assert exc.value.code == E.IMAGE_TOO_SMALL

    def test_E06_wrong_password(self, tmp_path):
        img = _make_image("RGB", tmp_path)
        f   = _make_file(tmp_path, "f.txt", b"secret")
        c   = Container(str(img), "correct")
        c.add_file(str(f))
        c.embed()
        c.save()

        embedded = tmp_path / "img_RGB_embedded.png"
        c2 = Container(str(embedded), "wrong")
        with pytest.raises(SystemExit) as exc:
            c2.extract()
        assert exc.value.code == E.WRONG_PASSWORD

    def test_E06_case_sensitive_password(self, tmp_path):
        img = _make_image("RGB", tmp_path)
        f   = _make_file(tmp_path, "f.txt", b"x")
        c   = Container(str(img), "Password")
        c.add_file(str(f))
        c.embed()
        c.save()

        embedded = tmp_path / "img_RGB_embedded.png"
        c2 = Container(str(embedded), "password")  # different case
        with pytest.raises(SystemExit) as exc:
            c2.extract()
        assert exc.value.code == E.WRONG_PASSWORD

    def test_E07_corrupt_image(self, tmp_path):
        bad = tmp_path / "corrupt.png"
        bad.write_bytes(b"this is not an image")
        with pytest.raises(SystemExit) as exc:
            Container(str(bad), "pw")
        assert exc.value.code == E.IMAGE_LOAD_ERROR

    def test_E07_empty_file(self, tmp_path):
        bad = tmp_path / "empty.png"
        bad.write_bytes(b"")
        with pytest.raises(SystemExit) as exc:
            Container(str(bad), "pw")
        assert exc.value.code == E.IMAGE_LOAD_ERROR

    # --- CLI-level errors (subprocess) ---

    def _run(self, *args, cwd=None):
        return subprocess.run(
            [sys.executable, "-m", "lsb_tool", *args],
            capture_output=True,
            cwd=str(cwd or Path.cwd()),
        )

    def test_E02_no_mode(self, tmp_path):
        img = _make_image("RGB", tmp_path)
        r   = self._run("-i", str(img), "-p", "pw", cwd=tmp_path)
        assert r.returncode == E.INVALID_ARGS
        assert b"[E02]" in r.stderr

    def test_E03_image_not_found(self, tmp_path):
        r = self._run("-e", "-i", "ghost.png", "-p", "pw", cwd=tmp_path)
        assert r.returncode == E.IMAGE_NOT_FOUND
        assert b"[E03]" in r.stderr

    def test_E04_embed_file_not_found(self, tmp_path):
        img = _make_image("RGB", tmp_path)
        r   = self._run("-E", "-i", str(img), "-p", "pw",
                        "-f", "no_such_file.txt", cwd=tmp_path)
        assert r.returncode == E.EMBED_FILE_NOT_FOUND
        assert b"[E04]" in r.stderr

    def test_E04_reports_all_missing(self, tmp_path):
        """All missing files are reported before exit, not just the first."""
        img = _make_image("RGB", tmp_path)
        r   = self._run("-E", "-i", str(img), "-p", "pw",
                        "-f", "ghost1.txt", "ghost2.txt", cwd=tmp_path)
        assert r.returncode == E.EMBED_FILE_NOT_FOUND
        assert b"ghost1.txt" in r.stderr
        assert b"ghost2.txt" in r.stderr

    def test_E05_via_cli(self, tmp_path):
        img = _make_image("RGB", tmp_path, size=(5, 5))
        f   = _make_file(tmp_path, "big.bin", b"X" * 5000)
        r   = self._run("-E", "-i", str(img), "-p", "pw", "-f", str(f), cwd=tmp_path)
        assert r.returncode == E.IMAGE_TOO_SMALL
        assert b"[E05]" in r.stderr

    def test_E06_via_cli(self, tmp_path):
        img = _make_image("RGB", tmp_path)
        f   = _make_file(tmp_path, "f.txt", b"data")
        # Embed with correct password
        self._run("-E", "-i", str(img), "-p", "correct",
                  "-f", str(f), cwd=tmp_path)
        embedded = tmp_path / "img_RGB_embedded.png"
        r = self._run("-e", "-i", str(embedded), "-p", "wrong", cwd=tmp_path)
        assert r.returncode == E.WRONG_PASSWORD
        assert b"[E06]" in r.stderr

    def test_E07_via_cli(self, tmp_path):
        bad = _make_file(tmp_path, "bad.png", b"not an image")
        r   = self._run("-e", "-i", str(bad), "-p", "pw", cwd=tmp_path)
        assert r.returncode == E.IMAGE_LOAD_ERROR
        assert b"[E07]" in r.stderr


# ---------------------------------------------------------------------------
# 8. Password edge cases
# ---------------------------------------------------------------------------

class TestPasswords:

    def test_special_characters(self, tmp_path):
        img = _make_image("RGB", tmp_path)
        pw  = "p@$$w0rd!€£¥"
        f   = _make_file(tmp_path, "f.bin", b"private")
        results, _ = _roundtrip(img, [f], password=pw)
        assert results[0][1] == bytearray(b"private")

    def test_very_long_password(self, tmp_path):
        img = _make_image("RGB", tmp_path)
        pw  = "a" * 512
        f   = _make_file(tmp_path, "f.bin", b"data")
        results, _ = _roundtrip(img, [f], password=pw)
        assert results[0][1] == bytearray(b"data")

    def test_empty_password(self, tmp_path):
        img = _make_image("RGB", tmp_path)
        f   = _make_file(tmp_path, "f.bin", b"data")
        results, _ = _roundtrip(img, [f], password="")
        assert results[0][1] == bytearray(b"data")


# ---------------------------------------------------------------------------
# 9. Output format
# ---------------------------------------------------------------------------

class TestOutputFormat:

    def test_output_is_always_png(self, tmp_path):
        """save() always writes a PNG regardless of the source format."""
        img = _make_image("RGB", tmp_path)
        c   = Container(str(img), "pw")
        c.add_file(str(_make_file(tmp_path, "f.txt", b"x")))
        c.embed()
        c.save()
        out = tmp_path / "img_RGB_embedded.png"
        assert out.exists()
        with Image.open(str(out)) as im:
            assert im.format == "PNG"

    def test_embedded_image_is_lossless(self, tmp_path):
        """Re-opening the saved PNG must not alter any pixel values."""
        img = _make_image("RGB", tmp_path)
        c   = Container(str(img), "pw")
        c.add_file(str(_make_file(tmp_path, "f.txt", b"hello")))
        c.embed()
        # Capture pixel grid before save
        _pxdata = lambda im: list(getattr(im, "get_flattened_data", im.getdata)())
        pixels_before = _pxdata(c.img)
        c.save()

        out = tmp_path / "img_RGB_embedded.png"
        with Image.open(str(out)) as im:
            pixels_after = _pxdata(im)

        assert pixels_before == pixels_after

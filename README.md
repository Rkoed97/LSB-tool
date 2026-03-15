# LSB Tool

Embed files inside a PNG image or extract previously hidden files using
**N-bit LSB steganography** secured by a password.

Files are scattered across pixels in a password-derived pseudo-random order so
the hidden data is not readable by standard steganalysis tools that scan
sequential pixel runs.

---

## Features

| | |
|-|-|
| **All image modes** | 1-bit, 8-bit grayscale/palette, 16-bit grayscale, RGB, RGBA |
| **N-bit embedding** | Store 1–N bits per channel (N limited by channel bit-depth) |
| **Multiple files** | Embed any number of files in a single carrier image |
| **Optional filename storage** | Preserve original filenames on extraction, or omit to save header space |
| **`python -m` support** | Run as `python -m lsb_tool` or via the `lsb-tool` entry point |
| **Error codes** | Every failure exits with a distinct code — see [ERRORS.md](ERRORS.md) |

---

## Installation

```bash
pip install lsb-tool
```

Or install from source:

```bash
git clone <repo>
cd lsb-tool
pip install -e .
```

### Requirements

- Python 3.8+
- Pillow ≥ 8.0
- NumPy ≥ 1.20

---

## Usage

The tool can be invoked in two equivalent ways:

```bash
lsb-tool [options]        # entry-point (after pip install)
python -m lsb_tool [options]
```

### Embed

```bash
lsb-tool -E -i carrier.png -p password -f file1.txt file2.bin
```

### Extract

```bash
lsb-tool -e -i carrier_embedded.png -p password
```

---

## Options

| Short | Long | Description |
|-------|------|-------------|
| `-i` | `--image` | Carrier image path (any PIL-supported format; output is always PNG) |
| `-p` | `--password` | Password used to derive the pixel-shuffle seed and verification hash |
| `-f` | `--files` | One or more files to embed (embed mode only) |
| `-l` | `--level` | Embedding depth — bits per channel (default `1`, max depends on image type) |
| `-n` | `--max-name-len` | Filename field size in bytes per file, 0–255 (default `0` = filenames not stored) |
| `-e` | `--extract` | Extract mode |
| `-E` | `--embed` | Embed mode |
| `-v` | `--verbose` | Print image, depth, capacity, and file diagnostics after the operation |

---

## Output

**Normal mode** — one line per operation:

```
Embedded 2 file(s) → photo_embedded.png
Extracted 2 file(s): report.pdf, archive.zip
```

**Verbose mode** (`-v` / `--verbose`):

```
  image    : photo.png (RGB, 1920×1080)
  depth    : 2 bits/channel → 6 bits/pixel
  capacity : 4,147,192 bytes
  used     : 12,345 bytes (0.3%)
  files    : report.pdf (9,000 B), archive.zip (3,345 B)
  hash     : 3a7f1c…e482d9
```

---

## Embedding depth (`-l` / `--level`)

Higher depth stores more bits per channel, multiplying capacity roughly
proportionally, but making changes more visible to the human eye.

| Image mode | Channel bit-depth | Max `-l` value |
|------------|-------------------|----------------|
| `1` (binary) | 1 | 1 |
| `L`, `LA`, `P`, `RGB`, `RGBA` | 8 | 8 |
| `I;16` (16-bit grayscale) | 16 | 16 |
| `I` (32-bit grayscale) | 32 | 32 |

If you request a depth greater than the image supports, the tool prints a
warning and clamps to the maximum automatically — no error is raised.

---

## Header structure

The payload is split into two regions written into the shuffled pixel stream.

### Region 1 — Preamble

Always written at **depth = 1** (LSB only), regardless of the `-l` value.
Occupies the first `⌈13 / channels⌉` pixels in the shuffled order.

| Bits | Field | Size |
|------|-------|------|
| 0 – 4 | Embedding depth (value of `-l`) | 5 bits |
| 5 – 12 | Filename field length (value of `-n`) | 8 bits |

The preamble pixel count by image mode:

| Image mode | Channels | Preamble pixels |
|------------|----------|-----------------|
| `1`, `L`, `P`, `I`, `I;16` | 1 | 13 |
| `LA` | 2 | 7 |
| `RGB` | 3 | 5 |
| `RGBA` | 4 | 4 |

### Region 2 — Main data

Written at the chosen depth (`-l`) across all remaining shuffled pixels.
Layout depends on the `-n` value:

#### Without filename storage (`-n 0`, the default)

| Offset | Field | Size |
|--------|-------|------|
| 0 | Password hash (SHA-256, 64 ASCII hex chars) | 512 bits |
| 512 | Number of embedded files | 32 bits |
| 544 | File 0 size in bytes | 32 bits |
| 576 | File 1 size in bytes | 32 bits |
| … | File N-1 size in bytes | 32 bits |
| 544 + 32×N | Raw file data (all files concatenated) | sum(sizes) × 8 bits |

**Total header overhead: `512 + 32 + 32×N` bits** (`72 + 4×N` bytes for N files).

#### With filename storage (`-n K`, K > 0)

| Offset | Field | Size |
|--------|-------|------|
| 0 | Password hash (SHA-256, 64 ASCII hex chars) | 512 bits |
| 512 | Number of embedded files | 32 bits |
| 544 | File 0 size in bytes | 32 bits |
| 576 | File 0 filename (UTF-8, zero-padded to K bytes) | K × 8 bits |
| 576 + K×8 | File 1 size in bytes | 32 bits |
| … | File 1 filename, File 2 size, … | … |
| 544 + (32 + K×8)×N | Raw file data (all files concatenated) | sum(sizes) × 8 bits |

**Total header overhead: `512 + 32 + (32 + K×8)×N` bits** (`72 + (4 + K)×N` bytes for N files, K-byte name field).

#### Overhead comparison

| Flags | Header overhead (1 file) | Header overhead (N files) |
|-------|--------------------------|---------------------------|
| `-n 0` | 76 bytes | `72 + 4×N` bytes |
| `-n 16` | 92 bytes | `72 + 20×N` bytes |
| `-n 32` | 108 bytes | `72 + 36×N` bytes |
| `-n 64` | 140 bytes | `72 + 68×N` bytes |
| `-n 255` | 327 bytes | `72 + 259×N` bytes |

---

## Examples

```bash
# Embed two files, no filename storage (minimal header)
lsb-tool -E -i photo.png -p hunter2 -f report.pdf archive.zip

# Extract (files are named extracted_file_0, extracted_file_1)
lsb-tool -e -i photo_embedded.png -p hunter2

# Embed with filename storage (32-byte name field) and depth 4
lsb-tool -E -i photo.png -p hunter2 -f secret.txt -l 4 -n 32

# Extract — file is restored as "secret.txt"
lsb-tool -e -i photo_embedded.png -p hunter2

# Check capacity and file details after embedding
lsb-tool -E -i photo.png -p hunter2 -f data.bin -v

# Embed multiple files into an RGBA image at depth 2, storing filenames
lsb-tool -E -i carrier.png -p "correct horse" -f a.txt b.bin c.log -l 2 -n 40
```

---

## Quirks and edge cases

**Filename truncation** — The filename field is exactly `-n` bytes wide. If a
filename's UTF-8 encoding is longer than `-n` bytes, it is silently truncated
to the first `-n` bytes. Truncation mid-character produces an invalid UTF-8
sequence; the tool falls back to `extracted_file_N` for that file on
extraction.  Use a `-n` value large enough to hold the longest filename you
expect (e.g. `-n 64` covers most practical names).

**Depth clamping** — Requesting `-l` greater than the image's channel
bit-depth produces a warning on stderr and continues at the clamped value.
The preamble always stores the actual depth used, so extraction is
self-consistent.

**Key derivation time** — The password hash is computed with `width × height`
SHA-256 iterations. For large images (e.g. 4K: ~8 million rounds) this can
take several seconds with no progress output.

**Image mode conversion** — If the input image is in an unsupported mode it is
converted to RGBA before embedding. The conversion is applied only to the
working copy; the original file on disk is not modified.

**Output is always PNG** — The tool saves `<name>_embedded.png` regardless of
the input format. This is deliberate: lossy formats (JPEG, WebP) alter pixel
values after saving and destroy the hidden data. Always use the PNG output as
the carrier for extraction.

**Passwords are case-sensitive** — `Hunter2` and `hunter2` produce entirely
different shuffle orders and hashes.

**Per-file size limit** — Each file's size is stored as a 32-bit unsigned
integer, capping individual files at 4 GiB. Total payload is limited by image
capacity.

---

## Image format note

Always use a lossless format (PNG, BMP, TIFF) for the carrier. Lossy formats
(JPEG, WebP) alter pixel values after saving and will destroy the hidden data.
The tool always produces PNG output regardless of the input format.

---

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Error codes

All errors exit with a specific code and print `[Exx] …` to stderr.
See [ERRORS.md](ERRORS.md) for the full reference.

| Code | Meaning |
|------|---------|
| E02 | No mode selected (`-E`/`--embed` or `-e`/`--extract` required) |
| E03 | Carrier image not found |
| E04 | A file to embed was not found |
| E05 | Files too large for this image at the chosen depth |
| E06 | Wrong password or no embedded data |
| E07 | Image file is corrupt or unsupported |
| E08 | Cannot write an output file |
| E10 | Internal error (bug) |

---

## How it works

1. **Key derivation** — The password and image dimensions are hashed (SHA-256,
   iterated `width × height` times) to produce a 64-character hex digest.
2. **Pixel shuffle** — A NumPy PCG64 RNG seeded from the digest shuffles all
   pixel coordinates into a pseudo-random order.
3. **Preamble** — The first `⌈13/channels⌉` shuffled pixels store a 13-bit
   header at depth=1: 5 bits for the embedding depth, 8 bits for the
   filename-field length.
4. **Main data** — Remaining shuffled pixels carry the payload at the chosen
   depth. Bit `k` maps to: `pixel = k ÷ (channels × depth)`,
   `channel = (k ÷ depth) mod channels`, `bit_pos = k mod depth`.
5. **Verification** — The first 512 bits of the main region store the
   password hash as ASCII hex. Extraction fails with E06 if it does not match.

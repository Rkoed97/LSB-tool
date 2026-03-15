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
| **Filename storage** | Optionally preserve original filenames on extraction |
| **Error codes** | Every failure exits with a distinct code — see [ERRORS.md](ERRORS.md) |

---

## Requirements

- Python 3.8+
- Pillow ≥ 8.0
- NumPy ≥ 1.20

```bash
pip install -r requirements.txt
```

---

## Usage

### Embed

```bash
python main.py -E -i carrier.png -p password -f file1.txt file2.bin
```

Options:

| Flag | Description |
|------|-------------|
| `-i` | Carrier image (any PIL-supported format; output is always PNG) |
| `-p` | Password used to derive the pixel-shuffle seed and verification hash |
| `-f` | One or more files to embed |
| `-l` | Bits per channel to use — **embedding depth** (default `1`, max depends on image type) |
| `-n` | Filename field length in bytes 0–255 (default `0` = filenames not stored) |
| `-v` | Print capacity and hash diagnostics after the operation |

Output: `<original_name>_embedded.png` in the current directory.

### Extract

```bash
python main.py -e -i carrier_embedded.png -p password
```

Extracted files are written to the current directory.  If `-n` was used during
embedding, the original filenames are restored; otherwise files are named
`extracted_file_0`, `extracted_file_1`, …

---

## Embedding depth (`-l`)

Higher depth stores more bits per channel, multiplying capacity roughly
proportionally, but making changes more visible to the human eye.

| Image type | Max depth | Capacity formula (bytes) |
|------------|-----------|--------------------------|
| 1-bit (`1`) | 1 | `(pixels − 5) × 1 / 8` |
| 8-bit (`L`, `LA`, `RGB`, `RGBA`, `P`) | 8 | `(pixels − preamble) × channels × depth / 8` |
| 16-bit grayscale (`I;16`) | 16 | same formula |

If you request a depth greater than the image supports, the tool warns and
clamps to the maximum automatically.

---

## Examples

```bash
# Embed two files at depth 1 (default)
python main.py -E -i photo.png -p hunter2 -f report.pdf archive.zip

# Extract (restores original files)
python main.py -e -i photo_embedded.png -p hunter2

# Embed with filename storage and depth 4
python main.py -E -i photo.png -p hunter2 -f secret.txt -l 4 -n 32

# Extract — file is written as "secret.txt" instead of "extracted_file_0"
python main.py -e -i photo_embedded.png -p hunter2

# Check capacity (verbose)
python main.py -E -i photo.png -p hunter2 -f data.bin -v
```

---

## Image format note

Always use PNG for the carrier image.  Lossy formats (JPEG, WebP) alter pixel
values after saving and will destroy the hidden data.  The tool always saves
output as PNG regardless of the input format.

---

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

---

## Error codes

All errors exit with a specific code and print `[Exx] …` to stderr.
See [ERRORS.md](ERRORS.md) for the full reference.

| Code | Meaning |
|------|---------|
| E02 | No mode selected (`-E` or `-e` required) |
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
   header at LSB-only depth: 5 bits for the embedding depth, 8 bits for the
   filename-field length.
4. **Main data** — Remaining shuffled pixels carry the payload at the chosen
   depth using the formula `bit k → pixel = k ÷ (channels × depth)`,
   `channel = (k ÷ depth) mod channels`, `bit_pos = k mod depth`.
5. **Verification** — The first 512 bits of the main region store the
   password-derived SHA-256 hash as ASCII.  Extraction fails with E06 if it
   does not match.

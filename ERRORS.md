# Error Code Reference

Every error the LSB steganography tool can emit is listed here. When something goes
wrong the tool prints a line of the form:

```
[Exx] Human-readable description of the problem.
```

Use the code (`xx`) to find the relevant entry below.

---

## Quick-reference table

| Code | Short name            | When it occurs                                                  |
|------|-----------------------|-----------------------------------------------------------------|
| E02  | Invalid arguments     | Neither `-E` nor `-e` was given, or required arguments missing  |
| E03  | Image not found       | The source image path does not exist                            |
| E04  | Embed file not found  | One or more files passed to `-f` do not exist                   |
| E05  | Image too small       | The payload exceeds the image's embedding capacity              |
| E06  | Wrong password        | Hash mismatch — wrong password or no data in the image          |
| E07  | Image load error      | The image file is corrupt, truncated, or in an unsupported format |
| E08  | Write error           | An output file could not be created or written                  |
| E10  | Internal error        | An unexpected internal state was reached (bug)                  |

---

## Detailed entries

### E02 — Invalid arguments

**Message:** `No mode selected. Use -E to embed files or -e to extract.`
(argparse also uses exit code 2 for unrecognised or missing required flags.)

**Cause:** The tool was invoked without specifying what to do, or a required
argument (such as `-i` or `-p`) was omitted.

**Fix:** Check the usage section at the top of `main.py --help`. At minimum you
need:

```
# Embed
python main.py -E -i image.png -p password -f file_to_hide.txt

# Extract
python main.py -e -i image.png -p password
```

---

### E03 — Image not found

**Message:** `Image file '<path>' not found.`

**Cause:** The path supplied with `-i` does not point to an existing file.

**Fix:** Verify the path with `ls` (or `dir` on Windows). Check for typos,
missing directories, or incorrect working directory.

---

### E04 — Embed file not found

**Message:** `File to embed not found: '<path>'`

**Cause:** One or more of the files passed to `-f` do not exist at the given
paths. All files must exist before the tool starts writing to the image.

**Fix:** Check the path(s) for typos. All files listed after `-f` must be
readable before running the tool.

---

### E05 — Image too small

**Message:**
```
The files are too large to embed in this image at depth <N>.
  Required : X bytes
  Available: Y bytes
  Try a larger image, increase the depth with -l, or embed fewer files.
```

**Cause:** The total payload (header + filenames + file data) does not fit
within the embedding capacity of the image at the chosen depth.

The capacity formula is:

```
available = (total_pixels - preamble_pixels) × channels × depth ÷ 8   bytes
```

Increasing `depth` multiplies capacity proportionally, at the cost of visible
degradation (each extra bit modifies higher-order bits in each channel).

**Fix — in order of preference:**

1. **Increase the depth** (`-l 2`, `-l 4`, …). Each step roughly doubles
   capacity. Do not exceed the image type's channel bit-depth (8 for standard
   PNG, 16 for 16-bit grayscale).
2. **Use a larger image.** Capacity scales with the number of pixels.
3. **Reduce the payload.** Compress files before embedding, or split them
   across multiple carrier images.
4. **Reduce the filename field.** A large `-n` value reserves space per file.
   Set it to 0 if stored filenames are not needed.

---

### E06 — Wrong password

**Message:**
```
Could not verify the embedded data.
The password may be incorrect, or this image contains no hidden files.
```

**Cause:** The 512-bit verification hash stored in the image does not match the
hash derived from the supplied password. This happens when:

- The password is wrong.
- The image was not created with this tool (or was created with a different
  version that used a different format).
- The image was modified after embedding (e.g. re-saved as JPEG, which is
  lossy and destroys the embedded bits).

**Fix:**

- Double-check the password. Passwords are case-sensitive.
- Make sure you are using the same image that was produced by the embed step
  (the `_embedded.png` file, not the original).
- Ensure the image was not converted to a lossy format between embed and
  extract. Always use PNG.

---

### E07 — Image load error

**Message:**
```
Could not open '<path>' as an image. The file may be corrupt,
truncated, or in an unsupported format.
```

**Cause:** The [Pillow](https://python-pillow.org/) library could not decode
the file. Common reasons:

- The file is not an image (e.g. a text file with a `.png` extension).
- The file is partially downloaded or otherwise truncated.
- The image is in a format Pillow does not support (e.g. HEIC without the
  heif plugin).

**Fix:**

- Verify the file opens correctly in an image viewer.
- Convert the image to PNG with any standard tool (`ffmpeg`, GIMP, ImageMagick)
  before using it as a carrier.
- Check that the file transfer completed without errors.

---

### E08 — Write error

**Message:** `Could not write '<filename>'. Check that you have write permission in the current directory.`

**Cause:** An extracted file (or the output `_embedded.png`) could not be
created. Common reasons:

- No write permission in the current directory.
- A directory with the same name already exists.
- The disk is full.
- The filename decoded from the image contains characters that are not
  valid on the current OS (unusual but possible with filenames embedded on
  a different operating system).

**Fix:**

- Run the tool from a directory you have write access to.
- Check available disk space.
- If the conflict is a filename collision, rename or move the conflicting
  file first.

---

### E10 — Internal error

**Message:** `An internal error occurred (<detail>). Please report this as a bug.`

**Cause:** The tool reached a code path that should be unreachable under
normal operation. This is a bug.

**Fix:** Please open an issue and include:

- The exact command you ran.
- The full error output (including the `[E10]` line and any Python traceback).
- The OS, Python version (`python --version`), and Pillow version
  (`python -c "import PIL; print(PIL.__version__)"`).

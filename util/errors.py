"""Exit codes and error-reporting for the LSB steganography tool.

All user-visible errors are routed through ``die()``, which prints a
human-readable message prefixed with the error code and exits with that
code as the process exit status.  Codes are documented in full in
ERRORS.md at the project root.
"""

import sys


class E:
    """Exit-code constants.  See ERRORS.md for the authoritative reference."""
    INVALID_ARGS         = 2   # Bad or missing CLI arguments (shared with argparse)
    IMAGE_NOT_FOUND      = 3   # Source image file does not exist on disk
    EMBED_FILE_NOT_FOUND = 4   # A file queued for embedding does not exist
    IMAGE_TOO_SMALL      = 5   # Payload does not fit at the chosen depth
    WRONG_PASSWORD       = 6   # Hash mismatch during extraction
    IMAGE_LOAD_ERROR     = 7   # PIL cannot open / decode the image
    WRITE_ERROR          = 8   # Cannot write an output file
    INTERNAL_ERROR       = 10  # Should never be reached; indicates a bug


def die(code, message):
    """Print a user-friendly error and exit with ``code``.

    Output is written to stderr so it does not pollute piped stdout.
    The ``[Exx]`` prefix lets users cross-reference ERRORS.md quickly.

    Args:
        code (int):    One of the ``E.*`` constants.
        message (str): Plain-language description of what went wrong.
    """
    print(f"[E{code:02d}] {message}", file=sys.stderr)
    sys.exit(code)

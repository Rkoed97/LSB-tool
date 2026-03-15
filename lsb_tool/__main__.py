#! /usr/bin/env python3
"""LSB Steganography Tool – CLI entry point.

Embeds files inside a PNG image or extracts previously embedded files from one,
using Least Significant Bit (LSB) steganography secured by a password.

Usage:
  Embed:   lsb_tool -E --image <image> --password <password> --files <file1> [file2 ...] [--level <level>] [-n <len>] [--verbose]
  Extract: lsb_tool -e --image <image> --password <password> [--verbose]

Arguments:
  -i/--image     Source image (any PIL-supported format; output is always PNG).
  -p/--password  Password used to derive the shuffle seed and header hash.
  -f/--files     One or more files to embed (embed mode only).
  -l/--level     LSB depth level 1–N (default 1; N depends on image type — see ERRORS.md).
  -n/--max-name-len  Filename field length in bytes 0–255 (default 0; 0 = no filenames stored).
  -e/--extract   Extract mode: read and save files hidden in the image.
  -E/--embed     Embed mode: hide files inside the image.
  -v/--verbose   Verbose: print capacity and hash diagnostics after the operation.

Output:
  Embed:   <original_name>_embedded.png written to the current directory.
  Extract: Files written to the current directory, named by stored filename or
           extracted_file_0, extracted_file_1, … if no filename was stored.

Error codes are documented in ERRORS.md.
"""

import sys
from argparse import ArgumentParser
from pathlib import Path

from lsb_tool.util.container import Container
from lsb_tool.util.errors import die, E
from lsb_tool.util.utils import status


def _build_parser():
	parser = ArgumentParser(
		description="Embed or extract files hidden inside a PNG image using LSB steganography."
	)
	parser.add_argument("-i", "--image", type=Path, help="Image to embed files in / extract from",
	                    required=True)
	parser.add_argument("-p", "--password", type=str, help="Embedding password", required=True)
	parser.add_argument("-f", "--files", type=Path, help="File(s) to embed (embed mode only)", nargs="+")
	parser.add_argument("-l", "--level", type=int,
	                    help="Embedding depth in bits per channel (default 1)", default=1)
	parser.add_argument("-n", "--max-name-len", type=int,
	                    help="Filename field length in bytes 0–255 (default 0 = no names)",
	                    default=0)
	parser.add_argument("-e", "--extract", help="Extract files hidden in the image", action="store_true")
	parser.add_argument("-E", "--embed", help="Embed files into the image", action="store_true")
	parser.add_argument("-v", "--verbose", help="Print capacity and hash diagnostics", action="store_true")
	return parser


def main():
	parser = _build_parser()
	args = parser.parse_args()

	if not args.image.exists():
		die(E.IMAGE_NOT_FOUND, f"Image file '{args.image}' not found.")

	if args.embed:  # Embedding
		missing = [f for f in args.files if not f.exists()]
		if missing:
			for f in missing:
				print(f"[E{E.EMBED_FILE_NOT_FOUND:02d}] File to embed not found: '{f}'",
				      file=sys.stderr)
			sys.exit(E.EMBED_FILE_NOT_FOUND)

		image = Container(args.image, args.password)
		image.set_level(args.level)
		image.set_max_name_len(args.max_name_len)

		for f in args.files:
			image.add_file(f)

		image.embed()
		image.save()

		out_name = "".join(str(args.image).split('/')[-1].split('.')[:-1]) + "_embedded.png"
		print(f"Embedded {len(args.files)} file(s) → {out_name}")

		if args.verbose:
			status(image)

	elif args.extract:  # Extraction
		image = Container(args.image, args.password)
		image.extract()

		names = ", ".join(image.filenames) if image.filenames else "none"
		print(f"Extracted {len(image.files)} file(s): {names}")

		if args.verbose:
			status(image)

	else:
		die(E.INVALID_ARGS, "No mode selected. Use -E/--embed to embed files or -e/--extract to extract.")


if __name__ == "__main__":
	main()

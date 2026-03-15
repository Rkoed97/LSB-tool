#! /usr/bin/env python3
"""LSB Steganography Tool – CLI entry point.

Embeds files inside a PNG image or extracts previously embedded files from one,
using Least Significant Bit (LSB) steganography secured by a password.

Usage:
  Embed:   main.py -E -i <image> -p <password> -f <file1> [file2 ...] [-l <level>] [-n <len>] [-v]
  Extract: main.py -e -i <image> -p <password> [-v]

Arguments:
  -i   Source image (any PIL-supported format; output is always PNG).
  -p   Password used to derive the shuffle seed and header hash.
  -f   One or more files to embed (embed mode only).
  -l   LSB depth level 1–N (default 1; N depends on image type — see ERRORS.md).
  -n   Filename field length in bytes 0–255 (default 0; 0 = no filenames stored).
  -e   Extract mode: read and save files hidden in the image.
  -E   Embed mode: hide files inside the image.
  -v   Verbose: print capacity and hash diagnostics after the operation.

Output:
  Embed:   <original_name>_embedded.png written to the current directory.
  Extract: Files written to the current directory, named by stored filename or
           extracted_file_0, extracted_file_1, … if no filename was stored.

Error codes are documented in ERRORS.md.
"""

import sys
from argparse import ArgumentParser
from pathlib import Path

from util.container import Container
from util.errors import die, E
from util.utils import status


def _build_parser():
	parser = ArgumentParser(
		description="Embed or extract files hidden inside a PNG image using LSB steganography."
	)
	parser.add_argument("-i", type=Path, help="Image to embed files in / extract from",
	                    required=True)
	parser.add_argument("-p", type=str, help="Embedding password", required=True)
	parser.add_argument("-f", type=Path, help="File(s) to embed (embed mode only)", nargs="+")
	parser.add_argument("-l", type=int,
	                    help="Embedding depth in bits per channel (default 1)", default=1)
	parser.add_argument("-n", "--max-name-len", type=int,
	                    help="Filename field length in bytes 0–255 (default 0 = no names)",
	                    default=0)
	parser.add_argument("-e", help="Extract files hidden in the image", action="store_true")
	parser.add_argument("-E", help="Embed files into the image", action="store_true")
	parser.add_argument("-v", help="Print capacity and hash diagnostics", action="store_true")
	return parser


def main():
	parser = _build_parser()
	args = parser.parse_args()

	if not args.i.exists():
		die(E.IMAGE_NOT_FOUND, f"Image file '{args.i}' not found.")

	if args.E:  # Embedding
		missing = [f for f in args.f if not f.exists()]
		if missing:
			for f in missing:
				print(f"[E{E.EMBED_FILE_NOT_FOUND:02d}] File to embed not found: '{f}'",
				      file=sys.stderr)
			sys.exit(E.EMBED_FILE_NOT_FOUND)

		image = Container(args.i, args.p)
		image.set_level(args.l)
		image.set_max_name_len(args.max_name_len)

		for f in args.f:
			image.add_file(f)

		print(f"Embedding {len(args.f)} file(s) into '{args.i}' at depth {image.depth}...",
		      flush=True)
		image.embed()

		out_name = "".join(str(args.i).split('/')[-1].split('.')[:-1]) + "_embedded.png"
		print(f"Saving '{out_name}'...", flush=True)
		image.save()
		print("Done.")

		if args.v:
			status(image)

	elif args.e:  # Extraction
		image = Container(args.i, args.p)

		print(f"Extracting from '{args.i}'...", flush=True)
		image.extract()

		if args.v:
			status(image)

	else:
		die(E.INVALID_ARGS, "No mode selected. Use -E to embed files or -e to extract.")


if __name__ == "__main__":
	main()

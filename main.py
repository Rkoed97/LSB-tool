#! /usr/bin/python

from util.container import Container
from argparse import ArgumentParser
from pathlib import Path
from util.utils import status

parser = ArgumentParser()

parser.add_argument("-i", type=Path, help="Image to embed files in", required=True)
parser.add_argument("-p", type=str, help="Embedding password", required=True)
parser.add_argument("-f", type=Path, help="Embedded files for the image", nargs="+")
parser.add_argument("-e", help="extracts", action="store_true")
parser.add_argument("-E", help="embeds", action="store_true")
parser.add_argument("-v", help="verbose output", action="store_true")

args = parser.parse_args()

if not args.i.exists():
	print(f"No such file {args.i}")
	exit(-1)

if args.E: #Embedding
	errors = [i if not i.exists() else 0 for i in args.f]
	if any(errors):
		for i in errors:
			if i:
				print(f"No such file {i}")
		exit(-1)

	image = Container(args.i, args.p)

	for i in args.f:
		image.add_file(i)

	print("Embedding image")
	image.embed()
	print("Embedding image done!")

	print("Saving image")
	image.save()
	print("Saving image done!")

	if args.v: status(image)

	del image
elif args.e:
	print("Creating container")
	image = Container(args.i, args.p)
	print("Creating container done!")

	print("Extracting from image")
	image.extract(args.p)
	print("Extracting from image done!")

	if args.v: status(image)
else:
	print("Wrong syntax, choose wether to extract or embed!")
	exit(-1)
#!/usr/bin/python

from util.func import encode, decode
from argparse import ArgumentParser
from pathlib import Path
from os.path import isfile

parser = ArgumentParser(prog="LSB Encoder/Decoder", description="Python LSB encoder", epilog="If the decoded message seems jibberish, there is no message to decode")

parser.add_argument("-e", help="Embeds message file in the input image file", action="store_true")
parser.add_argument("-E", help="Extracts message file from the input image file", action="store_true")
parser.add_argument("-i", type=Path, help="Sets the input image file", nargs="?")
parser.add_argument("-m", type=Path, help="Sets the file to be embedded as message", nargs="?")
parser.add_argument("-o", type=Path, help="Set the output image file (defaults to extracted.jpg)", nargs="?")

args = parser.parse_args()

if args.e:
	try:
		errors = [i if not isfile(i) else 0 for i in [args.i, args.m]]
		if any(errors):
			for i in errors:
				if i:
					print(f"No such file {i}")
			exit(-1)

		encode(args.i, args.m, args.o)
	except:
		print("Syntax error!")
		print("Example syntax: ./LSB.py -e -i in.png -m message_file -o out.png")
elif args.E:
	# try:
	if not isfile(args.i):
		print(f"No such file {i}")
		exit(-1)
	
	decode(args.i, args.o)
	# except:
	# 	print("Syntax error!")
	# 	print("Example syntax: ./LSB.py -E -i in.png -o extracted_message")
else:
	print("Syntax error!")
	print("Example syntax:	./LSB.py -E -i in.png -o extracted_message")
	print("		./LSB.py -e -i in.png -m message_file -o out.png")

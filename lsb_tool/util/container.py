from lsb_tool.util.security import get_hash, get_generator, verify_hash
from lsb_tool.util.utils import embed_files, test_fit, extract_hash, extract_files, read_preamble
from lsb_tool.util.errors import die, E
from PIL import Image, UnidentifiedImageError
from math import prod, ceil
from pathlib import Path

class Container:
	"""Wraps a PIL image and provides LSB steganography embed/extract operations.

	On construction the image is opened, its pixels are loaded into a mutable
	pixel-access object, and a password-derived shuffle of all pixel coordinates
	is computed. Every subsequent read or write uses that shuffled order so that
	data is scattered pseudo-randomly across the image rather than written
	sequentially from the top-left corner.

	Layout (in the shuffled pixel stream):

	  Preamble (first ceil(13/channels) pixels, always LSB/depth=1):
	    bits 0-4  : depth (5-bit uint, 1–32; max valid value depends on image mode)
	    bits 5-12 : max_name_len (8-bit uint)

	  Main data (remaining pixels, depth=N bits per channel):
	    [0   – 511]           : SHA-256 hash of the password (64 ASCII chars × 8 bits)
	    [512 – 543]           : number of embedded files (32-bit uint)
	    per file:
	      32 bits             : file size in bytes
	      max_name_len*8 bits : filename, UTF-8, zero-padded (omitted if max_name_len=0)
	    [remainder]           : raw file bytes, concatenated
	"""

	supported_modes = ['1', 'I', 'I;16', 'L', 'LA', 'P', 'RGB', 'RGBA']

	# Number of channels per pixel (= max LSBs at depth=1).
	bits = {	'1':1, 'I':1, 'I;16':1, 'L':1, 'P':1, #grayscale images
				'LA':2, #grayscale with alpha channel
				'RGB':3, #true color
				'RGBA':4 #true color with alpha channel
			}

	# Bit-depth of each channel value (stored here for reference / future use).
	depths = {	'1':1, #1-bit pixel values
				'L':8, 'P':8, 'LA':8, 'RGB':8, 'RGBA':8, #8-bit pixel values
				'I;16':16, #16-bit pixel values
				'I':32 #32-bit pixel values
			}

	def __init__(self, filename, password):
		"""Open an image file and prepare it for steganographic operations.

		If the image mode is not in supported_modes it is converted to RGBA,
		which is the most capable supported mode (4 bits/pixel).

		The pixel coordinate list is shuffled using an RNG seeded from the
		password hash so that the storage positions are unpredictable without
		the password.

		Args:
			filename (str | Path): Path to the source image file.
			password (str): Password used to derive the hash and shuffle seed.
		"""
		#Image elements
		self.filename = str(filename)
		try:
			self.img = Image.open(filename)
		except (UnidentifiedImageError, OSError) as exc:
			die(E.IMAGE_LOAD_ERROR,
			    f"Could not open '{filename}' as an image. "
			    f"The file may be corrupt, truncated, or in an unsupported format.")

		#Checking if the image is supported as it is, converting otherwise
		if self.img.mode not in self.supported_modes:
			self.img = self.img.convert("RGBA") #Best type for embedding

		self.size = self.img.size          # (width, height) tuple
		self.pixels = self.img.load()      # Mutable PixelAccess object

		#Security elements
		self.hash = get_hash(password, self)
		self.rng = get_generator(self.hash)
		# Build a flat list of (x, y) coordinates for every pixel, then shuffle
		# it so data is written in a password-dependent pseudo-random order.
		self.pixel_values = [(i//self.size[1], i%self.size[1]) for i in range(prod(self.size))]
		self.rng.shuffle(self.pixel_values)

		#Key elements
		self.files = []      # List of bytes objects, one per file to embed/extract
		self.filenames = []  # Original filenames, one per file
		self.depth = 1       # LSB embedding depth (1–8)
		self.max_name_len = 0  # Filename field length in bytes (0 = no filename stored)

	def add_file(self, filename):
		"""Read a file from disk and queue it for embedding.

		Args:
			filename (str | Path): Path to the file to embed.
		"""
		with open(filename, "rb") as f:
			self.files.append(f.read())
		self.filenames.append(Path(filename).name)

	def set_level(self, level):
		"""Set the LSB embedding depth level.

		The maximum allowed depth is the bit-depth of the image's channel type:
		  1-bit ('1'):               depth capped at 1
		  8-bit ('L','P','LA',etc.): depth capped at 8
		  16-bit ('I;16'):           depth capped at 16
		  32-bit ('I'):              depth capped at 32

		Deeper levels store more bits per channel, increasing capacity at the
		cost of more visible image degradation.

		Args:
			level (int): Desired bit depth (clamped to 1 – channel bit-depth).
		"""
		max_depth = self.depths.get(self.img.mode, 8)
		clamped = max(1, min(max_depth, level))
		if clamped != level:
			print(f"Warning: depth {level} is not supported by this image type "
			      f"(max {max_depth} for '{self.img.mode}' mode). Using depth={clamped}.")
		self.depth = clamped

	def set_max_name_len(self, n):
		"""Set the per-file filename field length in bytes (0–255).

		Set to 0 (the default) to omit filenames entirely; extracted files
		will be named extracted_file_0, extracted_file_1, etc.

		Args:
			n (int): Filename field size in bytes (clamped to 0–255).
		"""
		self.max_name_len = max(0, min(255, n))

	def embed(self):
		"""Write all queued files into the image using LSB steganography.

		Verifies the payload fits before writing; exits with E05 if not.
		"""
		channels = self.bits[self.img.mode]
		test_fit(self, channels, self.depth)   # exits via die() if too large
		embed_files(self, channels, self.depth)

	def extract(self):
		"""Extract previously embedded files from the image and write them to disk.

		Reads the preamble to determine the embedding depth and filename field
		length, then verifies the header hash. If the hash matches, reads all
		embedded files and writes them to the current directory using either the
		stored filename (if max_name_len > 0) or extracted_file_<index>.
		"""
		channels = self.bits[self.img.mode]
		preamble_pixels = ceil(13 / channels)

		depth, max_name_len = read_preamble(self)
		self.depth = depth
		self.max_name_len = max_name_len

		hash_string = extract_hash(self, channels, depth, preamble_pixels)

		if verify_hash(self, hash_string):
			extract_files(self, channels, depth, preamble_pixels, max_name_len)
			written = []
			for i, (file_data, filename) in enumerate(zip(self.files, self.filenames)):
				out_name = filename if filename else f"extracted_file_{i}"
				try:
					with open(out_name, "wb") as f:
						f.write(file_data)
				except OSError:
					die(E.WRITE_ERROR,
					    f"Could not write '{out_name}'. "
					    f"Check that you have write permission in the current directory.")
				written.append(out_name)
		else:
			die(E.WRONG_PASSWORD,
			    "Could not verify the embedded data. "
			    "The password may be incorrect, or this image contains no hidden files.")

	def save(self):
		"""Save the modified image as a PNG file in the current directory.

		The output filename is derived from the original filename by stripping
		the extension and appending ``_embedded.png``.
		PNG is used to guarantee lossless storage of the modified pixel values;
		a lossy format (e.g. JPEG) would destroy the hidden data.
		"""
		new_file = "".join(self.filename.split('/')[-1].split('.')[:-1])
		self.img.save(new_file+"_embedded.png", format="png")

	def reset_rng(self):
		"""Re-seed the RNG to its initial state using the stored hash.

		Useful if you need to replay the pixel shuffle from the beginning
		(e.g. for a second pass over the image).
		"""
		self.rng = get_generator(self.hash)

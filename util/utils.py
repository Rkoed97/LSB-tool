from math import prod, ceil
from pathlib import Path
from util.errors import die, E

# Header size lookup table (kept for future reference / validation use).
# Each entry is [hash_bits, file_count_bits, ???, total_bits] for a given mode.
# Not actively used in the current implementation; computed values in
# embed_files / test_fit are the authoritative source.
header_size = {
	**dict.fromkeys(['1', 'I', 'I;16', 'L', 'P'], [504, 32, 32, 568]), #For grayscale and black/white images (1 channel)
	**dict.fromkeys(['LA'], [504, 32, 33, 569]), #For grayscale with alpha channel (2 channels)
	**dict.fromkeys(['RGB', 'RGBA'], [504, 32, 34, 570]) #For true color (3 and 4 channels)
}



def inject_pixel(orig, adder, bit_pos=0):
	"""Write one message bit into each channel of a single pixel at the given bit position.

	For each channel: if the message bit is 1, bit ``bit_pos`` is set; if 0 it is
	cleared. ``bit_pos=0`` (the default) modifies the LSB, reproducing the
	original behaviour.

	When ``adder`` has fewer elements than ``orig`` (e.g. embedding 3-bit data
	into an RGBA pixel), the missing channels are copied from the original so
	those channels are left untouched.

	Args:
		orig (tuple | int): The original pixel value. A tuple for multi-channel
		                    modes (RGB, RGBA, LA), or a plain int for grayscale.
		adder (list[int]):  Message bits to write, one per channel (0 or 1).
		bit_pos (int):      Which bit of each channel to modify (0 = LSB).

	Returns:
		tuple: The modified pixel value with the target bit updated.
	"""
	adder = list(adder)  # prevent in-place mutation of caller's list
	mask = 1 << bit_pos
	inject = lambda x: (x[0] | mask) if x[1] else (x[0] & ~mask)

	try:
		final = list(orig)
	except:
		final = [orig]

	if len(final) == len(adder):
		final = list(map(inject, [(final[i], adder[i]) for i in range(len(adder))]))
		return tuple(final)
	elif len(adder) < len(orig):
		# Fewer message bits than channels: leave the extra channels unchanged
		for i in range(len(adder), len(orig)):
			adder.append(orig[i])
		final = list(map(inject, [(final[i], adder[i]) for i in range(len(adder))]))
		return tuple(final)
	else:
		# Should never happen: more message bits than pixel channels
		die(E.INTERNAL_ERROR,
		    "inject_pixel received more bits than the pixel has channels. "
		    "Please report this as a bug.")



def extract_pixel(orig, channel, bit_pos=0):
	"""Read one bit from a specific channel of a pixel.

	Args:
		orig (tuple | int): Pixel value (tuple for multi-channel, int for grayscale).
		channel (int):      Zero-based channel index to read from.
		bit_pos (int):      Which bit to read (0 = LSB).

	Returns:
		int: The requested bit (0 or 1).
	"""
	try:
		orig = list(orig)
	except:
		orig = [orig]

	return (orig[channel] >> bit_pos) & 1



# Split a flat list/string into 8-element chunks (used to reassemble bytes from bits).
splitup = lambda arr: [arr[i:i+8] for i in range(0, len(arr), 8)]



def _bits_to_str(bits):
	return "".join([str(b) for b in bits])


def _write_preamble_bit(container, k, bit, channels):
	"""Write a single bit to position k in the preamble region (always LSB, depth=1)."""
	pixel_idx = k // channels
	ch = k % channels
	x, y = container.pixel_values[pixel_idx]
	try:
		p = list(container.pixels[x, y])
	except:
		p = [container.pixels[x, y]]
	if bit:
		p[ch] |= 1
	else:
		p[ch] &= ~1
	# Mode "1": PIL normalises any non-zero value to 255 on storage.
	# 255 & ~1 = 254 (non-zero) would be stored as 255, flipping a 0-bit back to 1.
	# Explicitly write 0 or 255 so the LSB reads back correctly.
	if container.img.mode == '1':
		p[ch] = 255 if (p[ch] & 1) else 0
	container.pixels[x, y] = tuple(p)


def _read_preamble_bit(container, k, channels):
	"""Read a single bit from position k in the preamble region (always LSB, depth=1)."""
	pixel_idx = k // channels
	ch = k % channels
	x, y = container.pixel_values[pixel_idx]
	return extract_pixel(container.pixels[x, y], ch, 0)


def _write_main_bit(container, k, bit, channels, depth, preamble_pixels):
	"""Write a single bit to position k in the main data region."""
	pixel_idx = k // (channels * depth)
	ch = (k // depth) % channels
	bp = k % depth
	x, y = container.pixel_values[preamble_pixels + pixel_idx]
	mask = 1 << bp
	try:
		p = list(container.pixels[x, y])
	except:
		p = [container.pixels[x, y]]
	if bit:
		p[ch] |= mask
	else:
		p[ch] &= ~mask
	# Mode "1": same normalisation as _write_preamble_bit — avoid 254→255 rounding.
	if container.img.mode == '1':
		p[ch] = 255 if (p[ch] & mask) else 0
	container.pixels[x, y] = tuple(p)


def _read_main_bit(container, k, channels, depth, preamble_pixels):
	"""Read a single bit from position k in the main data region."""
	pixel_idx = k // (channels * depth)
	ch = (k // depth) % channels
	bp = k % depth
	x, y = container.pixel_values[preamble_pixels + pixel_idx]
	return extract_pixel(container.pixels[x, y], ch, bp)


def read_preamble(container):
	"""Read the 12-bit preamble and return (depth, max_name_len).

	The preamble is always stored at LSB (bit_pos=0), using the first
	ceil(13 / channels) pixels in the shuffled order.

	  bits 0-4  : depth        (5-bit uint, values 1-32)
	  bits 5-12 : max_name_len (8-bit uint, values 0-255)

	Args:
		container: A Container instance.

	Returns:
		tuple[int, int]: (depth, max_name_len)
	"""
	channels = container.bits[container.img.mode]
	bits = [_read_preamble_bit(container, k, channels) for k in range(13)]
	depth = int(_bits_to_str(bits[0:5]), 2)
	max_name_len = int(_bits_to_str(bits[5:13]), 2)
	# Clamp depth to a valid range so a bad password doesn't cause division by zero
	depth = max(1, min(32, depth))
	return depth, max_name_len



def embed_files(container, channels, depth):
	"""Encode the preamble, header, filenames, and file data into the container's pixels.

	Layout:
	  Preamble (first ceil(13/channels) pixels, depth=1):
	    5 bits: depth
	    8 bits: max_name_len

	  Main data region (remaining pixels, depth=N):
	    512 bits : hash (64 ASCII chars)
	     32 bits : num_files
	    per file:
	      32 bits              : file size in bytes
	      max_name_len*8 bits  : filename bytes, UTF-8, zero-padded (omitted if max_name_len=0)
	    file data (concatenated)

	Args:
		container: A Container instance with .hash, .files, .filenames,
		           .max_name_len, and .pixel_values attributes.
		channels (int): Number of channels in the image (bits per pixel at depth=1).
		depth (int):    Number of LSBs per channel to use (1–8).
	"""
	preamble_pixels = ceil(13 / channels)

	# Write 13-bit preamble (always depth=1, bit_pos=0)
	preamble_bits = f"{depth:05b}{container.max_name_len:08b}"
	for k in range(13):
		_write_preamble_bit(container, k, int(preamble_bits[k]), channels)

	# Build main message: hash + num_files + per-file (size [+ name]) + file data
	header = "".join([f"{ord(c):08b}" for c in container.hash])  # 512 bits
	header += f"{len(container.files):032b}"

	for i, file_data in enumerate(container.files):
		header += f"{len(file_data):032b}"
		if container.max_name_len > 0:
			name = container.filenames[i] if i < len(container.filenames) else ""
			name_bytes = name.encode('utf-8')[:container.max_name_len]
			name_bytes = name_bytes + b'\x00' * (container.max_name_len - len(name_bytes))
			header += "".join([f"{b:08b}" for b in name_bytes])

	files_bits = "".join(
		["".join([f"{b:08b}" for b in file_data]) for file_data in container.files]
	)
	message = header + files_bits

	for k in range(len(message)):
		_write_main_bit(container, k, int(message[k]), channels, depth, preamble_pixels)



def test_fit(container, channels, depth):
	"""Check whether the queued files will fit inside the image.

	Args:
		container: A Container instance.
		channels (int): Number of channels in the image.
		depth (int):    Number of LSBs per channel to use.

	Returns:
		bool: True if the message fits, False otherwise.
	"""
	preamble_pixels = ceil(13 / channels)
	total_pixels = prod(container.size)
	main_pixels = total_pixels - preamble_pixels
	main_capacity = main_pixels * channels * depth

	name_bits_per_file = container.max_name_len * 8
	files_data_bits = sum([len(f) for f in container.files]) * 8
	message_size = 512 + 32 + (32 + name_bits_per_file) * len(container.files) + files_data_bits

	if message_size > main_capacity:
		needed_bytes   = (message_size + 7) // 8
		available_bytes = main_capacity // 8
		die(E.IMAGE_TOO_SMALL,
		    f"The files are too large to embed in this image at depth {depth}.\n"
		    f"  Required : {needed_bytes:,} bytes\n"
		    f"  Available: {available_bytes:,} bytes\n"
		    f"  Try a larger image, increase the depth with -l, or embed fewer files.")
	return True



def status(container):
	"""Print a diagnostic summary of the container's capacity and contents.

	Args:
		container: A Container instance (used after embed or extract).
	"""
	channels = container.bits[container.img.mode]
	depth = container.depth
	preamble_pixels = ceil(13 / channels)
	total_pixels = prod(container.size)
	main_pixels = total_pixels - preamble_pixels
	capacity = main_pixels * channels * depth

	name_bits_per_file = container.max_name_len * 8
	files_data_bits = sum([len(f) * 8 for f in container.files])
	message_size = 512 + 32 + (32 + name_bits_per_file) * len(container.files) + files_data_bits

	print(f"""
{container.filename}

Embedded files sizes: {[len(i) for i in container.files]}

->{container.hash}
->{container.rng}
->{container.img.mode} mode
->{container.size} pixels
->{channels * depth} estimated bits/pixel (depth={depth})
->{capacity} estimated bits to fit
->{message_size} estimated message size
""")



def extract_hash(container, channels, depth, preamble_pixels):
	"""Read the 512-bit hash from the beginning of the embedded main data region.

	Args:
		container: A Container instance whose pixel_values have been shuffled.
		channels (int): Number of channels in the image.
		depth (int):    Embedding depth read from the preamble.
		preamble_pixels (int): Number of pixels reserved for the preamble.

	Returns:
		str: The 64-character hex hash string extracted from the image header.
	"""
	raw_bits = [_read_main_bit(container, k, channels, depth, preamble_pixels)
	            for k in range(512)]
	raw_str = _bits_to_str(raw_bits)
	return "".join([chr(int(raw_str[j:j+8], 2)) for j in range(0, len(raw_str), 8)])



def extract_files(container, channels, depth, preamble_pixels, max_name_len):
	"""Read the file count, sizes, filenames, and raw file data from the embedded header.

	Populates container.files and container.filenames.

	Args:
		container: A Container instance after a successful extract_hash call.
		channels (int): Number of channels in the image.
		depth (int):    Embedding depth read from the preamble.
		preamble_pixels (int): Number of pixels reserved for the preamble.
		max_name_len (int): Filename field length in bytes (0 = no filename stored).
	"""
	container.files = []
	container.filenames = []

	# Read num_files (bits 512-543)
	bits = [_read_main_bit(container, k, channels, depth, preamble_pixels)
	        for k in range(512, 544)]
	no_files = int(_bits_to_str(bits), 2)

	offset = 544
	file_sizes = []
	file_names = []

	for i in range(no_files):
		# Read file size (32 bits)
		size_bits = [_read_main_bit(container, k, channels, depth, preamble_pixels)
		             for k in range(offset, offset + 32)]
		file_size = int(_bits_to_str(size_bits), 2)
		file_sizes.append(file_size)
		offset += 32

		# Read filename field if present
		if max_name_len > 0:
			name_bits = [_read_main_bit(container, k, channels, depth, preamble_pixels)
			             for k in range(offset, offset + max_name_len * 8)]
			name_bytes = bytes([int(_bits_to_str(name_bits[j:j+8]), 2)
			                    for j in range(0, len(name_bits), 8)])
			null = name_bytes.find(b'\x00')
			name_bytes = name_bytes[:null] if null != -1 else name_bytes
			try:
				filename = Path(name_bytes.decode('utf-8')).name
				if not filename:
					filename = f"extracted_file_{i}"
			except (UnicodeDecodeError, ValueError):
				filename = f"extracted_file_{i}"
			file_names.append(filename)
			offset += max_name_len * 8
		else:
			file_names.append(f"extracted_file_{i}")

	# Read file data
	for i in range(no_files):
		file_bits = [_read_main_bit(container, k, channels, depth, preamble_pixels)
		             for k in range(offset, offset + file_sizes[i] * 8)]
		file_bytes = bytes([int(_bits_to_str(file_bits[j:j+8]), 2)
		                    for j in range(0, len(file_bits), 8)])
		container.files.append(bytearray(file_bytes))
		container.filenames.append(file_names[i])
		offset += file_sizes[i] * 8

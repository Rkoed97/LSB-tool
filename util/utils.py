from math import prod

header_size = {
	**dict.fromkeys(['1', 'I', 'I;16', 'L', 'P'], [504, 32, 32, 568]), #For grayscale and black/white images (1 channel)
	**dict.fromkeys(['LA'], [504, 32, 33, 569]), #For grayscale with alpha channel (2 channels)
	**dict.fromkeys(['RGB', 'RGBA'], [504, 32, 34, 570]) #For true color (3 and 4 channels)
}



def inject_pixel(orig, adder):

	inject = lambda x: x[0] | x[1] if x[1] else x[0] & (~1)

	try:
		final = list(orig)
	except:
		final = [orig]

	if len(final) == len(adder):
		final = list(map(inject, [(final[i], adder[i]) for i in range(len(adder))]))
		return tuple(final)
	elif len(adder) < len(orig):
		#Cloning into adder missing components
		for i in range(len(adder), len(orig)):
			adder.append(orig[i])
		final = list(map(inject, [(final[i], adder[i]) for i in range(len(adder))]))
		return tuple(final)
	else:
		print("Magic has finally happened! Check the injection!")
		exit(-1)



def extract_pixel(orig, channel):
	try:
		orig = list(orig)
	except:
		orig = [orig]

	return orig[channel] & 1



splitup = lambda arr: [arr[i:i+8] for i in range(0, len(arr), 8)]



def embed_files(container, bit):

	#*Building the header

	#Converting the hash to a bit array
	header = "".join([f"{i:08b}" for i in [ord(j) for j in container.hash]])

	#Adding the no of files
	cheader = header
	header += f"{len(container.files):032b}"

	#Adding the file sizes (in bytes)
	cheader = header

	for i in container.files:
		header += f"{len(i):032b}"

	#Adding the files
	cheader = header

	files = [list(i) for i in container.files]
	message = list(header + "".join(["".join([f"{i:08b}" for i in k]) for k in files]))
	del header

	#injecting the image

	for k in range(0, len(message), bit):
		ck = k//bit

		x, y = container.pixel_values[ck]

		container.pixels[x,y] = inject_pixel(container.pixels[x,y], [int(i) for i in message[k:k+bit]])

def test_fit(container, bit):
	image_size = prod(container.size) * bit #No. of pixelx * bits/pixel
	
	files_size = sum([len(i) for i in container.files])
	message_size = 544 + 32*len(container.files) + files_size

	return message_size <= image_size



def status(container):

	files_size = sum([len(i)*8 for i in container.files])
	message_size = 544 + 32*len(container.files) + files_size

	print(f"""
{container.filename}

Embedded files sizes: {[len(i) for i in container.files]}

->{container.hash}
->{container.rng}
->{container.img.mode} mode
->{container.size} pixels
->{container.bits[container.img.mode]} estimated bits/pixel
->{prod(container.size) * container.bits[container.img.mode]} estimated bits to fit
->{message_size} estimated message size
""")



def extract_hash(container):

	pixels = [(i//container.img.size[1], i%container.img.size[1]) for i in range(prod(container.img.size))]

	#Recreating the pixel order
	container.rng.shuffle(pixels)

	raw_header = []

	#Based on the algorithm, the hash is 512 bits wide
	for k in range(0, 512):
		ck = k // container.bits[container.img.mode]
		x, y = container.pixel_values[ck]

		raw_header += [extract_pixel(container.pixels[x, y], k%container.bits[container.img.mode])]

	raw_header = "".join([str(i) for i in raw_header])

	#Processing the header from bitarray to string
	return "".join([chr(int(i, 2)) for i in [raw_header[j:j+8] for j in range(0, len(raw_header), 8)]])



def extract_files(container):

	#Resetting the files inside of the container
	container.files = []

	pixels = [(i//container.img.size[1], i%container.img.size[1]) for i in range(prod(container.img.size))]

	#Recreating the pixel order
	container.rng.shuffle(pixels)

	image_content = []

	#Based on the algorithm, the no of files is 32-bit, after hash
	for k in range(512, 544):
		ck = k // container.bits[container.img.mode]
		x, y = container.pixel_values[ck]

		image_content += [extract_pixel(container.pixels[x, y], k%container.bits[container.img.mode])]

	no_files = int("".join([str(i) for i in image_content]), 2)

	file_sizes = []

	for i in range(no_files):
		file = []

		#Based on the algorithm, the no of files is 32-bit, after hash
		for k in range(544+32*i, 544+32*(i+1)):
			ck = k // container.bits[container.img.mode]
			x, y = container.pixel_values[ck]

			file += [extract_pixel(container.pixels[x, y], k%container.bits[container.img.mode])]

		file_sizes.append(int("".join([str(i) for i in file]), 2)*8)

	offset = 544 + no_files*32

	file_starts = [offset + sum(file_sizes[:i]) for i in range(no_files)]

	for i in range(no_files):
		file = []

		for k in range(file_starts[i], file_starts[i] + file_sizes[i]):
			ck = k // container.bits[container.img.mode]
			x, y = container.pixel_values[ck]

			file += [extract_pixel(container.pixels[x, y], k%container.bits[container.img.mode])]

		file = splitup("".join([str(i) for i in file]))
		file = [int(i, 2) for i in file]

		container.files.append(bytearray(file))
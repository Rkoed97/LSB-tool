from util.utils import inject_pixel, extract_pixel, get_seed
from random import seed, shuffle
from PIL import Image
from math import prod

def encode(image_path, message_path, output_path):

	#*	Initializing needed variables

	#Opening initial image
	img = Image.open(image_path)
	image = img.load() #pixel matrix

	#Checking image mode to be compatible
	if image.mode not in ["RGB", "RGBA"]:
		print(f"Image is {image.mode}, advanced injection is not yet possible for it. Try with RGB/RGBA/RGBa")
	
	#Opening message
	with open(message_path, "rb") as f:
		message = list(f.read())

	print(f"{len(message)=} leads to {len(message)*8 + 33} used bits")
	print(f"That need to fit in image of size {img.size}, total {prod(img.size)} pixels, {prod(img.size)*3} bits\n\n")

	#Getting random seed
	s = get_seed(img)
	seed(s)

	if not len(message)*8 + 33 <= prod(img.size)*3: #+33 is to account for the 32-bit length specifier at the beginning of the message (rounded to the pixel values)
		print("Advanced injection is not possible with the given image-message pair")
		exit(-1)

	#Initializing final image
	out_img = Image.new(img.mode, img.size)
	out_image = out_img.load() #pixel matrix

	#*	Encoding the message to an array of bits
	#?		:#010b
	#?		# = use the alternative form (insert 0b)
	#?		0 = pad with 0
	#?		10 = chars to pad to (including 0b)
	#?		b = use binary for the number

	t_mess = [f"{j:08b}" for j in message]
	t_mess.insert(0, f"{len(message):033b}")
	message = [int(i) for i in "".join(t_mess)]

	#*	Injecting the message into the image and writing the new one

	pixels = [(i//img.size[1], i%img.size[1]) for i in range(prod(img.size))]

	shuffle(pixels)

	#Copying the original image over

	for x, y in pixels:
		out_image[x,y] = image[x,y]

	for k in range(0,len(message),3):
		#Getting pixel coordinates
		ck = k // 3

		x, y = pixels[ck]

		out_image[x,y] = inject_pixel(image[x,y], tuple(message[k:k+3]))

	#*	Saving injected image

	if not output_path:
		output_path = "embedded.png"

	out_img.save(output_path, format="png")

	with open("outputs/debug_info", "w+") as f:
		f.write(str(message[:33])+'\n')
		for i in range(33, len(message), 8):
			f.write(str(message[i:i+8])+'\n')

		f.write("\n\n\n\n\n\n\n\n\n\n\n")

		

def decode(image_path, output_path):
	img = Image.open(image_path)
	image = img.load() #pixel matrix

	s = get_seed(img)
	seed(s)

	pixels = [(i//img.size[1], i%img.size[1]) for i in range(prod(img.size))]

	shuffle(pixels)

	length = []

	for k in range(0,33,3): #reading the 32-bit length specifier
		#Getting pixel coordinates
		ck = k // 3
		x, y = pixels[ck]

		length += extract_pixel(image[x,y])

	#Decoding the length of the message
	length = int("".join([str(i) for i in length]), 2)

	message = []

	for k in range(33, length*8+33, 3):
		ck = k//3
		x, y = pixels[ck]

		message += extract_pixel(image[x,y])

	with open("outputs/debug_info_decode", "w+") as f:
		for i in range(0, len(message), 8):
			f.write(str(message[i:i+8])+'\n')

	#Decoding the message
	message = "".join([str(i) for i in message])
	message = [int(message[i:i+8], 2) for i in range(0, len(message), 8)]

	message = message[:-1]

	if not output_path:
		output_path = "extracted.file"

	with open(output_path, "wb") as f:
		f.write(bytearray(message))
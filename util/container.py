from util.security import get_hash, get_generator, verify_hash
from util.utils import embed_files, test_fit, extract_hash, extract_files
from PIL import Image
from math import prod

class Container:

	supported_modes = ['1', 'I', 'I;16', 'L', 'LA', 'P', 'RGB', 'RGBA']
	#Message bits/pixel
	bits = {	'1':1, 'I':1, 'I;16':1, 'L':1, 'P':1, #grayscale images
				'LA':2, #grayscale with alpha channel
				'RGB':3, #true color
				'RGBA':4 #true color with alpha channel
			}
	
	#Here for future reference
	depths = {	'1':1, #1-bit pixel values
				'L':8, 'P':8, 'LA':8, 'RGB':8, 'RGBA':8, #8-bit pixel values
				'I;16':16, #16-bit pixel values
				'I':32 #32-bit pixel values
			}
	
	def __init__(self, filename, password):

		#Image elements
		self.filename = str(filename)
		self.img = Image.open(filename)

		#Checking if the image is supported as it is, converting otherwise
		if self.img.mode not in self.supported_modes:
			self.img = self.img.convert("RGBA") #Best type for embedding

		self.size = self.img.size
		self.pixels = self.img.load()

		#Security elements
		self.hash = get_hash(password, self)
		self.rng = get_generator(self.hash)
		self.pixel_values = [(i//self.size[1], i%self.size[1]) for i in range(prod(self.size))]
			#Shuffling the pixels as per the rng
		self.rng.shuffle(self.pixel_values)

		#Key elements
		self.files = []

	def add_file(self, filename):
		with open(filename, "rb") as f:
			self.files.append(f.read())

	#Return the bit array if successful, 0 otherwise
	def embed(self):
		if test_fit(self, self.bits[self.img.mode]):
			return embed_files(self, self.bits[self.img.mode])
		else:
			return 0

	def extract(self, password):

		hash_string = extract_hash(self)

		if verify_hash(self, hash_string):
			print("Header hash matches! Files can be extracted!")
			extract_files(self)
			for i in self.files:
				with open(f"extracted_file_{self.files.index(i)}", "wb") as f:
					f.write(i)
			print(f"{len(self.files)} have been extracted, as :{[f'extracted_file_{i}' for i in range(len(self.files))]}")
		else:
			print("Header hash doesn't match! The password is wrong or there are no files hidden")
			exit(-1)

	def save(self):
		new_file = "".join(self.filename.split('/')[-1].split('.')[:-1])
		self.img.save(new_file+"_embedded.png", format="png")

	def reset_rng(self):
		self.rng = get_generator(self.hash)
		
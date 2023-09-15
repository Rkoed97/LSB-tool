from random import choice, seed, shuffle
from math import prod

def inject_pixel(orig, adder):
	final = list(orig)

	if adder[0]:
		final[0] = final[0] | adder[0]
	else:
		final[0] = final[0] & (~1)

	if len(adder) >= 2:
		if adder[1]:
			final[1] = final[1] | adder[1]
		else:
			final[1] = final[1] & (~1)

	if len(adder) >= 3:
		if adder[2]:
			final[2] = final[2] | adder[2]
		else:
			final[2] = final[2] & (~1)

	return tuple(final)

def extract_pixel(orig):
	return [orig[0] & 1, orig[1] & 1, orig[2] & 1]

def get_seed(image):
	n = prod(image.size)
	for i in range(100):
		seed(n)
		n = int("".join([choice("1234567890") for i in range(32)]))

	return n
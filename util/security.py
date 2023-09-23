from hashlib import sha256, md5
from numpy.random import default_rng
from math import prod

def get_hash(password, img):
	password = password+str(img.size)
	rounds = prod(img.size)
	for i in range(rounds):
		password = sha256(password.encode()).hexdigest()
	return sha256(password.encode()).hexdigest()

def get_generator(seed):
	return default_rng(seed=int(seed, 16))

def verify_hash(container, hsh):
	return container.hash == hsh

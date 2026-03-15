import hmac
from hashlib import sha256
from numpy.random import default_rng
from math import prod

def get_hash(password, img):
	"""Derive a deterministic SHA-256 hash from a password and image dimensions.

	The password is salted with the image size string, then hashed repeatedly
	prod(width * height) times to make brute-force attacks expensive. A final
	SHA-256 pass produces the output hex digest.

	Args:
		password (str): The user-supplied embedding/extraction password.
		img: A Container instance (must have a .size attribute of (width, height)).

	Returns:
		str: A 64-character lowercase hex SHA-256 digest used as both the
		     header verification token and the RNG seed.
	"""
	password = password+str(img.size)
	rounds = prod(img.size)
	for i in range(rounds):
		password = sha256(password.encode()).hexdigest()
	return sha256(password.encode()).hexdigest()

def get_generator(seed):
	"""Create a NumPy random Generator seeded from a hex hash string.

	The hex digest is converted to an integer so it can serve as a numeric seed
	for numpy's default_rng (PCG64). The same seed always produces the same
	pixel shuffle order, which is required for both embedding and extraction.

	Args:
		seed (str): A hex string (e.g. the output of get_hash).

	Returns:
		numpy.random.Generator: A seeded RNG used to shuffle pixel coordinates.
	"""
	return default_rng(seed=int(seed, 16))

def verify_hash(container, hsh):
	"""Check whether an extracted header hash matches the container's expected hash.

	Called during extraction to confirm that the correct password was supplied
	and that the image actually contains embedded data.

	Args:
		container: A Container instance with a .hash attribute.
		hsh (str): The hash string read back from the image header.

	Returns:
		bool: True if the hashes match (correct password / data present).
	"""
	try:
		return hmac.compare_digest(container.hash, hsh)
	except TypeError:
		# hsh may contain non-ASCII characters when the password is wrong and
		# the extracted bit-stream decodes to arbitrary Unicode code points.
		# Any such mismatch is definitively a failed verification.
		return False

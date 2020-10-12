import base64


def encode_file_b64(filename: str):
	with open(filename, "rb") as image_file:
		encoded_string = base64.b64encode(image_file.read())
	return encoded_string
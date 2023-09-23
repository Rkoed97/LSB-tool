# LSB tool

## Custom LSB embedding/extracting tool

Instead of embedding just a text message, it is capable of embedding full files, due to its binary interpretation of the message files provided

Due to a very simple pseudo-random seed generated for each image, the pixels are shuffled before the injection of the file, so the embedded file or text cannot be detected by any steganography tool for reading pngs (such as zsteg)

The greatest effect for the human eye is with RGBA images, because of the alpha value. If the majority of the pixels have almost 0 alpha value, the subtle change in color of the pixel is virtually unnoticeable.

The code works by embedding the message file bit-by-bit in each pixel's color values' LSB[^0] (R,G,B). Before it embeds the file itself, it also embeds a header, which contains the following:

1. A 512bit sha256 header than contains the sha256(password) hash used to embed the files (also used to check if the password is correct for that file at the time of extraction
2. A 32-bit unsigned integer signaling how many files are there in the image
3. N 32-bit unsigned integers signaling the sizes of each file in the image (in bytes)

After this header, the files are embedded one right after the other, in the random order set by the Container initialization, with a random seed and generator based on the password and dimensions of the image

Example syntax:

Embedding:
```
./main.py -E -i container.png -p password -f messages/message messages/a.out -v
```

Extracting:
```
./main.py -e -i container_embedded.png -p password -v
```

Testing the tool
```
./test.sh
```

<details>
<summary>Following plans are in the work:</summary>
  
  1. **L2SB**[^1] embedding[^3]
  
</details>

[^0]: Least Significant Bit
[^1]: The 2 Least Significant Bits
[^2]: It can be used as an actual 33-bit unsigned integer, I just chose 33 over 32 to round up for the 3bits/pixel
[^3]: This would double the room for embedded files, at the cost of more noticeable changes in pixel color

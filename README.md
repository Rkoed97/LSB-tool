# LSB tool

## Custom LSB embedding/extracting tool

Instead of embedding just a text message, it is capable of embedding full files, due to its binary interpretation of the message files provided

For now, only RGB/RGBA/RGBa image modes are supported for encoding, and only one file per image.

Due to a very simple pseudo-random seed generated for each image (based on its size, no hashing yet), the pixels are shuffled before the injection of the file, so the embedded file or text cannot be detected by any steganography tool for reading pngs (such as zsteg)

The greatest effect for the human eye is with RGBA images, because of the alpha value. If the majority of the pixels have almost 0 alpha value, the subtle change in color of the pixel is virtually unnoticeable.

The code works by embedding the message file bit-by-bit in each pixel's color values' LSB[^0] (R,G,B). Before it embeds the file itself, it also embeds a 33-bit[^2] integer value that tells the decoder how big the message file is, in 8-bit unsigned integers. Thus, there is no need for additional padding for signaling the end of the file, as well as keeping the file well-hidden, due to it being split between (pseudo)random pixels in the image.

<details>
<summary>Following plans are in the work:</summary>

  1. Embedding in **gray-scale** images
  2. Embedding **multiple files** in the same image
  3. **2bit/pixel**[^5] embedding and **4bit/pixel**[^6] embedding[^3]
  4. **L2SB**[^1] embedding[^4]
  
</details>

[^0]: Least Significant Bit
[^1]: The 2 Least Significant Bits
[^2]: It can be used as an actual 33-bit unsigned integer, I just chose 33 over 32 to round up for the 3bits/pixel
[^3]: This would allow for up to double (for grey-scale) and 33% (for RGBA) more room to embed files in an image
[^4]: This would double the room for embedded files, at the cost of more noticeable changes in pixel color
[^5]: For gray-scale or palletised modes with an alpha channel (PA, LA etc.)
[^6]: For RGBA/RGBa modes
# Some code for testing enhanced RLE compression for the DLPC900 USB driver

import numpy
import time
import sys
from PIL import Image
import random

import usb.core
import usb.util

# Generate specified number of random RGB bmp images (blue channel random only)
def generateRandomRBGImages(number, resolution=(1920, 1080)):
    for imgNum in range(number):
        print(f"Generating image {imgNum}")

        img = Image.new("RGB", resolution, "black")  # create a new black image
        pixels = img.load()  # create the pixel map

        for i in range(img.size[0]):  # for every column
            for j in range(img.size[1]):  # for every row
                b = random.randint(0, 255)  # pick random value for blue channel
                pixels[i, j] = (0, 0, b)  # set the color

        filename = "random%s_rgb.bmp" % imgNum
        img.save(filename)
        print(f"Saved {filename}")


# Generate specified number of random greyscale bmp images (L instead of RGB)
def generateRandomBWImages(number, resolution=(1920, 1080)):
    for imgNum in range(number):
        print(f"Generating image {imgNum}")

        img = Image.new("L", resolution, 0)  # create a new black image
        pixels = img.load()  # create the pixel map

        for i in range(img.size[0]):  # for every column
            for j in range(img.size[1]):  # for every row
                pixels[i, j] = random.randint(0, 255)  # random grayscale
                # pixels[i,j] = 255                 # white

        filename = "random%s_bw.bmp" % imgNum
        img.save(filename)
        print(f"Saved {filename}")


# Convert a number into a bit string of given length
def numToBits(number, length):
    # number - number to convert
    # length - length of resultant bit string
    b = bin(number)[2:]
    padding = length - len(b)
    b = "0" * padding + b
    return b


# Convert a bit string into a list of full bytes
def bitsToBytes(bitString):
    bytelist = []
    if len(bitString) % 8 != 0:  # add 0 padding to fill last byte
        padding = 8 - len(bitString) % 8
        bitString = "0" * padding + bitString
    for i in range(len(bitString) // 8):  # pack bytes
        bytelist.append(int(bitString[8 * i : 8 * (i + 1)], 2))
    bytelist.reverse()
    return bytelist


# function that encodes a 8 bit numpy array matrix as enhanced run length encoded string of bits
def encode(image):
    #  header creation

    # print(f"encode...")
    bytecount = 48
    bitstring = []

    bitstring.append(0x53)
    bitstring.append(0x70)
    bitstring.append(0x6C)
    bitstring.append(0x64)

    width = numToBits(1920, 16)
    width = bitsToBytes(width)
    for i in range(len(width)):
        bitstring.append(width[i])

    height = numToBits(1080, 16)
    height = bitsToBytes(height)
    for i in range(len(height)):
        bitstring.append(height[i])

    total = numToBits(0, 32)
    total = bitsToBytes(total)
    for i in range(len(total)):
        bitstring.append(total[i])

    for i in range(8):
        bitstring.append(0xFF)

    for i in range(4):  #  black curtain
        bitstring.append(0x00)

    bitstring.append(0x00)

    bitstring.append(0x02)  #  enhanced rle

    bitstring.append(0x01)

    for i in range(21):
        bitstring.append(0x00)

    # end header creation

    n = 0
    i = 0
    j = 0

    while i < 1080:
        while j < 1920:
            # print(f"             encoding column {j}")
            if i > 0 and numpy.all(image[i, j, :] == image[i - 1, j, :]):
                while j < 1920 and numpy.all(image[i, j, :] == image[i - 1, j, :]):
                    n = n + 1
                    j = j + 1

                bitstring.append(0x00)
                bitstring.append(0x01)
                bytecount += 2

                if n >= 128:
                    byte1 = (n & 0x7F) | 0x80
                    byte2 = n >> 7
                    bitstring.append(byte1)
                    bitstring.append(byte2)
                    bytecount += 2

                else:
                    bitstring.append(n)
                    bytecount += 1
                n = 0

            else:
                if j < 1919 and numpy.all(image[i, j, :] == image[i, j + 1, :]):
                    n = n + 1
                    while j < 1919 and numpy.all(image[i, j, :] == image[i, j + 1, :]):
                        n = n + 1
                        j = j + 1
                    if n >= 128:
                        byte1 = (n & 0x7F) | 0x80
                        byte2 = n >> 7
                        bitstring.append(byte1)
                        bitstring.append(byte2)
                        bytecount += 2

                    else:
                        bitstring.append(n)
                        bytecount += 1

                    bitstring.append(image[i, j - 1, 0])
                    bitstring.append(image[i, j - 1, 1])
                    bitstring.append(image[i, j - 1, 2])
                    bytecount += 3

                    j = j + 1
                    n = 0

                else:
                    if (
                        j > 1917
                        or numpy.all(image[i, j + 1, :] == image[i, j + 2, :])
                        or numpy.all(image[i, j + 1, :] == image[i - 1, j + 1, :])
                    ):
                        bitstring.append(0x01)
                        bytecount += 1
                        bitstring.append(image[i, j, 0])
                        bitstring.append(image[i, j, 1])
                        bitstring.append(image[i, j, 2])
                        bytecount += 3

                        j = j + 1
                        n = 0

                    else:
                        bitstring.append(0x00)
                        bytecount += 1

                        toappend = []

                        while (
                            numpy.any(image[i, j, :] != image[i, j + 1, :])
                            and numpy.any(image[i, j, :] != image[i - 1, j, :])
                            and j < 1919
                        ):
                            n = n + 1
                            toappend.append(image[i, j, 0])
                            toappend.append(image[i, j, 1])
                            toappend.append(image[i, j, 2])
                            j = j + 1

                        if n >= 128:
                            byte1 = (n & 0x7F) | 0x80
                            byte2 = n >> 7
                            bitstring.append(byte1)
                            bitstring.append(byte2)
                            bytecount += 2

                        else:
                            bitstring.append(n)
                            bytecount += 1

                        for k in toappend:
                            bitstring.append(k)
                            bytecount += 1
                        n = 0
        j = 0
        i = i + 1
        bitstring.append(0x00)
        bitstring.append(0x00)
        bytecount += 2
    bitstring.append(0x00)
    bitstring.append(0x01)
    bitstring.append(0x00)
    bytecount += 3

    # has to end with multiple of 4 bytes
    while (bytecount) % 4 != 0:
        bitstring.append(0x00)
        bytecount += 1

    size = bytecount

    # print(f"{size}"")

    # update size that was previously set to 0
    total = numToBits(size, 32)
    total = bitsToBytes(total)
    for i in range(len(total)):
        bitstring[i + 8] = total[i]

    return bitstring, bytecount


# test compression
def test():

    images = []
    oldSizes = []
    newSizes = []
    compressionRatios = []
    durations = []

    for i in range(10):
        # filename = "random%s.bmp" % i
        filename = "projector/images/new1.bmp"
        print(f"encoding {filename}...")
        images.append(filename)

        with open(filename, "rb") as imageFile:
            f = imageFile.read()
            oldSizes.append(len(bytearray(f)))

        t = time.clock()

        im = Image.open(filename)
        imagedata = numpy.array(im)

        barray, size = encode(imagedata)

        durations.append(time.clock() - t)
        newSizes.append(size)
        compressionRatios.append(oldSizes[i] / size)

        print(f" Old size: {oldSizes[i]}")
        print(f" New size: {newSizes[i]}")
        print(f" Compression ratio {compressionRatios[i]}")
        print(f" Time to compress: {durations[i]}")

    for i in range(10):
        print(f"{images[i]}")
        print(f" Old size: {oldSizes[i]}")
        print(f" New size: {newSizes[i]}")
        print(f" Compression ratio {compressionRatios[i]}")
        print(f" Time to compress: {durations[i]}")

    print(f"Averages:")
    print(f" Average old size: {sum(oldSizes) / len(oldSizes)}")
    print(f" Average new size: {sum(newSizes) / len(newSizes)}")
    print(f" Average compression ratio: {sum(compressionRatios) / len(compressionRatios)}")
    print(f" Average time to compress: {sum(durations) / len(durations)}")


"""
    # bmp functions that could be added to USB driver

    # see 2.4.4.4.1 "Initialize Pattern BMP Load" in programmer's guide
    def setBmp(self,index,size):
        print(f"set bmp...")
        payload=[]

        index=numToBits(index,5)
        index='0'*11+index
        index=bitsToBytes(index)
        for i in range(len(index)):
            payload.append(index[i])

        total=numToBits(size,32)
        total=bitsToBytes(total)
        for i in range(len(total)):
            payload.append(total[i])

        self.send('w', 0x1a2a, payload)
        self.checkAllStatus()

    #  bmp loading function, See 2.4.4.4.2 "Pattern BMP Load" in programmer's guide
    def loadBmp(self,image,size):
        # divided in 56 bytes packages
        #   max  hid package size=64, flag bytes=4, usb command bytes=2
        #   size of package description bytes=2. 64-4-2-2=56

        print(f"Load bmp...")
        t=time.clock()

        packnum=size//504+1

        counter=0

        for i in range(packnum):
            if i %100==0:
                print(f"{i},{packnum}")
            payload=[]
            if i<packnum-1:
                leng=numToBits(504,16)
                bits=504
            else:
                leng=numToBits(size%504,16)
                bits=size%504
            leng=bitsToBytes(leng)
            for j in range(2):
                payload.append(leng[j])
            for j in range(bits):
                payload.append(image[counter])
                counter+=1
            self.send('w', 0x1a2b, payload, sequenceByte=0x11)


        print(f"{time.clock()-t}")
        self.checkAllStatus()

    def sendBmp(self,image,exp,rep=1):

            self.stopSequence()

            print(f"Send bmp...")

            oldLen = 0

            with open(image, "rb") as imageFile:
                f = imageFile.read()
                oldLen =  len(bytearray(f))

            t=time.clock()

            im = Image.open(image)
            imagedata = numpy.array(im)

            barray, size = encode(imagedata)

            elapsedTime = time.clock() - t

            print(f"{str(elapsedTime)} seconds, {str(oldLen)} bytes before, {str(size)} bytes after, compression ratio of {str(oldLen/size)}")

            self.define_pattern(exp)
            self.configure_pattern_LUT(rep)

            # size = len(barray)

            self.setBmp(0,size)
            print(f"uploading...")
            self.loadBmp(barray,size)

"""

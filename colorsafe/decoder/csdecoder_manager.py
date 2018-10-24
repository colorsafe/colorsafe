from PIL import Image
import re

from colorsafe.decoder.csimages_decoder import ColorSafeImagesDecoder

MaxColorVal = 255


class InputPages:
    def __init__(self, totalPages, height, width):
        self.totalPages = totalPages
        self.height = height
        self.width = width

    def getPagePixel(self, page, y, x):
        """For caller to implement"""
        pass


def sortStringsNumerically(l):
    def stringSplitByNumbers(x):
        r = re.compile(r'(\d+)')
        p = r.split(x)
        return [int(y) if y.isdigit() else y for y in p]

    return sorted(l, key=stringSplitByNumbers)


def getPageGrayPixel(pageNum, y, x, pagePixels, grayscale=True):
    pixel = pagePixels[pageNum][x, y]

    if grayscale:
        value = float(pixel) / MaxColorVal
        channels = (value, value, value)
    else:
        channels = (
            float(pixel[0]) / MaxColorVal,
            float(pixel[1]) / MaxColorVal,
            float(pixel[2]) / MaxColorVal)

    return channels


class ColorSafeDecoder:
    def __init__(self, filenames, colorDepth, outfile, saveMetadata):
        #channelsPageList = list()
        self.pagePixels = list()

        for filename in sortStringsNumerically(filenames):
            try:
                image = Image.open(filename)
            except IOError:
                print "ERROR: File {} is not a valid image file".format(filename)
                return

            pixels = image.load()
            self.pagePixels.append(pixels)

            #width = image.size[0]
            #height = image.size[1]

            # Remove alpha channel, combine into an appropriate channels list.
            #channelsList = list()
            # for y in range(height):
            #    channelsRow = list()
            #    for x in range(width):
            #        pixel = pixels[x,y]

            #        try:
            #            channels = ColorChannels(pixel[0], pixel[1], pixel[2])
            #        except TypeError: # Grayscale
            #            channels = ColorChannels(pixel, pixel, pixel)

            #        channels.multiplyShade([1.0 / MaxColorVal])
            #        channelsRow.append(channels)
            #    channelsList.append(channelsRow)

            # channelsPageList.append(channelsList)

        try:
            len(self.pagePixels[0][0, 0])  # Will be an int, not a list if image is grayscale
            grayscale = False
        except TypeError:
            grayscale = True

        def getPagePixel(self, pageNum, y, x):
            return getPageGrayPixel(pageNum, y, x, self.pagePixels, grayscale)

        pages = InputPages(len(self.pagePixels), image.size[1], image.size[0])
        pages.pagePixels = self.pagePixels
        pages.getPagePixel = getPagePixel.__get__(pages, pages.__class__)

        csFile = ColorSafeImagesDecoder(pages, colorDepth)

        print "Decoded %d bytes with %.2f%% average damage" % (
            len(csFile.dataStr), 100 * csFile.sectorDamageAvg)

        f = open(outfile, "w")
        f.write(csFile.dataStr)
        f.close()

        if saveMetadata:
            f = open("metadata.txt", "w")
            f.write(csFile.metadataStr)
            f.close()

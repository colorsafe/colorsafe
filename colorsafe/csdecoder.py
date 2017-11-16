import cslib
from PIL import Image

MaxColorVal = 255

class ColorSafeDecoder:
    #Preprocess self.pixelList in place
    def preprocess(self, images):
        """
        Not yet implemented

        1. Find image region of interest
        2. Correct rotation
        3. Normalize image brightness
        4. Resize image pixels into dots - calculate working width/height, scale image up to closest integer multiples of those
        """
        pass

    def __init__(self, args):
        channelsPageList = list()
        for filename in args.filenames:
            image = Image.open(filename)
            pixels = image.load()

            width = image.size[0]
            height = image.size[1]

            # Remove alpha channel, combine into an appropriate channels list.
            #TODO: Consider mmap.
            channelsList = list()
            for y in range(height):
                channelsRow = list()
                for x in range(width):
                    pixel = pixels[x,y]
                    channels = cslib.ColorChannels(pixel[0], pixel[1], pixel[2])
                    channels.multiplyShade([1.0 / MaxColorVal])
                    channelsRow.append(channels)
                channelsList.append(channelsRow)

            channelsPageList.append(channelsList)

        self.preprocess(channelsPageList)

        csFile = cslib.ColorSafeImageFiles()
        data = csFile.decode(channelsPageList, args.colorDepth)

        f = open("outdata.txt","w")
        f.write(data)
        f.close()

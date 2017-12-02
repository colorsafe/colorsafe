from colorsafe import ColorChannels, ColorSafeImageFiles
from PIL import Image

MaxColorVal = 255

class ColorSafeDecoder:
    def __init__(self, args):
        channelsPageList = list()
        for filename in args.filenames:
            image = Image.open(filename)
            pixels = image.load()

            width = image.size[0]
            height = image.size[1]

            # Remove alpha channel, combine into an appropriate channels list.
            channelsList = list()
            for y in range(height):
                channelsRow = list()
                for x in range(width):
                    pixel = pixels[x,y]

                    try:
                        channels = ColorChannels(pixel[0], pixel[1], pixel[2])
                    except TypeError: # Grayscale
                        channels = ColorChannels(pixel, pixel, pixel)

                    channels.multiplyShade([1.0 / MaxColorVal])
                    channelsRow.append(channels)
                channelsList.append(channelsRow)

            channelsPageList.append(channelsList)

        csFile = ColorSafeImageFiles()
        data,metadata = csFile.decode(channelsPageList, args.colorDepth)

        print "Decoded successfully with %.2f %% average damage" % (100*csFile.sectorDamageAvg)

        f = open(args.outfile,"w")
        f.write(data)
        f.close()

        if args.saveMetadata:
            f = open("metadata.txt","w")
            f.write(metadata)
            f.close()

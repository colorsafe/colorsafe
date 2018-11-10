import math
import constants
import utils


class ColorChannels:
    """A group of color channels consisting of Red, Green, and Blue values from 0.0 to 1.0.

       TODO: Channels and values (colors and shades) should be stored in metadata header separately.
       TODO: Cmd program can simplify color/shade combos with Grayscale, CYMK, RGB, and higher options.

    """
    RedDefault = 0.0
    GreenDefault = 0.0
    BlueDefault = 0.0

    def __init__(self, red=RedDefault, green=GreenDefault, blue=BlueDefault):
        self.red = red
        self.green = green
        self.blue = blue

    def setChannels(self, channels):
        if len(channels) == constants.ColorChannels:
            self.red = channels[0]
            self.green = channels[1]
            self.blue = channels[2]
        elif len(channels) == constants.ColorChannels1:
            self.red = channels[0]
            self.green = channels[0]
            self.blue = channels[0]

    def multiplyShade(self, shades):
        if len(shades) == constants.ColorChannels:
            self.red *= shades[0]
            self.green *= shades[1]
            self.blue *= shades[2]
        elif len(shades) == constants.ColorChannels1:
            self.red *= shades[0]
            self.green *= shades[0]
            self.blue *= shades[0]

    def subtractShade(self, shade):
        self.red -= shade
        self.green -= shade
        self.blue -= shade

    def getChannels(self):
        return (self.red, self.green, self.blue)

    def getAverageShade(self):
        return (self.red + self.green + self.blue) / constants.ColorChannels


class Dot:
    """A group of channels representing a group of colorDepth bits.
    """

    channels = None

    def getChannelNum(self, bitCount):
        """Get channel number based on how many bits (based on colorDepth) are needed. Currently, this maps 1:1.
        """
        # TODO: Make these modes options for any colorDepth, add to metadata
        # header.
        if bitCount % constants.ColorChannels == 0:
            channelNum = constants.ColorChannels
        elif bitCount % constants.ColorChannels2 == 0:
            channelNum = constants.ColorChannels2
        else:
            channelNum = constants.ColorChannels1

        return channelNum

    def getChannels(self):
        return self.channels.getChannels()


class DotByte:
    """A group of 8 Dots, representing colorDepth bytes of data.
    """

    dots = None
    bytesList = None


class DotRow:
    """A horizontal group of DotBytes.
    """

    dotBytes = None
    bytesList = None

    @staticmethod
    def getMaxRowBytes(colorDepth, width):
        return colorDepth * width / constants.ByteSize

    @staticmethod
    def getMagicRowBytes(colorDepth, width):
        maxRowBytes = DotRow.getMaxRowBytes(colorDepth, width)
        return [constants.MagicByte] * maxRowBytes

    @staticmethod
    def getXORMask(rowNumber):
        return constants.Byte55 if rowNumber % 2 == 0 else constants.ByteAA


class Sector:
    """A vertical group of DotRows.
    """

    @staticmethod
    def get_block_sizes(height, width, color_depth, ecc_rate):
        def fill_block_sizes(bytes, max_bytes_per_block):
            if bytes <= max_bytes_per_block:
                return [bytes]
            else:
                block_sizes = [max_bytes_per_block] * (bytes / max_bytes_per_block)

                remainder = bytes % max_bytes_per_block
                if remainder != 0:
                    last_two_avg = utils.average([remainder, max_bytes_per_block])
                    block_sizes[-1] = int(math.ceil(last_two_avg))
                    block_sizes.append(int(math.floor(last_two_avg)))

            return block_sizes

        data_row_count = Sector.getDataRowCount(height, ecc_rate)
        ecc_row_count = height - constants.MagicRowHeight - data_row_count

        total_bytes = (data_row_count + ecc_row_count) * width * color_depth / constants.ByteSize
        data_bytes = data_row_count * width * color_depth / constants.ByteSize
        ecc_bytes = ecc_row_count * width * color_depth / constants.ByteSize

        data_row_percentage = float(data_row_count) / (height - constants.MagicRowHeight)
        ecc_row_percentage = float(ecc_row_count) / (height - constants.MagicRowHeight)

        max_data_block_size = int(round(data_row_percentage * constants.RSBlockSizeMax))
        max_ecc_block_size = int(round(ecc_row_percentage * constants.RSBlockSizeMax))

        rs_block_sizes = fill_block_sizes(total_bytes, constants.RSBlockSizeMax)
        data_block_sizes = fill_block_sizes(data_bytes, max_data_block_size)
        ecc_block_sizes = fill_block_sizes(ecc_bytes, max_ecc_block_size)

        return data_row_count, ecc_row_count, rs_block_sizes, data_block_sizes, ecc_block_sizes

    @staticmethod
    def getDataRowCount(height, eccRate):
        return int(math.floor(
            (height - constants.MagicRowHeight) / (1 + eccRate)))


class Metadata:
    eccMode = "ECC"
    dataMode = "DAT"
    pageNumber = "PAG"
    metadataCount = "MET"

    ambiguous = "AMB"
    crc32CCheck = "CRC"
    csCreationTime = "TIM"
    eccRate = "ECR"
    fileExtension = "EXT"
    fileSize = "SIZ"
    filename = "NAM"
    majorVersion = "MAJ"
    minorVersion = "MIN"
    revisionVersion = "REV"
    totalPages = "TOT"

    # Required, in order
    RequiredInOrder = (eccMode, dataMode, pageNumber, metadataCount)

    # Required, in no order
    # TODO: Some of these should possibly be required on each page
    RequiredNoOrder = (
        ambiguous,
        crc32CCheck,
        eccRate,
        majorVersion,
        minorVersion,
        revisionVersion,
        fileSize,
        csCreationTime,
        totalPages,
        fileExtension,
        filename)

    # TODO: Filename/ext not required, how to track?


class MetadataSector(Sector):
    MetadataInitPaddingBytes = 1
    ColorDepthBytes = 1
    MetadataSchemeBytes = 3
    MetadataEndPaddingBytes = 1
    MetadataDefaultScheme = 1

    metadata = None
    data = None

    height = None
    width = None
    colorDepth = None
    eccRate = None
    dataStart = None


class Page:
    """A collection of sectors, used for shuffling and placing them correctly on each page, and for keeping track of
    page specific properties, like page number.
    """

    sectors = None

    dataSectors = None
    metadataSectors = None
    pageNumber = None
    sectorsVertical = None
    sectorsHorizontal = None
    colorDepth = None
    eccRate = None
    sectorHeight = None
    sectorWidth = None


class ColorSafeFile:
    """The ColorSafe data and borders, all dimensions in dots."""

    data = None


class ColorSafeImages:
    """A collection of saved ColorSafeFile objects, as images of working regions without outside borders or headers
    """

    images = None
from colorsafe.csdatastructures import constants, DotByte, DotRow, Sector, Page, ColorSafeFile, MetadataSector
from colorsafe.csdatastructures import Dot
from colorsafe.utils import floatToBinaryList, intToBinaryList


class DotDecoder(Dot):
    """A group of channels representing a group of colorDepth bits.

    There are three modes of encoding a color into a dot: shade, primary, and secondary.

    TODO: Extend to multiple shades
    """

    def __init__(self, channels, colorDepth, thresholdWeight):
        """Takes in a list of channels, returns a list of bytes
        """
        channelNum = self.getChannelNum(colorDepth)

        bitList = None

        if channelNum == constants.ColorChannels:
            bitList = self.decodePrimaryMode(channels, colorDepth)

        if channelNum == constants.ColorChannels1:
            bitList = self.decodeShadeMode(
                channels, colorDepth, thresholdWeight)

        if channelNum == constants.ColorChannels2:
            bitList = self.decodeSecondaryMode(channels, colorDepth)

        self.bitList = bitList

    def decodePrimaryMode(self, channels, colorDepth):
        bitList = list()

        for channel in channels.getChannels():
            bitList.extend(
                floatToBinaryList(
                    channel,
                    colorDepth /
                    constants.ColorChannels))

        return bitList

    def decodeShadeMode(self, channels, colorDepth, thresholdWeight):
        val = channels.getAverageShade()

        bitList = [int(val > thresholdWeight)]
        return bitList

    def decodeSecondaryMode(self, channels, colorDepth):
        zeroPosition = 0
        shadeBits = colorDepth - 2

        # Find the color, e.g. the 0 position, if channel is less than the
        # threshold: half the smallest possible value.
        for i, channel in enumerate(channels.getChannels()):
            if channel < 0.5 / (1 << shadeBits):
                zeroPosition = i + 1
                break

        # These two bits are set by the color itself: 0 -> 00, 1 -> 10, 2 ->
        # 01, 3 -> 11
        firstHalfFirstBit, secondHalfFirstBit = intToBinaryList(
            zeroPosition, constants.ColorChannels2)

        # Remove zero position, since it won't contribute to the shade value
        setChannels = list(channels.getChannels())
        if zeroPosition >= 1:
            setChannels.pop(zeroPosition - 1)

        # Get average shade value
        valAvg = float(sum(setChannels)) / len(setChannels)

        # Get the shade bits, insert the first two color bits at first and
        # halfway positions
        bitList = floatToBinaryList(valAvg, shadeBits)
        bitList.insert(0, firstHalfFirstBit)
        bitList.insert(colorDepth / 2, secondHalfFirstBit)

        return bitList


class DotByteDecoder(DotByte):
    """A group of 8 Dots, representing colorDepth bytes of data.
    """

    def __init__(self, channelsList, colorDepth, thresholdWeight):
        """Takes in a list of exactly ByteSize (8) channels, returns a list of decoded bytes.

        Sets each dot's decoded data into colorDepth bytes.
        """
        bytesList = list()
        for i in range(colorDepth):
            bytesList.append(constants.Byte00)

        for i in range(constants.ByteSize):
            # If channelsList has less than 8 channels, explicitly fail
            channel = channelsList[i]

            dot = DotDecoder(channel, colorDepth, thresholdWeight)
            data = dot.bitList

            for b in range(colorDepth):
                bytesList[b] = bytesList[b] | data[b] << i

        self.bytesList = bytesList


class DotRowDecoder(DotRow):
    """A horizontal group of DotBytes.
    """

    def __init__(
            self,
            channelsList,
            colorDepth,
            width,
            rowNumber,
            thresholdWeight,
            xorRow=True):
        """Takes in a list of width channels, returns a list of decoded bytes
        """
        if width % constants.ByteSize != 0:
            return None

        mask = self.getXORMask(rowNumber)

        bytesList = list()
        for w in range(0, width, constants.ByteSize):
            channels = channelsList[w: w + constants.ByteSize]
            db = DotByteDecoder(channels, colorDepth, thresholdWeight)
            data = db.bytesList
            bytesList.extend(data)

        for i, byte in enumerate(bytesList):
            if xorRow:
                bytesList[i] = bytesList[i] ^ mask
            else:
                bytesList[i] = bytesList[i]

        self.bytesList = bytesList


class SectorDecoder(Sector):
    """A vertical group of DotRows.
    """

    def __init__(
            self,
            channelsList,
            colorDepth,
            height,
            width,
            dataRowCount,
            eccRate,
            thresholdWeight):
        """Takes in a list of height*width channels, returns a list of decoded data/ecc bytes
        """
        dataRows = list()
        eccRows = list()

        self.height = height
        self.width = width
        self.colorDepth = colorDepth
        self.eccRate = eccRate
        self.dataRowCount, self.eccRowCount, self.rsBlockSizes, self.dataBlockSizes, self.eccBlockSizes = \
            Sector.get_block_sizes(height, width, colorDepth, eccRate)

        for row in range(0, height * width, width):
            channels = channelsList[row: row + width]
            rowNum = row / width

            dotRow = DotRowDecoder(channels, colorDepth, width, rowNum, thresholdWeight)
            bytesList = dotRow.bytesList

            if row < dataRowCount * width:
                dataRows.extend(bytesList)

            # Ignore magic row
            if row > dataRowCount * width:
                eccRows.extend(bytesList)

        self.dataRows = dataRows
        self.eccRows = eccRows


class MetadataSectorDecoder(MetadataSector):
    def getMetadata(self):
        """TODO: Decode all metadata from the encoded metadata string
        """
        pass


class PageDecoder(Page):
    """A collection of sectors, used for shuffling and placing them correctly on each page, and for keeping track of
    page specific properties, like page number.
    """

    def __init__(self,
               channelsSectorList,
               colorDepth,
               sectorHeight,
               sectorWidth,
               sectorsVertical,
               sectorsHorizontal,
               dataRows,
               thresholdWeight):
        """Takes a list of channels, places sectors and metadata sectors into this object.

        Channels list must be a list size sectorsVertical*sectorsHorizontal. Each inner list will consist of
        sectorHeight*sectorWidth channels.
        """
        sectors = list()
        for channelsList in channelsSectorList:
            s = SectorDecoder(channelsList,
                              colorDepth,
                              sectorHeight,
                              sectorWidth,
                              dataRows,
                              thresholdWeight)
            sectors.add(s)

        self.sectors = sectors

    def getMetadataSectors(self):
        """TODO: Get all metadata sectors in this page, using method from the spec: random-reproducible
        """
        pass

    def getDataSectors(self):
        """TODO: Get all data sectors in this page - all non-metadata sectors
        """
        pass


class ColorSafeFileDecoder(ColorSafeFile):
    """The ColorSafe data and borders, all dimensions in dots."""

    def __init__(self, pages):
        """TODO: Take a list of channels, format into sectors, then set a list of pages into this object

        0. Preprocess
            1. Find potential location of metadata sectors based on sector count
            2. Function to take channels, bucket into sectors based on sector coordinate
        1. Process each page:
            1. Get all metadata sectors
            2. Get colordepth, metadata mode from the first metadata sector
            3. Get all data sectors
        2. Process entire file
            1. Shuffle ECC data
            2. Get corrected data
            3. Combine metadata sectors, save metadata
            4. Combine sectors, save file
        """
        pass

    def metadataSectorsToMetadata(self):
        """TODO: Take a list of metadataSectors, get their metadata, and combine them into a single Metadata object
        """
        pass

    def pagesToMetadataSectors(self, pages):
        """TODO: Take a list of pages and return a list of all metadataSectors.
        Get the random-reproducible inserted order of metadata, add each into a list in order.
        """
        pass

    def pagesToDataSectors(self, pages):
        """TODO: Take a list of pages and return the positions of dataSectors and metadataSectors.
        Place all sectors that aren't metadata sequentially into a list
        """
        pass

    def deshuffleECCData(self):
        """TODO: Take a list of pages, and de-shuffle the ECC data in each sector according to the spec - random-reproducible.
        This will return a list of pages with the original ECC data positions.
        """
        pass

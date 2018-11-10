import binascii
import math
import random
import time

from unireedsolomon import RSCoder

from colorsafe.csdatastructures import constants, ColorChannels, Dot, DotByte, DotRow, Sector, Page, ColorSafeFile, \
    Metadata, MetadataSector
from colorsafe.exceptions import EncodingError
from colorsafe.utils import binaryListToVal, binaryListToFloat


class DotEncoder(Dot):
    """A group of channels representing a group of colorDepth bits.

    There are three modes of encoding a color into a dot: shade, primary, and secondary.
    """

    def __init__(self, bitList):
        """Set values from bitList into channels.
        """
        channelNum = self.getChannelNum(len(bitList))

        if channelNum == constants.ColorChannels or channelNum == constants.ColorChannels1:
            channels = self.encodeSecondaryMode(bitList, channelNum)

        if channelNum == constants.ColorChannels2:
            channels = self.encodePrimaryMode(bitList)

        self.channels = channels

    def encodePrimaryMode(self, bitList):
        """Primary mode: Divide list into 2. Each half's first bit represents color, the rest combined represent shade.
        Return color channels. Thus, the shade alone represents (colorDepth-2) bits of information.
        """
        firstHalf = bitList[0:len(bitList) / 2]
        secondHalf = bitList[len(bitList) / 2:len(bitList)]

        firstHalfFirstBit = firstHalf.pop(0)
        secondHalfFirstBit = secondHalf.pop(0)

        # A terse way to map 2 bits to 4 colors (00: White, 01: Magenta, 10: Cyan, 11: Yellow)
        # TODO: Swap magenta and cyan?
        index = binaryListToVal([firstHalfFirstBit, secondHalfFirstBit])
        color = [1.0] * (constants.ColorChannels + 1)
        color[index] = 0
        color = tuple(color[1:])

        channels = ColorChannels()
        channels.setChannels(color)

        valueList = firstHalf + secondHalf
        if len(valueList):
            value = binaryListToFloat(valueList)
            channels.multiplyShade([value])

        return channels

    def encodeSecondaryMode(self, bitList, channelNum):
        """Secondary mode: Divide list into channelNum. Each division represents the shade of each channel. Return color
        channels.

        For example, with 3-color channels, list is divided into 3, with each division corresponding to the shade of R,
        G, or B. With 1-color channel, list is not divided, and the entire list corresponds to the shade of gray.
        """
        channelVals = list()
        bpc = len(bitList) / channelNum  # Bits per channel

        for b in range(0, len(bitList), bpc):
            channelBits = bitList[b: b + bpc]
            channelVal = binaryListToFloat(channelBits)
            channelVals.append(channelVal)

        channels = ColorChannels()
        channels.setChannels(channelVals)

        return channels


class DotByteEncoder(DotByte):
    """A group of 8 Dots, representing colorDepth bytes of data.
    """
    # TODO: Encode should return ColorChannels object, not Dot.

    def __init__(self, bytesList, colorDepth):
        """Takes in a list of up to colorDepth bytes, returns a list of ByteSize (8) encoded dots.

        For each input byte in bytesList, take the i'th bit and encode into a dot.
        """
        dots = list()
        for i in range(constants.ByteSize):
            vals = list()

            # Ensure colorDepth bytes are added, even if bytesList doesn't have
            # enough data (0-pad)
            for b in range(colorDepth):
                byte = constants.Byte00

                if b < len(bytesList):
                    byte = bytesList[b]

                vals.append(byte >> i & 1)

            p = DotEncoder(vals)
            dots.append(p)

        self.bytesList = bytesList
        self.dots = dots


class DotRowEncoder(DotRow):
    """A horizontal group of DotBytes.
    """

    def __init__(self, bytesList, colorDepth, width, rowNumber, xorRow=True):
        """Takes in a list of bytes, returns a list of encoded dotBytes.

        Performs an XOR on each byte, alternating between AA and 55 per row to prevent rows/columns of 0's or 1's.
        If less bytes are supplied than fit into a row, they will be 0-padded to fill to the end.
        """
        if width % constants.ByteSize != 0:
            return None

        # TODO: Set AMB metadata parameter instead. Fix this - fails when magic row is intended.
        # If the bytes to be encoded represent the magic row, fail.
        # if bytesList == DotRow.getMagicRowBytes(colorDepth, width):
        #    return None

        maxRowBytes = self.getMaxRowBytes(colorDepth, width)
        mask = self.getXORMask(rowNumber)

        dotBytes = list()
        for inByte in range(0, maxRowBytes, colorDepth):
            bl = bytesList[inByte: inByte + colorDepth]

            if len(bl) < colorDepth:
                bl.extend([constants.Byte00] * (colorDepth - len(bl)))

            blTemp = list()
            for b in bl:
                # Valid bytesList inputs are strings (e.g. read from a file) or
                # ints (e.g. metadata header constants).
                try:
                    if xorRow:
                        blTemp.append(ord(b) ^ mask)
                    else:
                        blTemp.append(ord(b))
                except TypeError:
                    if xorRow:
                        blTemp.append(b ^ mask)
                    else:
                        blTemp.append(b)

            db = DotByteEncoder(blTemp, colorDepth)
            dotBytes.append(db)

        self.dotBytes = dotBytes


class SectorEncoder(Sector):
    """A vertical group of DotRows.
    """

    def __init__(self, data, colorDepth, height, width, eccRate, dataStart=0):
        """Takes in a list of bytes, returns a list of dotRows
        """
        self.height = height
        self.width = width
        self.colorDepth = colorDepth
        self.eccRate = eccRate
        self.data = data

        self.dataRowCount, self.eccRowCount, self.rsBlockSizes, self.dataBlockSizes, self.eccBlockSizes = \
            Sector.get_block_sizes(height, width, colorDepth, eccRate)

        self.putData(dataStart)
        self.putECCData(dataStart)

    def putData(self, dataStart=0):
        """Takes in a list of data, returns a list of dataRows
        """
        self.dataRows = list()
        bytesPerRow = self.width * self.colorDepth / constants.ByteSize

        for row in range(self.dataRowCount):
            minIndex = dataStart + row * bytesPerRow
            maxIndex = dataStart + ((row + 1) * bytesPerRow)

            insertData = self.data[minIndex: maxIndex]
            insertRow = DotRowEncoder(
                list(insertData),
                self.colorDepth,
                self.width,
                row)
            self.dataRows.append(insertRow)

    def putECCData(self, dataStart=0):
        eccData = list()

        totalBytes = (self.height - 1) * self.width / constants.ByteSize
        for i, rsBlockLength in enumerate(self.rsBlockSizes):
            messageLength = self.dataBlockSizes[i]
            errorLength = self.eccBlockSizes[i]
            rsEncoder = RSCoder(rsBlockLength, messageLength)

            minIndex = dataStart + sum(self.dataBlockSizes[:i])
            maxIndex = dataStart + sum(self.dataBlockSizes[:i + 1])

            dataBlock = list(self.data[minIndex: maxIndex])
            if len(dataBlock) < messageLength:
                dataBlock.extend([chr(constants.Byte00)] *
                                 (messageLength - len(dataBlock)))
            dbTemp = ""
            for c in dataBlock:
                try:
                    dbTemp += c
                except TypeError:
                    dbTemp += chr(c)

            rsBlock = rsEncoder.encode(dbTemp)
            eccBlock = rsBlock[-errorLength:]

            eccData.extend(eccBlock)

        eccMagicRow = DotRowEncoder(
            DotRow.getMagicRowBytes(
                self.colorDepth,
                self.width),
            self.colorDepth,
            self.width,
            self.dataRowCount)

        self.eccRows = [eccMagicRow]
        bytesPerRow = self.width * self.colorDepth / constants.ByteSize
        for row in range(self.eccRowCount):
            insertData = eccData[row * bytesPerRow: (row + 1) * bytesPerRow]
            insertRow = DotRowEncoder(insertData, self.colorDepth, self.width, row)
            self.eccRows.append(insertRow)

        self.eccData = eccData

    # TODO: For ECC swapping in CS file, to distribute across pages
    def getECCbit(self, i):
        pass

    def putECCbit(self, i):
        pass


class MetadataSectorEncoder(MetadataSector, SectorEncoder):

    def __init__(self, height, width, colorDepth, eccRate, metadata):
        self.height = height
        self.width = width
        self.colorDepth = colorDepth
        self.eccRate = eccRate
        self.dataStart = 0  # TODO: Make this an argument for putdata, not a self object

        self.dataRowCount, self.eccRowCount, self.rsBlockSizes, self.dataBlockSizes, self.eccBlockSizes = \
            Sector.get_block_sizes(height, width, colorDepth, eccRate)

        self.putMetadata(metadata)
        self.putData()
        self.putECCData()

    # TODO: This only supports values less than 256. It XOR's inelegantly. Fix
    # it, add non-xor method to DotByte?
    def getMetadataSchemeBytes(self):
        ret = [self.MetadataDefaultScheme ^ constants.Byte55] * self.colorDepth
        ret += [constants.Byte55] * self.colorDepth * \
            (self.MetadataSchemeBytes - 1)
        return ret

    def getColorDepthBytes(self):
        return [self.colorDepth ^ constants.Byte55] * self.colorDepth

    def putMetadata(self, metadata):
        self.metadata = dict()

        # Format header
        self.data = DotRow.getMagicRowBytes(self.colorDepth, self.width)

        # Multiply each by self.colorDepth to make these effectively black and white
        # TODO: Header 11110000/00001111 instead of 11111111 - less likely to
        # collide/smudge first/last bit.
        self.data.extend([constants.ByteAA] *
                         self.MetadataInitPaddingBytes *
                         self.colorDepth)
        self.data.extend(self.getColorDepthBytes())
        self.data.extend(self.getMetadataSchemeBytes())
        self.data.extend([constants.ByteAA] *
                         self.MetadataEndPaddingBytes *
                         self.colorDepth)

        # Format metadata, interleave lists and 0-byte join
        # TODO: Encode ints not in ascii
        for (key, value) in metadata.items():
            kvString = str(key) + chr(constants.Byte00) + \
                (str(value) if value else "") + chr(constants.Byte00)

            # TODO: Get from static method?
            maxDataPerSector = Sector.getDataRowCount(
                self.height, self.eccRate) * self.width * self.colorDepth
            if len(kvString) + len(self.data) < maxDataPerSector:
                self.data.extend([ord(i) for i in kvString])
                self.metadata[key] = value

        return self.metadata

    def updateMetadata(self, key, value):
        """Update the value by rewriting all metadata.
        Used when value is known after all data and metadata is encoded, or is unwieldy to calculate before.
        Updated value should be less than the originally written one, or else metadata could drop existing data.
        """
        self.metadata[key] = value
        self.putMetadata(self.metadata)


class PageEncoder(Page):
    """A collection of sectors, used for shuffling and placing them correctly on each page, and for keeping track of
    page specific properties, like page number.
    """

    def __init__(self,
                 dataSectors,
                 metadataSectors,
                 pageNumber,
                 sectorsVertical,
                 sectorsHorizontal,
                 colorDepth,
                 eccRate,
                 sectorHeight,
                 sectorWidth):
        """Takes in a list of data and metadata sectors, places them in this object in the correct order.
        """
        self.dataSectors = dataSectors
        self.metadataSectors = metadataSectors
        self.pageNumber = pageNumber
        self.sectorsVertical = sectorsVertical
        self.sectorsHorizontal = sectorsHorizontal
        self.colorDepth = colorDepth
        self.eccRate = eccRate
        self.sectorHeight = sectorHeight
        self.sectorWidth = sectorWidth

        self.putMetadataSectors()
        self.putDataSectors()

    def putDataSectors(self):
        """Put all data sectors into this page, around all metadata sectors
        """
        self.dataSectorCount = (
            self.sectorsVertical * self.sectorsHorizontal) - len(self.metadataSectors)
        dataSectorIndex = 0
        for sectorIndex, sector in enumerate(self.sectors):
            if sector is None:
                self.sectors[sectorIndex] = self.dataSectors[dataSectorIndex]
                dataSectorIndex += 1

    def putMetadataSectors(self):
        """Put all metadata sectors into this page, using method from the spec: random-reproducible
        """
        self.sectors = [None] * \
            (len(self.dataSectors) + len(self.metadataSectors))

        random.seed(self.pageNumber)
        allMetadataPagePositions = range(0, len(self.sectors))
        random.shuffle(allMetadataPagePositions)
        self.metadataSectorsPositions = allMetadataPagePositions[: len(
            self.metadataSectors)]

        metadataSectorIndex = 0
        for i in self.metadataSectorsPositions:
            self.sectors[i] = self.metadataSectors[metadataSectorIndex]
            metadataSectorIndex += 1


class ColorSafeFileEncoder(ColorSafeFile):
    """The ColorSafe data and borders, all dimensions in dots."""

    def __init__(self,
               data,
               sectorsVertical,
               sectorsHorizontal,
               colorDepth,
               eccRate,
               sectorHeight,
               sectorWidth,
               filename,
               fileExtension):
        """Take data and format it into data Sectors, then add metadata Sectors. Then use them to put Pages into this
        object.
        """
        self.data = data
        self.sectorsVertical = sectorsVertical
        self.sectorsHorizontal = sectorsHorizontal
        self.colorDepth = colorDepth
        self.eccRate = eccRate
        self.sectorHeight = sectorHeight
        self.sectorWidth = sectorWidth
        self.filename = filename
        self.fileExtension = fileExtension

        self.dataRowCount = Sector.getDataRowCount(
            self.sectorHeight, self.eccRate)

        self.putDataSectors(self.data)

        # TODO: this should account for metadata
        self.maxData = self.dataPerSector * self.sectorsVertical * self.sectorsHorizontal

        self.createMetadataSectors()
        self.sectorsToPages(self.dataSectors, self.metadataSectors)

    def putDataSectors(self, data):
        """Take data and place it into a list of Sectors, bucketing as much data as possible into each one.
        """
        self.dataSectors = list()

        self.dataPerSector = self.sectorWidth * self.colorDepth * \
            self.dataRowCount / constants.ByteSize

        for dataStart in range(0, len(self.data), self.dataPerSector):
            # TODO: Setting data into Sector in place (using Sector's dataStart)
            # argument) may improve performance
            data = self.data[dataStart: dataStart + self.dataPerSector]

            s = SectorEncoder(
                data,
                self.colorDepth,
                self.sectorHeight,
                self.sectorWidth,
                self.eccRate)

            self.dataSectors.append(s)

        return self.dataSectors

    def createMetadataSectors(self):
        """Create metadata sectors from ColorSafeFile properties, Constants, and other functions.
        """
        self.metadata = dict()
        self.metadataSectors = list()
        self.totalMetadataSectors = 0

        csCreationTime = int(time.time())

        # TODO: Must include source! Change this implementation
        crc32CCheck = binascii.crc32("0")

        fileSize = len(self.data)  # In bytes

        self.metadata[Metadata.crc32CCheck] = crc32CCheck
        self.metadata[Metadata.csCreationTime] = csCreationTime
        self.metadata[Metadata.dataMode] = constants.DataMode
        self.metadata[Metadata.eccMode] = constants.ECCMode
        self.metadata[Metadata.eccRate] = self.eccRate
        self.metadata[Metadata.fileExtension] = self.fileExtension
        self.metadata[Metadata.fileSize] = fileSize
        self.metadata[Metadata.filename] = self.filename
        self.metadata[Metadata.majorVersion] = constants.MajorVersion
        self.metadata[Metadata.minorVersion] = constants.MinorVersion
        self.metadata[Metadata.revisionVersion] = constants.RevisionVersion

        # This should not cause extra 0's in value; it will be updated with
        # correct values before writing
        self.metadata[Metadata.pageNumber] = chr(
            0) * constants.TotalPagesMaxBytes
        self.metadata[Metadata.totalPages] = chr(
            0) * constants.TotalPagesMaxBytes

        # Set to maximum possible. This will be updated with correct values
        # before writing.
        self.metadata[Metadata.metadataCount] = self.sectorsVertical * \
            self.sectorsHorizontal

        # Reverse sort metadata that has no required order
        metadataRequiredNoOrderKeys = set(
            [key for (key, value) in self.metadata.items()]) - set(Metadata.RequiredInOrder)
        metadataRequiredNoOrder = [(key, self.metadata[key])
                                   for key in metadataRequiredNoOrderKeys]
        metadataRequiredNoOrder.sort(key=lambda tup: -len(str(tup)))
        metadataRequiredNoOrder = [
            key for (key, value) in metadataRequiredNoOrder]

        metadataInsertOrdered = list(Metadata.RequiredInOrder) + metadataRequiredNoOrder

        metadataRemaining = metadataInsertOrdered
        while metadataRemaining != Metadata.RequiredInOrder:
            metadataToInsert = dict()
            for key in metadataRemaining:
                metadataToInsert[key] = self.metadata[key]

            mdSector = MetadataSectorEncoder(
                self.sectorHeight,
                self.sectorWidth,
                self.colorDepth,
                self.eccRate,
                metadataToInsert)

            metadataInserted = mdSector.metadata

            # If required in order metadata not inserted, break; nothing else
            # will fit anyways
            breakLoop = False
            for md in Metadata.RequiredInOrder:
                if md not in metadataInserted:
                    breakLoop = True
                    break
            if breakLoop:
                break

            # If nothing additional after required metadata, remove first
            # (largest) non-ordered metadata kv pair
            if metadataInserted == Metadata.RequiredInOrder:
                metadataRemaining.pop(len(Metadata.RequiredInOrder))
                continue

            self.metadataSectors.append(mdSector)

            metadataRemaining = list(
                set(metadataRemaining) -
                set(metadataInserted))

        self.sectorsPerPage = self.sectorsVertical * self.sectorsHorizontal

        if self.sectorsPerPage <= 1:
            raise EncodingError("Error: cannot encode 1 sector per page. Page height/width is possibly too small.")

        dsCount = len(self.dataSectors)
        msCount = len(self.metadataSectors)

        # The following equations are derived from the combination of two dependent equations:
        # 1. The number of metadata sectors is equal to the first one on each page, plus the rest
        # 2. Number of pages is the ceiling of data sector + metadata sector count divided by sectors per page.
        # It is valid only for m+d>1, so use max(equation,1) to ensure it
        # always returns one or more pages.
        totalPages = max(
            int(math.ceil(float(dsCount + msCount - 1) / (self.sectorsPerPage - 1))), 1)
        totalMetadataSectors = totalPages + msCount - 1

        self.totalSectors = dsCount + totalMetadataSectors

        paddingMetadataSectors = self.sectorsHorizontal - \
            (self.totalSectors % self.sectorsHorizontal)
        self.totalSectors += paddingMetadataSectors
        totalMetadataSectors += paddingMetadataSectors

        # Get metadataPositions dict: { pageNum: metadataSectorsOnPage, ... }
        metadataPositions = range(totalPages)
        random.seed(0)
        random.shuffle(metadataPositions)
        metadataPositions = metadataPositions * \
            int(math.ceil(totalMetadataSectors / totalPages))
        metadataPositions = metadataPositions[:totalMetadataSectors]
        metadataPositions = {
            i: metadataPositions.count(i) for i in metadataPositions}

        self.totalPages = totalPages
        self.totalMetadataSectors = totalMetadataSectors
        self.metadataPositions = metadataPositions

    def sectorsToPages(self, dataSectors, metadataSectors):
        """Take a list of dataSectors and metadataSectors, and return a list of Pages.
        The Sector positions will be formatted according to the spec - metadata positions random-reproducible.
        """
        self.pages = list()
        mdIterator = 0
        for pageNum in range(self.totalPages):
            pageMetadataSectors = [metadataSectors[0]]

            count = self.metadataPositions[pageNum]
            for i in range(count - 1):
                pageMetadataSectors.append(metadataSectors[mdIterator])
                mdIterator = (mdIterator + 1) % len(metadataSectors)

            for sector in pageMetadataSectors:
                sector.updateMetadata(
                    Metadata.metadataCount,
                    len(pageMetadataSectors))
                sector.updateMetadata(Metadata.pageNumber, pageNum)
                sector.updateMetadata(Metadata.totalPages, self.totalPages)

            dataSectorsCount = self.sectorsVertical * \
                self.sectorsHorizontal - len(pageMetadataSectors)
            pageDataSectors = dataSectors[pageNum *
                                          dataSectorsCount: (pageNum +
                                                             1) *
                                          dataSectorsCount]

            p = PageEncoder(pageDataSectors,
                     pageMetadataSectors,
                     pageNum,
                     self.sectorsVertical,
                     self.sectorsHorizontal,
                     self.colorDepth,
                     self.eccRate,
                     self.sectorHeight,
                     self.sectorWidth)

            self.pages.append(p)

        return self.pages

    def shuffleECCData(self):
        """TODO: Take a list of pages, and shuffle the ECC data in each sector according to the spec - random-reproducible.
        Return pages with shuffled ECC data.
        """
        pass


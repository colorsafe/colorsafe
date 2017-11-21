#!/usr/bin/python

from unireedsolomon.rs import RSCoder, RSCodecError
import binascii
import math
import random
import time

class Constants:
    ByteSize = 8
    Byte00 = 0b00000000
    Byte11 = 0b11111111
    Byte55 = 0b01010101
    ByteAA = 0b10101010

    ColorChannels = 3 # R, G, B, and all secondary combinations
    ColorChannels1 = 1 # Shades of gray only
    ColorChannels2 = 2 # Primary subtractive colors, CMYK
    ColorDepthMax = 2 ** ByteSize - 1
    DataMode = 1
    ECCMode = 1
    MagicByte = 0b10011001
    MagicRowHeight = 1
    MajorVersion = 0
    MinorVersion = 1
    RSBlockSizeMax = 2 ** ByteSize - 1
    RevisionVersion = 0
    TotalPagesMaxBytes = 8 # 8 bytes per page maximum for the total-pages field

class Defaults:
    colorDepth = 1
    eccRate = 0.2

    # All in dots
    sectorHeight = 64
    sectorWidth = 64
    borderSize = 1
    gapSize = 1 # TODO: Consider splitting to left,right,top,bottom to remove 1&2 numbers from various functions

    # An integer representing the number of pixels colored in per dot per side.
    dotFillPixels = 3

    # An integer representing the number of pixels representing a dot per side.
    # Warning: Encoding processing time increases proportionally to this value
    pixelsPerDot = 4

    filename = "out"
    fileExtension = "txt"

def binaryListToVal(l):
    """Takes a list of binary values, return an int corresponding to their value.
    """
    place = 1
    val = 0
    for i in l:
        val += place * i
        place = place << 1
    return val

def binaryListToFloat(l):
    """Takes a list of binary values, returns a float corresponding to their fractional value.
    """
    f = float( binaryListToVal(l) ) / (( 1 << len(l) ) - 1)
    return f

def floatToBinaryList(f, bits):
    """Takes a float f, returns a list of binary values with a length of bits.
    """
    num = int(round(float(f) * ((1 << bits)-1)))

    ret = list()
    for i in range(bits):
        ret.append(num >> i & 1)

    return ret

def intToBinaryList(num, bits):
    """Takes an int, returns a list of its binary number with length bits.
    """
    ret = list()

    for i in range(bits):
        ret.append(num >> i & 1)

    return ret

def lowThreshold(colorDepth):
    return ( 0.5 / ( 1 << colorDepth ) )

def highThreshold(colorDepth):
    return 1 - lowThreshold(colorDepth)

# TODO: Channels and values (colors and shades) should be stored in metadata header separately. Remove notion of 
#       "color".
#       Many values and 1 channel is like a laser-depth engraving. Many channels and 1 value is like atoms.
#       Cmd program can simplify with Grayscale, CYMK, RGB, and higher options.
class ColorChannels:
    """A group of color channels consisting of Red, Green, and Blue values from 0.0 to 1.0.
    """
    RedDefault = 0.0
    GreenDefault = 0.0
    BlueDefault = 0.0

    def __init__(self, red = RedDefault, green = GreenDefault, blue = BlueDefault):
        self.red = red
        self.green = green
        self.blue = blue

    def setChannels(self,channels):
        if len(channels) == Constants.ColorChannels:
            self.red = channels[0]
            self.green = channels[1]
            self.blue = channels[2]
        elif len(channels) == Constants.ColorChannels1:
            self.red = channels[0]
            self.green = channels[0]
            self.blue = channels[0]

    def multiplyShade(self,shades):
        if len(shades) == Constants.ColorChannels:
            self.red *= shades[0]
            self.green *= shades[1]
            self.blue *= shades[2]
        elif len(shades) == Constants.ColorChannels1:
            self.red *= shades[0]
            self.green *= shades[0]
            self.blue *= shades[0]

    def subtractShade(self,shade):
        self.red -= shade
        self.green -= shade
        self.blue -= shade

    def getChannels(self):
        return (self.red, self.green, self.blue)

    def getAverageShade(self):
        return (self.red + self.green + self.blue)/Constants.ColorChannels

class Dot:
    """A group of channels representing a group of colorDepth bits.

    There are three modes of encoding a color into a dot: shade, primary, and secondary.
    """
    def getChannelNum(self, bitCount):
        """Get channel number based on how many bits (based on colorDepth) are needed. Currently, this maps 1:1.
        """
        # TODO: Make these modes options for any colorDepth, add to metadata header.
        if bitCount % Constants.ColorChannels == 0:
            channelNum = Constants.ColorChannels
        elif bitCount % Constants.ColorChannels2 == 0:
            channelNum = Constants.ColorChannels2
        else:
            channelNum = Constants.ColorChannels1

        self.channelNum = channelNum
        return channelNum

    def encodePrimaryMode(self, bitList):
        """Primary mode: Divide list into 2. Each half's first bit represents color, the rest combined represent shade.
        Return color channels. Thus, the shade alone represents (colorDepth-2) bits of information.
        """
        firstHalf = bitList[0:len(bitList)/2]
        secondHalf = bitList[len(bitList)/2:len(bitList)]

        firstHalfFirstBit = firstHalf.pop(0)
        secondHalfFirstBit = secondHalf.pop(0)

        # A terse way to map 2 bits to 4 colors (White, Cyan, Magenta, Yellow)
        index = binaryListToVal([firstHalfFirstBit,secondHalfFirstBit])
        color = [1.0]*(Constants.ColorChannels+1)
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
        bpc = len(bitList)/channelNum # Bits per channel

        for b in range(0, len(bitList), bpc):
            channelBits = bitList[b : b + bpc]
            channelVal = binaryListToFloat(channelBits)
            channelVals.append(channelVal)

        channels = ColorChannels()
        channels.setChannels(channelVals)

        return channels

    def encode(self, bitList):
        """Set values from bitList into channels.
        """
        channelNum = self.getChannelNum(len(bitList))

        if channelNum == Constants.ColorChannels or channelNum == Constants.ColorChannels1:
            channels = self.encodeSecondaryMode(bitList, channelNum)

        if channelNum == Constants.ColorChannels2:
            channels = self.encodePrimaryMode(bitList)

        self.channels = channels
        return self.channels

    def decodePrimaryMode(self, channels, colorDepth):
        bitList = list()

        for channel in channels.getChannels():
            bitList.extend(floatToBinaryList(channel, colorDepth/Constants.ColorChannels))

        return bitList

    def decodeShadeMode(self, channels, colorDepth, thresholdWeight):
        val = channels.getAverageShade()
        val = max(0.0, val - thresholdWeight)
        bitList = floatToBinaryList(val, colorDepth)
        return bitList

    def decodeSecondaryMode(self, channels, colorDepth):
        vals = list()
        zeroPosition = 0
        shadeBits = colorDepth - 2

        # Find the color, e.g. the 0 position, if channel is less than the threshold: half the smallest possible value.
        for i,channel in enumerate(channels.getChannels()):
            if channel < 0.5 / (1 << shadeBits):
                zeroPosition = i + 1
                break

        # These two bits are set by the color itself: 0 -> 00, 1 -> 10, 2 -> 01, 3 -> 11
        firstHalfFirstBit, secondHalfFirstBit = intToBinaryList(zeroPosition, Constants.ColorChannels2)

        # Remove zero position, since it won't contribute to the shade value
        setChannels = list(channels.getChannels())
        if zeroPosition >= 1:
            setChannels.pop(zeroPosition-1)

        # Get average shade value
        valAvg = float(sum(setChannels))/len(setChannels)

        # Get the shade bits, insert the first two color bits at first and halfway positions
        bitList = floatToBinaryList(valAvg, shadeBits)
        bitList.insert(0,firstHalfFirstBit)
        bitList.insert(colorDepth/2,secondHalfFirstBit)

        return bitList

    def decode(self, channels, colorDepth, thresholdWeight):
        """Takes in a list of channels, returns a list of bytes
        """
        channelNum = self.getChannelNum(colorDepth)

        bitList = None

        if channelNum == Constants.ColorChannels:
            bitList = self.decodePrimaryMode(channels, colorDepth)

        if channelNum == Constants.ColorChannels1:
            bitList = self.decodeShadeMode(channels, colorDepth, thresholdWeight)

        if channelNum == Constants.ColorChannels2:
            bitList = self.decodeSecondaryMode(channels, colorDepth)

        self.bitList = bitList
        return bitList

    def getChannels(self):
        return self.channels.getChannels()

class DotByte:
    """A group of 8 Dots, representing colorDepth bytes of data.
    """
    #TODO: Consider a constructor with colorDepth arg, since both functions use it
    #TODO: Encode should return ColorChannels object, not Dot.
    def encode(self, bytesList, colorDepth):
        """Takes in a list of up to colorDepth bytes, returns a list of ByteSize (8) encoded dots.

        For each input byte in bytesList, take the i'th bit and encode into a dot.
        """
        dots = list()
        for i in range(Constants.ByteSize):
            vals = list()

            # Ensure colorDepth bytes are added, even if bytesList doesn't have enough data (0-pad)
            for b in range(colorDepth):
                byte = Constants.Byte00

                if b < len(bytesList):
                    byte = bytesList[b]

                vals.append(byte >> i & 1)

            p = Dot()
            p.encode(vals)
            dots.append(p)

        self.bytesList = bytesList
        self.dots = dots
        return dots

    def decode(self, channelsList, colorDepth, thresholdWeight):
        """Takes in a list of exactly ByteSize (8) channels, returns a list of decoded bytes.

        Sets each dot's decoded data into colorDepth bytes.
        """
        bytesList = list()
        for i in range(colorDepth):
            bytesList.append(Constants.Byte00)

        for i in range(Constants.ByteSize):
            channel = channelsList[i] #If channelsList has less than 8 channel, explicitly fail

            dot = Dot()
            data = dot.decode(channel, colorDepth, thresholdWeight)

            for b in range(colorDepth):
                bytesList[b] = bytesList[b] | data[b] << i

        self.bytesList = bytesList
        return bytesList

class DotRow:
    """A horizontal group of DotBytes.
    """
    @staticmethod
    def getMaxRowBytes(colorDepth, width):
        return colorDepth * width / Constants.ByteSize

    @staticmethod
    def getMagicRowBytes(colorDepth, width):
        maxRowBytes = DotRow.getMaxRowBytes(colorDepth, width)
        return [Constants.MagicByte] * maxRowBytes

    def getXORMask(self, rowNumber):
        return Constants.Byte55 if rowNumber % 2 == 0 else Constants.ByteAA

    def encode(self, bytesList, colorDepth, width, rowNumber, xorRow = True):
        """Takes in a list of bytes, returns a list of encoded dotBytes.

        Performs an XOR on each byte, alternating between AA and 55 per row to prevent rows/columns of 0's or 1's.
        If less bytes are supplied than fit into a row, they will be 0-padded to fill to the end.
        """
        if width % Constants.ByteSize != 0:
            return None

        # TODO: Set AMB metadata parameter instead. Fix this - fails when magic row is intended.
        # If the bytes to be encoded represent the magic row, fail.
        #if bytesList == DotRow.getMagicRowBytes(colorDepth, width):
        #    return None

        maxRowBytes = self.getMaxRowBytes(colorDepth, width)
        mask = self.getXORMask(rowNumber)

        dotBytes = list()
        for inByte in range(0, maxRowBytes, colorDepth):
            bl = bytesList[inByte : inByte + colorDepth] 

            if len(bl) < colorDepth:
                bl.extend( [Constants.Byte00] * (colorDepth - len(bl)) )

            blTemp = list()
            for b in bl:
                # Valid bytesList inputs are strings (e.g. read from a file) or ints (e.g. metadata header constants).
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

            db = DotByte()
            db.encode(blTemp, colorDepth)
            dotBytes.append(db)

        self.dotBytes = dotBytes
        return dotBytes

    def decode(self, channelsList, colorDepth, width, rowNumber, thresholdWeight, xorRow = True):
        """Takes in a list of width channels, returns a list of decoded bytes
        """
        if width % Constants.ByteSize != 0:
            return None

        mask = self.getXORMask(rowNumber)

        bytesList = list()
        for w in range(0, width, Constants.ByteSize):
            channels = channelsList[w : w + Constants.ByteSize]
            db = DotByte()
            data = db.decode(channels, colorDepth, thresholdWeight)
            bytesList.extend(data)

        for i,byte in enumerate(bytesList):
            if xorRow:
                bytesList[i] = bytesList[i] ^ mask
            else:
                bytesList[i] = bytesList[i]

        self.bytesList = bytesList
        return bytesList

class Sector:
    """A vertical group of DotRows.
    """
    @staticmethod
    def getDataRowCount(height, eccRate):
        return int ( math.floor( ( height - Constants.MagicRowHeight ) / ( 1 + eccRate ) ) )

    def encode(self, data, colorDepth, height, width, eccRate, dataStart = 0):
        """Takes in a list of bytes, returns a list of dotRows
        """
        self.height = height
        self.width = width
        self.colorDepth = colorDepth
        self.eccRate = eccRate
        self.data = data

        self.getBlockSizes()
        self.putData(dataStart)
        self.putECCData(dataStart)

    def decode(self, channelsList, colorDepth, height, width, dataRowCount, eccRate, thresholdWeight):
        """Takes in a list of height*width channels, returns a list of decoded data/ecc bytes
        """
        dataRows = list()
        eccRows = list()

        # TODO: No self, remove this
        self.height = height
        self.width = width
        self.colorDepth = colorDepth
        self.eccRate = eccRate
        self.getBlockSizes()

        for row in range(0, height*width, width):
            channels = channelsList[row : row + width]
            dotRow = DotRow()
            rowNum = row/width
            bytesList = dotRow.decode(channels, colorDepth, width, rowNum, thresholdWeight)

            if row < dataRowCount * width:
                dataRows.extend(bytesList)

            # Ignore magic row
            if row > dataRowCount * width:
                eccRows.extend(bytesList)

        self.dataRows = dataRows
        self.eccRows = eccRows
        return dataRows, eccRows

    def getBlockSizes(self):
        self.rsBlockSizes = list()
        self.dataBlockSizes = list()
        self.eccBlockSizes = list()

        self.dataRowCount = Sector.getDataRowCount(self.height, self.eccRate)
        self.eccRowCount = self.height - Constants.MagicRowHeight - self.dataRowCount

        totalBytes = ( self.height - 1 ) * self.width * self.colorDepth / Constants.ByteSize

        if totalBytes <= Constants.RSBlockSizeMax:
            self.rsBlockSizes.append(totalBytes)
        else:
            self.rsBlockSizes = [ Constants.RSBlockSizeMax ] * (totalBytes/Constants.RSBlockSizeMax)

            if totalBytes % Constants.RSBlockSizeMax != 0:
                self.rsBlockSizes.append( totalBytes % Constants.RSBlockSizeMax )

                lastVal = int( math.floor( ( self.rsBlockSizes[-1] + self.rsBlockSizes[-2] ) / 2.0 ) )
                secondLastVal = int ( math.ceil( ( self.rsBlockSizes[-1] + self.rsBlockSizes[-2] ) / 2.0 ) )

                self.rsBlockSizes[-1] = lastVal
                self.rsBlockSizes[-2] = secondLastVal

        for size in self.rsBlockSizes:
            dataRowPercentage = float(self.dataRowCount) / ( self.height - Constants.MagicRowHeight )
            eccRowPercentage = float(self.eccRowCount) / ( self.height - Constants.MagicRowHeight )

            self.dataBlockSizes.append( int ( math.floor( size * dataRowPercentage ) ) )
            self.eccBlockSizes.append( int ( math.ceil( size * eccRowPercentage ) ) )

    def putData(self, dataStart = 0):
        """Takes in a list of data, returns a list of dataRows
        """
        self.dataRows = list()
        bytesPerRow = self.width * self.colorDepth / Constants.ByteSize

        for row in range(self.dataRowCount):
            minIndex = dataStart + row * bytesPerRow
            maxIndex = dataStart + ((row + 1) * bytesPerRow)

            insertData = self.data[ minIndex : maxIndex ]
            insertRow = DotRow()
            insertRow.encode( list(insertData), self.colorDepth, self.width, row )
            self.dataRows.append(insertRow)

    def putECCData(self, dataStart = 0):
        eccData = list()

        totalBytes = ( self.height - 1 ) * self.width / Constants.ByteSize
        for i,rsBlockLength in enumerate(self.rsBlockSizes):
            messageLength = self.dataBlockSizes[i]
            errorLength = self.eccBlockSizes[i]
            rsEncoder = RSCoder(rsBlockLength, messageLength)

            minIndex = dataStart + sum(self.dataBlockSizes[:i])
            maxIndex = dataStart + sum(self.dataBlockSizes[:i+1])

            dataBlock = list(self.data[ minIndex : maxIndex ])
            if len(dataBlock) < messageLength:
                dataBlock.extend([chr(Constants.Byte00)] * (messageLength - len(dataBlock)))
            dbTemp = ""
            for c in dataBlock:
                try:
                    dbTemp += c
                except TypeError:
                    dbTemp += chr(c)

            rsBlock = rsEncoder.encode(dbTemp)
            eccBlock = [ord(j) for j in rsBlock[-errorLength:]]

            eccData.extend(eccBlock)

        eccMagicRow = DotRow()
        eccMagicRow.encode(DotRow.getMagicRowBytes(self.colorDepth, self.width), self.colorDepth, self.width, \
            self.dataRowCount)

        self.eccRows = [ eccMagicRow ]
        bytesPerRow = self.width * self.colorDepth / Constants.ByteSize
        for row in range(self.eccRowCount):
            insertData = eccData[ row * bytesPerRow : (row + 1) * bytesPerRow ]
            insertRow = DotRow()
            insertRow.encode( insertData, self.colorDepth, self.width, row )
            self.eccRows.append(insertRow)

    # For ECC swapping in CS file, to distribute across pages
    def getECCbit(self, i):
        pass

    def putECCbit(self, i):
        pass

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

    # TODO: Tuples?
    # Required, in order
    RequiredInOrder = [eccMode, dataMode, pageNumber, metadataCount]

    # Required, in no order
    # TODO: Some of these should possibly be required on each page
    RequiredNoOrder = [ambiguous, crc32CCheck, eccRate, majorVersion, minorVersion, revisionVersion, fileSize, \
        csCreationTime, totalPages, fileExtension, filename]

    # TODO: Filename/ext not required, how to track?

class MetadataSector(Sector):
    MetadataInitPaddingBytes = 1
    ColorDepthBytes = 1
    MetadataSchemeBytes = 3
    MetadataEndPaddingBytes = 1
    MetadataDefaultScheme = 1

    #m = MetadataSector(32,32,3,0.2,{"k":"v"})
    def __init__(self, height, width, colorDepth, eccRate, metadata):
        self.height = height
        self.width = width
        self.colorDepth = colorDepth
        self.eccRate = eccRate
        self.dataStart = 0 #TODO: Make this an argument for putdata, not a self object

        self.getBlockSizes()
        self.putMetadata(metadata)
        self.putData()
        self.putECCData()

    #TODO: This only supports values less than 256. It XOR's inelegantly. Fix it, add non-xor method to DotByte?
    def getMetadataSchemeBytes(self):
        ret = [self.MetadataDefaultScheme ^ Constants.Byte55]*self.colorDepth
        ret += [Constants.Byte55]*self.colorDepth*(self.MetadataSchemeBytes-1)
        return ret

    def getColorDepthBytes(self):
        return [self.colorDepth ^ Constants.Byte55]*self.colorDepth

    def putMetadata(self, metadata):
        self.metadata = dict()

        # Format header
        self.data = DotRow.getMagicRowBytes(self.colorDepth, self.width)

        # Multiply each by self.colorDepth to make these effectively black and white
        # TODO: Header 11110000/00001111 instead of 11111111 - less likely to collide/smudge first/last bit.
        self.data.extend([Constants.ByteAA]*self.MetadataInitPaddingBytes*self.colorDepth)
        self.data.extend(self.getColorDepthBytes())
        self.data.extend(self.getMetadataSchemeBytes())
        self.data.extend([Constants.ByteAA]*self.MetadataEndPaddingBytes*self.colorDepth)

        # Format metadata, interleave lists and 0-byte join
        # TODO: Encode ints not in ascii
        for (key, value) in metadata.items():
            kvString = str(key) + chr(Constants.Byte00) + (str(value) if value else "") + chr(Constants.Byte00)

            #TODO: Get from static method?
            maxDataPerSector = Sector.getDataRowCount(self.height, self.eccRate) * self.width * self.colorDepth
            if len(kvString) + len(self.data) < maxDataPerSector:
                self.data.extend([ord(i) for i in kvString])
                self.metadata[key] = value

        return self.metadata

    def getMetadata(self):
        """Decode all metadata from the encoded metadata string
        """
        pass

    def updateMetadata(self, key, value):
        """Update the value by rewriting all metadata.
        Used when value is known after all data and metadata is encoded, or is unwieldy to calculate before.
        Updated value should be less than the originally written one, or else metadata could drop existing data.
        """
        self.metadata[key] = value
        self.putMetadata(self.metadata)

class Page:
    """A collection of sectors, used for shuffling and placing them correctly on each page, and for keeping track of
    page specific properties, like page number.
    """
    def encode(self,
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

    def decode(self,
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
            s = Sector()
            s.decode(channelsList, colorDepth, sectorHeight, sectorWidth, dataRows, thresholdWeight)
            sectors.add(s)

        self.sectors = sectors

    def putMetadataSectors(self):
        """Put all metadata sectors into this page, using method from the spec: random-reproducible
        """
        self.sectors = [None] * (len(self.dataSectors) + len(self.metadataSectors))

        random.seed(self.pageNumber)
        allMetadataPagePositions = range(0, len(self.sectors))
        random.shuffle(allMetadataPagePositions)
        self.metadataSectorsPositions = allMetadataPagePositions[ : len(self.metadataSectors) ]

        metadataSectorIndex = 0
        for i in self.metadataSectorsPositions:
            self.sectors[i] = self.metadataSectors[metadataSectorIndex]
            metadataSectorIndex += 1

    def getMetadataSectors(self):
        """Get all metadata sectors in this page, using method from the spec: random-reproducible
        """
        pass

    def putDataSectors(self):
        """Put all data sectors into this page, around all metadata sectors
        """
        self.dataSectorCount = (self.sectorsVertical*self.sectorsHorizontal)-len(self.metadataSectors)
        dataSectorIndex = 0
        for sectorIndex,sector in enumerate(self.sectors):
            if sector == None:
                self.sectors[sectorIndex] = self.dataSectors[dataSectorIndex]
                dataSectorIndex += 1

    def getDataSectors(self):
        """Get all data sectors in this page - all non-metadata sectors
        """
        pass

# The ColorSafe data and borders, all dimensions in dots.
class ColorSafeFile:

    def encode(self,
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

        self.dataRowCount = Sector.getDataRowCount(self.sectorHeight, self.eccRate)

        self.putDataSectors(self.data)
        self.maxData = self.dataPerSector * self.sectorsVertical * self.sectorsHorizontal #TODO: Unused, add in header
        self.createMetadataSectors()
        self.sectorsToPages(self.dataSectors, self.metadataSectors)

    def decode(self, pages):
        """Take a list of channels, format into sectors, then set a list of pages into this object

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

    def putDataSectors(self, data):
        """Take data and place it into a list of Sectors, bucketing as much data as possible into each one.
        """
        self.dataSectors = list()

        self.dataPerSector = self.sectorWidth * self.colorDepth * self.dataRowCount / Constants.ByteSize

        for dataStart in range(0,len(self.data),self.dataPerSector):
            # TODO: Setting data into Sector in place (using Sector's dataStart argument) may improve performance
            data = self.data[dataStart: dataStart + self.dataPerSector]

            s = Sector()
            s.encode(data, self.colorDepth, self.sectorHeight, self.sectorWidth, self.eccRate)

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

        fileSize = len(self.data) # In bytes

        self.metadata[Metadata.crc32CCheck] = crc32CCheck
        self.metadata[Metadata.csCreationTime] = csCreationTime
        self.metadata[Metadata.dataMode] = Constants.DataMode
        self.metadata[Metadata.eccMode] = Constants.ECCMode
        self.metadata[Metadata.eccRate] = self.eccRate
        self.metadata[Metadata.fileExtension] = self.fileExtension
        self.metadata[Metadata.fileSize] = fileSize
        self.metadata[Metadata.filename] = self.filename
        self.metadata[Metadata.majorVersion] = Constants.MajorVersion
        self.metadata[Metadata.minorVersion] = Constants.MinorVersion
        self.metadata[Metadata.revisionVersion] = Constants.RevisionVersion

        # This should not cause extra 0's in value; it will be updated with correct values before writing
        self.metadata[Metadata.pageNumber] = chr(0) * Constants.TotalPagesMaxBytes
        self.metadata[Metadata.totalPages] = chr(0) * Constants.TotalPagesMaxBytes

        # Set to maximum possible. This will be updated with correct values before writing.
        self.metadata[Metadata.metadataCount] = self.sectorsVertical * self.sectorsHorizontal 

        # Reverse sort metadata that has no required order
        metadataRequiredNoOrderKeys = set([key for (key, value) in self.metadata.items()]) - \
            set(Metadata.RequiredInOrder)
        metadataRequiredNoOrder = [(key, self.metadata[key]) for key in metadataRequiredNoOrderKeys]
        metadataRequiredNoOrder.sort(key = lambda tup: -len(str(tup)))
        metadataRequiredNoOrder = [key for (key, value) in metadataRequiredNoOrder]

        metadataInsertOrdered = Metadata.RequiredInOrder + metadataRequiredNoOrder

        metadataRemaining = metadataInsertOrdered
        while metadataRemaining != Metadata.RequiredInOrder:
            metadataToInsert = dict()
            for key in metadataRemaining:
                metadataToInsert[key] = self.metadata[key]

            mdSector = MetadataSector(self.sectorHeight, self.sectorWidth, self.colorDepth, self.eccRate, \
                metadataToInsert)

            metadataInserted = mdSector.metadata

            # If required in order metadata not inserted, break; nothing else will fit anyways
            breakLoop = False
            for md in Metadata.RequiredInOrder:
                if md not in metadataInserted:
                    breakLoop = True
                    break
            if breakLoop:
                break

            # If nothing additional after required metadata, remove first (largest) non-ordered metadata kv pair
            if metadataInserted == Metadata.RequiredInOrder:
                metadataRemaining.pop(len(Metadata.RequiredInOrder))
                continue

            self.metadataSectors.append(mdSector)

            metadataRemaining = list(set(metadataRemaining) - set(metadataInserted))

        self.sectorsPerPage = self.sectorsVertical * self.sectorsHorizontal

        dsCount = len(self.dataSectors)
        msCount = len(self.metadataSectors)

        # The following equations are derived from the combination of two dependent equations:
        # 1. The number of metadata sectors is equal to the first one on each page, plus the rest
        # 2. Number of pages is the ceiling of data sector + metadata sector count divided by sectors per page.
        # It is valid only for m+d>1, so use max(equation,1) to ensure it always returns one or more pages.
        totalPages = max( int( math.ceil( float(dsCount + msCount - 1) / (self.sectorsPerPage - 1) ) ), 1)
        totalMetadataSectors = totalPages + msCount - 1

        self.totalSectors = dsCount + totalMetadataSectors

        paddingMetadataSectors = self.sectorsHorizontal - (self.totalSectors % self.sectorsHorizontal)
        self.totalSectors += paddingMetadataSectors
        totalMetadataSectors += paddingMetadataSectors

        # Get metadataPositions dict: { pageNum: metadataSectorsOnPage, ... }
        metadataPositions = range(totalPages)
        random.seed(0)
        random.shuffle(metadataPositions)
        metadataPositions = metadataPositions * int( math.ceil(totalMetadataSectors/totalPages) )
        metadataPositions = metadataPositions[:totalMetadataSectors]
        metadataPositions = { i : metadataPositions.count(i) for i in metadataPositions }

        self.totalPages = totalPages
        self.totalMetadataSectors = totalMetadataSectors
        self.metadataPositions = metadataPositions

    def metadataSectorsToMetadata(self):
        """Take a list of metadataSectors, get their metadata, and combine them into a single Metadata object
        """
        pass

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
                sector.updateMetadata(Metadata.metadataCount, len(pageMetadataSectors))
                sector.updateMetadata(Metadata.pageNumber, pageNum)
                sector.updateMetadata(Metadata.totalPages, self.totalPages)

            dataSectorsCount = self.sectorsVertical * self.sectorsHorizontal - len(pageMetadataSectors)
            pageDataSectors = dataSectors[pageNum*dataSectorsCount : (pageNum+1)*dataSectorsCount]

            p = Page()
            p.encode(pageDataSectors,
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

    def pagesToMetadataSectors(self, pages):
        """Take a list of pages and return a list of all metadataSectors.
        Get the random-reproducible inserted order of metadata, add each into a list in order.
        """
        pass

    def pagesToDataSectors(self, pages):
        """Take a list of pages and return the positions of dataSectors and metadataSectors.
        Place all sectors that aren't metadata sequentially into a list
        """
        pass

    def shuffleECCData(self):
        """Take a list of pages, and shuffle the ECC data in each sector according to the spec - random-reproducible.
        Return pages with shuffled ECC data.
        """
        pass

    def deshuffleECCData(self):
        """Take a list of pages, and de-shuffle the ECC data in each sector according to the spec - random-reproducible.
        This will return a list of pages with the original ECC data positions.
        """
        pass

class ColorSafeImageFiles:
    """A collection of saved ColorSafeFile objects, as images of working regions without outside borders or headers
    """
    # TODO: Black and white constants in ColorChannels
    BorderColor = (0,0,0)

    def encode(self,
               data,
               fullWorkingHeightPixels,
               fullWorkingWidthPixels,
               dotFillPixels = Defaults.dotFillPixels,
               pixelsPerDot = Defaults.pixelsPerDot,
               colorDepth = Defaults.colorDepth,
               eccRate = Defaults.eccRate,
               sectorHeight = Defaults.sectorHeight,
               sectorWidth = Defaults.sectorWidth,
               borderSize = Defaults.borderSize,
               gapSize = Defaults.gapSize,
               filename = Defaults.filename,
               fileExtension = Defaults.fileExtension):
        """Convert ColorSafeFile into a list of formatted images, with borders and gaps, and scaled properly.
        """

        if not colorDepth or colorDepth < 0 or colorDepth > Constants.ColorDepthMax:
            colorDepth = Defaults.colorDepth

        if dotFillPixels < 0:
            dotFillPixels = Defaults.dotFillPixels

        if pixelsPerDot < 0:
            pixelsPerDot = Defaults.pixelsPerDot

        self.fullWorkingHeightPixels = fullWorkingHeightPixels
        self.fullWorkingWidthPixels = fullWorkingWidthPixels
        self.dotFillPixels = dotFillPixels
        self.pixelsPerDot = pixelsPerDot
        self.colorDepth = colorDepth
        self.eccRate = eccRate
        self.sectorHeight = sectorHeight
        self.sectorWidth = sectorWidth
        self.borderSize = borderSize
        self.gapSize = gapSize
        self.filename = filename
        self.fileExtension = fileExtension

        # Calculate sector count based on maximum allowable in working region
        self.scale = self.pixelsPerDot

        # An integer representing the number of non-colored pixels representing a dot for respective sides.
        dotWhitespace = self.pixelsPerDot - self.dotFillPixels
        self.dotWhitespaceTop = int(math.floor(float(dotWhitespace)/2))
        self.dotWhitespaceBottom = int(math.ceil(float(dotWhitespace)/2))
        self.dotWhitespaceLeft = int(math.floor(float(dotWhitespace)/2))
        self.dotWhitespaceRight = int(math.ceil(float(dotWhitespace)/2))

        # In dots, excluding overlapping borders
        self.sectorHeightTotal = self.sectorHeight + self.borderSize + 2 * self.gapSize
        self.sectorWidthTotal = self.sectorWidth + self.borderSize + 2 * self.gapSize

        # Remove single extra non-overlapping border at the bottom-right of working region
        self.sectorsVertical = float(self.fullWorkingHeightPixels - self.scale*self.borderSize)
        self.sectorsVertical /= self.scale*self.sectorHeightTotal

        self.sectorsHorizontal = float(self.fullWorkingWidthPixels - self.scale*self.borderSize)
        self.sectorsHorizontal /= self.scale*self.sectorWidthTotal

        self.sectorsVertical = int ( math.floor(self.sectorsVertical) )
        self.sectorsHorizontal = int ( math.floor(self.sectorsHorizontal) )

        self.workingHeightPixels = (self.sectorsVertical * self.sectorHeightTotal + self.borderSize) * self.scale
        self.workingWidthPixels = (self.sectorsHorizontal * self.sectorWidthTotal + self.borderSize) * self.scale

        self.csFile = ColorSafeFile()
        self.csFile.encode(data,
                           self.sectorsVertical,
                           self.sectorsHorizontal,
                           self.colorDepth,
                           self.eccRate,
                           self.sectorHeight,
                           self.sectorWidth,
                           self.filename,
                           self.fileExtension)

        self.colorSafeFileToImages(self.csFile)

    def decode(self, channelsPagesList, colorDepth):
        """Convert a list of pages channels into a list of sector channels, create decoded sectors, return data.
        Remove borders and gaps, scale down.

        Pages channels is a list (size totalPages) of lists (size workingHeight) of rows (list size workingWidth) of
        channels.
        """
        # TODO: Need to shear image for x and y, not just rotate
        if not colorDepth or colorDepth < 0 or colorDepth > Constants.ColorDepthMax:
            colorDepth = Defaults.colorDepth

        # Put each sector's data into a cleaned channelsList, 1 set of channels per dot
        dataStr = ""
        eccStr = ""
        metadataStr = ""

        for page in channelsPagesList:
            # Get vertical sector bounds
            verChannelShadeAvg = list()
            for row in page:
                channelShadeSum = 0
                for channel in row:
                    channelShadeSum += channel.getAverageShade()
                verChannelShadeAvg.append(channelShadeSum/len(row))

            verticalBounds = self.findBounds(verChannelShadeAvg)

            # Get horizontal sector bounds
            horChannelShadeAvg = list()
            for i in range(len(page[0])):
                channelShadeSum = 0
                for row in page:
                    channelShadeSum += row[i].getAverageShade()
                horChannelShadeAvg.append(channelShadeSum/len(page))

            horizontalBounds = self.findBounds(horChannelShadeAvg)

            sectorsVertical = len(verticalBounds)
            sectorsHorizontal = len(horizontalBounds)

            # Move to this function's arguments
            sectorHeight = Defaults.sectorHeight
            sectorWidth = Defaults.sectorWidth
            gapSize = Defaults.gapSize
            borderSize = Defaults.borderSize
            eccRate = Defaults.eccRate

            sectorNum = -1

            # For each sector, beginning and ending at its gaps
            for topTemp, bottomTemp in verticalBounds:
                for leftTemp, rightTemp in horizontalBounds:
                    sectorNum += 1
                    # Use page-average to calculate height/width, works better for small sector sizes
                    # Rotation should even out on average
                    heightPerDot = float(bottomTemp - topTemp + 1) / (sectorHeight + 2 * gapSize)
                    widthPerDot = float(rightTemp - leftTemp + 1) / (sectorWidth + 2 * gapSize)

                    # TODO: Combine into one function
                    # Find real gaps, since small rotation across a large page may distort this.
                    # Look within one-dot unit of pixels away
                    bottommostTop = topTemp + int(round(heightPerDot))
                    topmostTop = topTemp - int(round(heightPerDot))
                    bottommostBottom = bottomTemp + int(round(heightPerDot))
                    topmostBottom = bottomTemp - int(round(heightPerDot))
                    rightmostLeft = leftTemp + int(round(widthPerDot))
                    leftmostLeft = leftTemp - int(round(widthPerDot))
                    rightmostRight = rightTemp + int(round(widthPerDot))
                    leftmostRight = rightTemp - int(round(widthPerDot))

                    top = topTemp
                    bottom = bottomTemp
                    left = leftTemp
                    right = rightTemp

                    gapThreshold = 0.75 # TODO: Possibly needs to be bigger

                    # Find top, going from border to gap (top to bottom)
                    for y in range(topmostTop+1, bottommostTop+1):
                        rowShadeSum = 0.0
                        for x in range(rightmostLeft, leftmostRight+1):
                            rowShadeSum += page[y][x].getAverageShade()
                        rowShadeSum /= (leftmostRight - rightmostLeft)
                        if rowShadeSum > gapThreshold:
                            top = y
                            break

                    # Find bottom, going from border to gap (bottom to top)
                    for y in range(topmostBottom+1, bottommostBottom+1)[::-1]:
                        rowShadeSum = 0.0
                        for x in range(rightmostLeft, leftmostRight+1):
                            rowShadeSum += page[y][x].getAverageShade()
                        rowShadeSum /= (leftmostRight - rightmostLeft)
                        if rowShadeSum > gapThreshold:
                            bottom = y
                            break

                    # Find left, going from border to gap (left to right)
                    for x in range(leftmostLeft+1, rightmostLeft+1):
                        rowShadeSum = 0.0
                        for y in range(bottommostTop, topmostBottom+1):
                            rowShadeSum += page[y][x].getAverageShade()
                        rowShadeSum /= (topmostBottom - bottommostTop)
                        if rowShadeSum > gapThreshold:
                            left = x
                            break

                    # Find right, going from border to gap (right to left)
                    for x in range(leftmostRight+1, rightmostRight+1)[::-1]:
                        rowShadeSum = 0.0
                        for y in range(bottommostTop, topmostBottom+1):
                            rowShadeSum += page[y][x].getAverageShade()
                        rowShadeSum /= (topmostBottom - bottommostTop)
                        if rowShadeSum > gapThreshold:
                            right = x
                            break

                    # For all pixels in sector, mark and sum boundary changes for all rows and columns
                    shadesPerChannel = 2
                    boundaryThreshold = 0.8 # TODO: Generalize to multiple shades

                    rowsBoundaryChanges = list()
                    for x in range(left + 1, right + 1):
                        allRowBoundaryChanges = 0
                        for y in range(top, bottom + 1):
                            current = page[y][x].getChannels()
                            previous = page[y][x - 1].getChannels()

                            for i in range(len(current)):
                                bucketCurrent = (0 if current[i] < boundaryThreshold else 1)
                                bucketPrevious = (0 if previous[i] < boundaryThreshold else 1)
                                # Get white to black only, seems to be more consistent
                                if bucketCurrent != bucketPrevious and bucketCurrent == 0:
                                    allRowBoundaryChanges += 1

                        rowsBoundaryChanges.append(allRowBoundaryChanges)

                    columnsBoundaryChanges = list()
                    for y in range(top + 1, bottom + 1):
                        allColumnBoundaryChanges = 0
                        for x in range(left, right + 1):
                            current = page[y][x].getChannels()
                            previous = page[y - 1][x].getChannels()

                            for i in range(len(current)):
                                bucketCurrent = (0 if current[i] < boundaryThreshold else 1)
                                bucketPrevious = (0 if previous[i] < boundaryThreshold else 1)
                                # Get white to black only, seems to be more consistent
                                if bucketCurrent != bucketPrevious and bucketCurrent == 0:
                                    allColumnBoundaryChanges += 1

                        columnsBoundaryChanges.append(allColumnBoundaryChanges)

                    # Find the most likely dot start locations, TODO: Combine into one function
                    avgPixelsWidth = int(round(widthPerDot))
                    minPixelsWidth = max(avgPixelsWidth - 1, 1)
                    maxPixelsWidth = max(avgPixelsWidth + 1, 2) # TODO: Max 2 correct? Forces scan to be 2x resolution...

                    rowDotStartLocations = list()
                    currentLocation = 0
                    for i in range(sectorWidth):
                        # TODO: Account for the gap, find initial data start
                        mnw = minPixelsWidth if i else 0
                        possible = rowsBoundaryChanges[currentLocation + mnw : currentLocation + maxPixelsWidth + (1 if i else 0)]
                        if possible:
                            index = possible.index(max(possible))
                        else:
                            index = 0
                        currentLocation += index + mnw
                        rowDotStartLocations.append(currentLocation)

                    # For ending, add average width to the end so that dot padding/fill is correct
                    rowDotStartLocations.append(rowDotStartLocations[-1] + avgPixelsWidth)

                    columnDotStartLocations = list()
                    currentLocation = 0
                    for i in range(sectorHeight):
                        # TODO: Account for the gap, find initial data start
                        mnw = minPixelsWidth if i else 0
                        possible = columnsBoundaryChanges[currentLocation + mnw : currentLocation + maxPixelsWidth + (1 if i else 0)]
                        if possible:
                            index = possible.index(max(possible))
                        else:
                            index = 0
                        currentLocation += index + mnw
                        columnDotStartLocations.append(currentLocation)

                    # For ending, add average width to the end so that dot padding/fill is correct
                    columnDotStartLocations.append(columnDotStartLocations[-1] + avgPixelsWidth)

                    #perc = str(int(100.0 * sectorNum / (sectorsHorizontal*sectorsVertical))) + "%"

                    minVals = [1.0, 1.0, 1.0]
                    maxVals = [0.0, 0.0, 0.0]
                    shadeBuckets = list()
                    BucketNum = 20 # TODO: Calculate dynamically?
                    for i in range(BucketNum):
                        shadeBuckets.append(0)
                        
                    # For each dot in the sector
                    channelsList = list()
                    for y in range(sectorHeight):
                        for x in range(sectorWidth):
                            pixelsTop = columnDotStartLocations[y] + top + 1
                            pixelsBottom = columnDotStartLocations[y + 1] + top + 1
                            pixelsLeft = rowDotStartLocations[x] + left + 1
                            pixelsRight = rowDotStartLocations[x + 1] + left + 1

                            # For each set of pixels corresponding to a dot
                            dotPixels = list()
                            for yPixel in range(pixelsTop, pixelsBottom):
                                for xPixel in range(pixelsLeft, pixelsRight):
                                    pixel = page[yPixel][xPixel]

                                    dotPixels.append(pixel)

                            # Average all pixels in the list, set into new ColorChannel
                            R,G,B = 0,0,0 # TODO: Generalize to channels, place in ColorChannels
                            for dotPixel in dotPixels:
                                R1,G1,B1 = dotPixel.getChannels()
                                R+=R1
                                G+=G1
                                B+=B1

                            R/=len(dotPixels)
                            G/=len(dotPixels)
                            B/=len(dotPixels)
                            c = ColorChannels(R,G,B)

                            channelsList.append(c)

                            # Get min and max vals for normalization
                            vals = c.getChannels()
                            for i,val in enumerate(vals):
                                if val < minVals[i]:
                                    minVals[i] = val
                                if val > maxVals[i]:
                                    maxVals[i] = val

                            bucketNum = int(c.getAverageShade()*BucketNum) - 1
                            shadeBuckets[bucketNum] += 1

                    for i,channels in enumerate(channelsList):
                        minVal = sum(minVals)/len(minVals)
                        maxVal = sum(maxVals)/len(maxVals)
                        channels.subtractShade(minVal)
                        channels.multiplyShade([1.0/(maxVal-minVal)])

                    # Get shade maxima locations, starting from each side
                    shadeMaximaLeft = 0
                    for i in range(1, BucketNum):
                        if shadeBuckets[i] < shadeBuckets[i-1]:
                            shadeMaximaLeft = i-1
                            break

                    shadeMaximaRight = BucketNum
                    for i in range(1, BucketNum)[::-1]:
                        if shadeBuckets[i] > shadeBuckets[i-1]:
                            shadeMaximaRight = i
                            break

                    # Get shade minima between maxima
                    shadeMinima = 5
                    for i in range(shadeMaximaLeft + 1, shadeMaximaRight):
                        if shadeBuckets[i] < shadeBuckets[i-1] and shadeBuckets[i] < shadeBuckets[i+1]:
                            shadeMinima = i
                            break

                    s = Sector()
                    dataRows = Sector.getDataRowCount(sectorHeight, eccRate)
                    DefaultThresholdWeight = 0.5 # TODO: Move to Constants, or ColorChannels
                    thresholdWeight = float(shadeMinima) / BucketNum - DefaultThresholdWeight
                    s.decode(channelsList, colorDepth, sectorHeight, sectorWidth, dataRows, eccRate, thresholdWeight)

                    outData = "".join([chr(i) for i in s.dataRows])
                    eccData = "".join([chr(i) for i in s.eccRows])

                    # Perform error correction, return uncorrected RS block on failure
                    # TODO: Recognize error data separately from normal data, to improve accuracy
                    correctedData = ""
                    dindex = 0
                    eindex = 0
                    for i,dbs in enumerate(s.dataBlockSizes):
                        ebs = s.eccBlockSizes[i]
                        uncorrectedStr = outData[dindex:dindex+dbs] + eccData[eindex:eindex+ebs]
                        rsEncoder = RSCoder(dbs+ebs, dbs)

                        try:
                            correctedStr = rsEncoder.decode(uncorrectedStr)[0]
                        except RSCodecError:
                            correctedStr = outData[dindex:dindex+dbs]

                        correctedData += correctedStr
                    
                        dindex += dbs
                        eindex += ebs

                    outData = correctedData

                    # Add data to output if sector is not metadata
                    magicRow = DotRow.getMagicRowBytes(colorDepth, sectorWidth)
                    if s.dataRows[:len(magicRow)] != magicRow:
                        dataStr += outData
                        eccStr += eccData
                    else:
                        metadataStr += outData + "\n\n"

        # TODO: Need to place sectors in Page objects, then each page in a CSFile, then call CSFile.decode()

        dataStr = dataStr.rstrip(chr(0))

        return dataStr, metadataStr

    #TODO: Consider moving this logic to a new ChannelsGrid object
    def findBounds(self, l):
        """Given a 1D black and white grid matrix (one axis of a 2D grid matrix) return a list of beginnings and ends.
        A beginning is the first whitespace (gap) after any black border, and an end is the last whitespace (gap)
        before the next black border.

        Use whitespace after borders rather than searching for the data within each border, since the
        data may be empty or inconsistent. Borders are the most reliable unit of recognition.
        """
        minLengthSector = 10 #TODO: Set to sectorWidth/sectorHeight

        lowBorderThreshold = 0.35
        highGapThreshold = 0.65

        minVal = min(l)
        maxVal = max(l)

        ending = -1
        beginning = -1

        begins = list()
        ends = list()

        # Find ending
        y = len(l)
        for i in l[::-1]:
            y -= 1

            val = (i-minVal)/(maxVal-minVal) # normalize

            if ending == -1:
                if val < lowBorderThreshold:
                    ending = y
                    break

        if ending == -1:
            # Ending not found
            return None

        # Find beginning and all begins/ends
        y = -1
        for ll in range(0,len(l)):
            y += 1

            val = (l[ll]-minVal)/(maxVal-minVal) # normalize
            prevVal = (l[ll-1]-minVal)/(maxVal-minVal) # normalize
            prev2Val = (l[ll-2]-minVal)/(maxVal-minVal) # normalize

            if y >= ending:
                break

            if beginning == -1:
                if val < lowBorderThreshold:
                    beginning = y
                    continue

            # Begins and ends matched, looking for new begin
            if len(begins) == len(ends):
                # Boundary where black turns white
                if val > highGapThreshold and (prevVal < lowBorderThreshold or prev2Val < lowBorderThreshold):
                    begins.append(y)
                    continue

            # More begins than ends, looking for new bottom
            if len(ends) < len(begins):
                # Boundary where white turns black
                if (prevVal > highGapThreshold or prev2Val > highGapThreshold) and \
                   val < lowBorderThreshold and \
                   y >= begins[-1] + minLengthSector:

                    ends.append(y-1)
                    continue

        if beginning == -1:
            # Beginning not found.
            return None

        if len(begins) != len(ends):
            # Begins and ends uneven, attempting correction

            # Attempt correction
            if len(begins) < len(ends):
                ends = ends[0:len(begins)]
            else:
                begins = begins[0:len(ends)]

        bounds = list()
        for i in range(0, len(begins)):
            bounds.append((begins[i], ends[i]))

        return bounds

    def colorSafeFileToImages(self, csFile):
        self.images = list()

        for page in csFile.pages:
            pixels = list()
            for row in range(self.workingHeightPixels):
                row = list()
                for column in range(self.workingWidthPixels):
                    row.append((255,255,255))
                pixels.append(row)

            for si,sector in enumerate(page.sectors):
                sx = si % page.sectorsHorizontal
                sy = si / page.sectorsHorizontal

                gapHor = self.gapSize*(2*sx+1)
                borderHor = self.borderSize*(sx+1)

                gapVer = self.gapSize*(2*sy+1)
                borderVer = self.borderSize*(sy+1)

                startHor = sx*page.sectorWidth + gapHor + borderHor
                startVer = sy*page.sectorHeight + gapVer + borderVer

                for ri,row in enumerate(sector.dataRows + sector.eccRows):
                    for dbi,dotByte in enumerate(row.dotBytes):
                        for di,dot in enumerate(dotByte.dots):

                            x = startHor + Constants.ByteSize * dbi + di
                            y = startVer + ri

                            x *= self.scale
                            y *= self.scale

                            pval = dot.getChannels()

                            for xi in range(self.dotWhitespaceLeft, self.pixelsPerDot-self.dotWhitespaceRight):
                                for yi in range(self.dotWhitespaceBottom, self.pixelsPerDot-self.dotWhitespaceTop):
                                    pixels[y+yi][x+xi] = pval

                borderStartHor = startHor - self.gapSize - self.borderSize
                borderStartVer = startVer - self.gapSize - self.borderSize
                borderEndHor = borderStartHor + self.sectorWidthTotal
                borderEndVer = borderStartVer + self.sectorHeightTotal

                # TODO: Fix missing bottom-right-most pixel
                # Draw vertical borders
                for xscale in range(0, self.scale):
                    for bx in [self.scale*borderStartHor + xscale, self.scale*borderEndHor + xscale]:
                        for by in range(self.scale*borderStartVer, self.scale*borderEndVer):
                            pixels[by][bx] = self.BorderColor

                # Draw horizontal borders
                for yscale in range(0, self.scale):
                    for bx in range(self.scale*borderStartHor, self.scale*borderEndHor):
                        for by in [self.scale*borderStartVer + yscale, self.scale*borderEndVer + yscale]:
                            pixels[by][bx] = self.BorderColor

            self.images.append(pixels)

        return self.images


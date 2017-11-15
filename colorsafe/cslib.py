#!/usr/bin/python
import mmap
import math
import random
import time
import binascii
from unireedsolomon.rs import RSCoder

class Constants:
    Byte00 = 0b00000000
    Byte11 = 0b11111111
    Byte55 = 0b01010101
    ByteAA = 0b10101010
    ByteSize = 8
    ColorChannels = 3 # R, G, and B
    ColorChannels1 = 1 # B and W
    ColorChannels2 = 2 # R and G, encodes RGBW
    DataMode = 1
    ECCMode = 1
    MagicByte = 0b11001100 ^ Byte55
    MagicRowHeight = 1
    MajorVersion = 0
    MinorVersion = 1
    RSBlockSizeMax = 2 ** 8 - 1
    RevisionVersion = 0
    TotalPagesMaxBytes = 8

def binaryListToVal(l):
    place = 1
    val = 0
    for i in l:
        val += place * i
        place = place << 1
    return val

def getMagicRowBytes(colorDepth, width):
    magicRowBytes = [Constants.MagicByte]*colorDepth
    magicRowBytes = magicRowBytes * (width/(Constants.ByteSize))
    return magicRowBytes

class Dot:
    # p = Dot([0,0,1,0,1,1])
    def __init__(self, bitList):
        self.bitList = bitList
        self.getChannelNum(bitList)
        self.encode(bitList)

    def getChannelNum(self, bitList):
        if len(bitList) % Constants.ColorChannels == 0:
            self.channelNum = Constants.ColorChannels
        elif len(bitList) % Constants.ColorChannels2 == 0:
            self.channelNum = Constants.ColorChannels2
        #elif len(bitList) == Constants.ColorChannels1:
        else:
            self.channelNum = Constants.ColorChannels1

    # Set values from bitList into channels
    def encode(self, bitList):
        channelVals = list()
        bpc = len(bitList)/self.channelNum

        for b in range(0, len(bitList), bpc):
            channelBits = bitList[b : b + bpc]
            bVal = binaryListToVal(channelBits)
            channelVal = 1.0 * bVal / ( ( 1 << bpc ) - 1 )
            channelVals.append(channelVal)

        self.channels = tuple(channelVals)

    def getRGB(self):
        MaxVal = 255

        ret = None

        if self.channelNum == 1:
            ret = tuple([int(MaxVal*self.channels[0])])*Constants.ColorChannels
        elif self.channelNum == Constants.ColorChannels2:
            if self.channels[0] < 0.5 and self.channels[1] < 0.5:
                color = (MaxVal,MaxVal,MaxVal) # White
            elif self.channels[0] > 0.5 and self.channels[1] < 0.5:
                color = (0,MaxVal,MaxVal) # Cyan
            elif self.channels[0] < 0.5 and self.channels[1] > 0.5:
                color = (MaxVal,0,MaxVal) # Magneta
            elif self.channels[0] > 0.5 and self.channels[1] > 0.5:
                color = (MaxVal,MaxVal,0) # Yellow

            # The only unambiguous way to encode values is selecting two channels to alter value.
            value0 = 2*abs(0.5-self.channels[0])
            value1 = 2*abs(0.5-self.channels[1])
            ret = tuple([int(value0*color[0]),int(value1*color[1]),int(color[2])])

        elif self.channelNum == Constants.ColorChannels:
            ret = tuple([int(i*MaxVal) for i in self.channels])

        return ret

# 8 Dots
class DotByte:
    # pb = DotByte([0xAA, 0x55, 0xFF], 3)
    def __init__(self, bytesList, colorDepth):
        self.colorDepth = colorDepth
        self.encodeBytes(bytesList)

    def encodeBytes(self, bytesList):
        if self.colorDepth % Constants.ColorChannels != 0 and self.colorDepth % Constants.ColorChannels2 != 0 and self.colorDepth % 1 != 0:
            return False

        self.dots = list()

        for i in range(Constants.ByteSize):
            vals = list()
            for b in range(self.colorDepth):
                byte = Constants.Byte00

                if b < len(bytesList):
                    byte = bytesList[b]

                vals.append(byte >> i & 1)

            p = Dot(vals)
            self.dots.append(p)

        return True

class DotRow:
    # pr = DotRow([0xFF] * 3 * 8, 3, 8, 0)
    def __init__(self, bytesList, colorDepth, width, rowNumber):
        self.colorDepth = colorDepth
        self.width = width
        self.rowNumber = rowNumber

        self.encodeBytes(bytesList)

    # TODO: Fail on magic row
    def encodeBytes(self, bytesList):
        if self.width % Constants.ByteSize != 0:
            return False

        mask = (Constants.Byte55 if self.rowNumber % 2 == 0 else Constants.ByteAA)

        self.dotBytes = list()

        for inByte in range(0, self.colorDepth*self.width/Constants.ByteSize, self.colorDepth):
            bl = bytesList[inByte : inByte + self.colorDepth] 

            if len(bl) < self.colorDepth:
                bl.extend( [Constants.Byte00] * (self.colorDepth - len(bl)) )

            blTemp = list()
            for b in bl:
                try:
                    blTemp.append(ord(b) ^ mask)
                except TypeError:
                    blTemp.append(b ^ mask)

            pb = DotByte(blTemp, self.colorDepth)
            self.dotBytes.append( pb )

        return True

class Sector:
    #s = Sector(64,64,3,0.2,[0xFF]*64*64*3)
    def __init__(self, height, width, colorDepth, eccRate, data, dataStart = 0):
        self.height = height
        self.width = width
        self.colorDepth = colorDepth
        self.eccRate = eccRate
        self.data = data

        self.getBlockSizes()
        self.putData(dataStart)
        self.putECCData(dataStart)

    def getBlockSizes(self):
        self.rsBlockSizes = list()
        self.dataBlockSizes = list()
        self.eccBlockSizes = list()

        self.dataRowCount = self.getDataRowCount()
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

    def getDataRowCount(self):
        return int ( math.floor( ( self.height - Constants.MagicRowHeight ) / ( 1 + self.eccRate ) ) )

    def putData(self, dataStart = 0):
        self.dataRows = list()
        bytesPerRow = self.width * self.colorDepth / Constants.ByteSize

        for row in range(self.dataRowCount):
            minIndex = dataStart + row * bytesPerRow
            maxIndex = dataStart + ((row + 1) * bytesPerRow)

            insertData = self.data[ minIndex : maxIndex ]
            insertRow = DotRow( list(insertData), self.colorDepth, self.width, row ) 
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

        eccMagicRow = DotRow( getMagicRowBytes(self.colorDepth, self.width), self.colorDepth, self.width, \
            self.dataRowCount)

        self.eccRows = [ eccMagicRow ]
        bytesPerRow = self.width * self.colorDepth / Constants.ByteSize
        for row in range(self.eccRowCount):
            insertData = eccData[ row * bytesPerRow : (row + 1) * bytesPerRow ]
            insertRow = DotRow( insertData, self.colorDepth, self.width, row )
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
        self.dataStart = 0 #TODO: Make arg for putdata, not self object

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
        self.data = getMagicRowBytes(self.colorDepth, self.width)

        # Multiply each by self.colorDepth to make these effectively black and white
        self.data.extend([Constants.ByteAA]*self.MetadataInitPaddingBytes*self.colorDepth)
        self.data.extend(self.getColorDepthBytes())
        self.data.extend(self.getMetadataSchemeBytes())
        self.data.extend([Constants.ByteAA]*self.MetadataEndPaddingBytes*self.colorDepth)

        # Format metadata, interleave lists and 0-byte join
        # TODO: Encode ints not in ascii, verify this is working
        for (key, value) in metadata.items():
            kvString = str(key) + chr(Constants.Byte00) + (str(value) if value else "") + chr(Constants.Byte00)
            if len(kvString) + len(self.data) < self.getDataRowCount() * self.width * self.colorDepth:
                self.data.extend([ord(i) for i in kvString])
                self.metadata[key] = value

    # Updated value should be less than the originally written one, or else metadata could drop existing data.
    def updatePageNumber(self, pageNumber):
        self.metadata[Metadata.pageNumber] = pageNumber
        self.putMetadata(self.metadata)

    # Updated value should be less than the originally written one, or else metadata could drop existing data.
    def updateMetadataCount(self, metadataCount):
        self.metadata[Metadata.metadataCount] = metadataCount
        self.putMetadata(self.metadata)


class Page:
    def __init__(self, dataSectors, metadataSectors, pageNumber, sectorsVertical, sectorsHorizontal, colorDepth, \
        eccRate, sectorHeight, sectorWidth):

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

    def putMetadataSectors(self):
        self.sectors = [None] * (len(self.dataSectors) + len(self.metadataSectors))

        random.seed(self.pageNumber)
        allMetadataPagePositions = range(0, len(self.sectors))
        random.shuffle(allMetadataPagePositions)
        self.metadataSectorsPositions = allMetadataPagePositions[ : len(self.metadataSectors) ]

        metadataSectorIndex = 0
        for i in self.metadataSectorsPositions:
            self.sectors[i] = self.metadataSectors[metadataSectorIndex]
            metadataSectorIndex += 1

    def putDataSectors(self):
        self.dataSectorCount = (self.sectorsVertical*self.sectorsHorizontal)-len(self.metadataSectors)
        dataSectorIndex = 0
        for sectorIndex,sector in enumerate(self.sectors):
            if sector == None:
                self.sectors[sectorIndex] = self.dataSectors[dataSectorIndex]
                dataSectorIndex += 1

# The ColorSafe data and borders, all dimensions in dots.
class ColorSafeFile:

    # c = ColorSafeFile([0xFF]*10,15,12)
    def __init__(self, data, sectorsVertical, sectorsHorizontal, colorDepth, eccRate, sectorHeight, sectorWidth, filename, fileExtension):
        self.data = data
        self.sectorsVertical = sectorsVertical
        self.sectorsHorizontal = sectorsHorizontal
        self.colorDepth = colorDepth
        self.eccRate = eccRate
        self.sectorHeight = sectorHeight
        self.sectorWidth = sectorWidth
        self.filename = filename
        self.fileExtension = fileExtension

        self.getFileProperties()
        self.putDataSectors()
        self.createMetadataSectors()
        self.createPages()

    def getFileProperties(self):
        self.dataRowCount = int ( math.floor( ( self.sectorHeight - Constants.MagicRowHeight ) / ( 1 + self.eccRate ) ) )
        self.dataPerSector = self.sectorWidth * self.colorDepth * self.dataRowCount
        self.maxData = self.dataPerSector * self.sectorsVertical * self.sectorsHorizontal

    def putDataSectors(self):
        self.dataSectors = list()

        for dataStart in range(0,len(self.data),self.dataPerSector):
            # TODO: Setting data into Sector in place (using Sector's dataStart argument) may improve performance
            data = self.data[dataStart: dataStart + self.dataPerSector]

            s = Sector(self.sectorHeight,self.sectorWidth,self.colorDepth,self.eccRate,data)
            self.dataSectors.append(s)

    def createMetadataSectors(self):
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

        self.totalSectors = len(self.dataSectors) + len(self.metadataSectors)
        self.totalMetadataSectors = len(self.metadataSectors)
        self.sectorsPerPage = self.sectorsVertical * self.sectorsHorizontal

        if self.totalSectors > 1:
            self.totalPages = int( math.ceil( 1.0 * (self.totalSectors - 1) / (self.sectorsPerPage - 1) ) )
        else:
            self.totalPages = 1

        paddingMetadataSectors = self.sectorsHorizontal - (self.totalSectors % self.sectorsHorizontal)
        self.totalSectors += paddingMetadataSectors
        self.totalMetadataSectors += paddingMetadataSectors

        self.metadataPositions = range(self.totalPages)
        random.seed(0)
        random.shuffle(self.metadataPositions)
        self.metadataPositions = self.metadataPositions * int( math.ceil(self.totalMetadataSectors/self.totalPages) )
        self.metadataPositions = self.metadataPositions[:self.totalMetadataSectors]
        self.metadataPositions = { i : self.metadataPositions.count(i) for i in self.metadataPositions }

    def createPages(self):
        self.pages = list()
        for pageNum in range(self.totalPages):
            pageMetadataSectors = [self.metadataSectors[0]]

            mdIterator = 0
            for page, count in self.metadataPositions.iteritems():
                for i in range(count - 1):
                    pageMetadataSectors.append(self.metadataSectors[mdIterator])
                    mdIterator = (mdIterator + 1) % len(self.metadataSectors)

            for sector in pageMetadataSectors:
                sector.updatePageNumber(pageNum)
                sector.updateMetadataCount(len(pageMetadataSectors))

            dataSectorsCount = self.sectorsVertical * self.sectorsHorizontal - len(pageMetadataSectors)
            pageDataSectors = self.dataSectors[pageNum*dataSectorsCount : (pageNum+1)*dataSectorsCount]

            p = Page(pageDataSectors, pageMetadataSectors, pageNum, self.sectorsVertical, self.sectorsHorizontal, self.colorDepth, self.eccRate, self.sectorHeight, self.sectorWidth)

            self.pages.append(p)

    # TODO: Implement this
    def shuffleECCData(self):
        allECCData = list()

        for p in pages:
            for s in sectors:
                allEccData.extend(s.getECCData)

    def close(self):
        if dataMemoryMap:
            dataMemoryMap.close()
            dataMemoryMap = None

        if filePointer:
            filePointer.close()
            filePointer = None


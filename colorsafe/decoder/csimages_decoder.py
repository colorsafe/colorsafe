import os

from unireedsolomon import RSCoder, RSCodecError

from colorsafe import constants, defaults, utils
from colorsafe.csdatastructures import ColorSafeImages, Sector, DotRow
from colorsafe.decoder.csdecoder import SectorDecoder
from colorsafe.decoder.csdecoder_getbounds import get_data_bounds
from colorsafe.decoder.csdecoder_getchannels import get_normalized_channels_list
from colorsafe.decoder.csinput_page import InputPage


class ColorSafeImagesDecoder(ColorSafeImages):
    """A collection of saved ColorSafeFile objects, as images of working regions without outside borders or headers
    """

    def __init__(self, pages, colorDepth, tmpdir = None):
        """Convert a list of pages channels into a list of sector channels, create decoded sectors, return data.
        Remove borders and gaps, scale down.

        Pages channels is a list (size totalPages) of lists (size workingHeight) of rows (list size workingWidth) of
        channels.
        """
        if not colorDepth or colorDepth < 0 or colorDepth > constants.ColorDepthMax:
            colorDepth = defaults.colorDepth

        # Put each sector's data into a cleaned channelsList, 1 set of channels
        # per dot
        dataStr = ""
        metadataStr = ""

        for page_num in range(pages.totalPages):
            page = InputPage(pages, page_num)

            # TODO: Calculate dynamically
            # TODO: Override by command-line argument
            sectorHeight = defaults.sectorHeight
            sectorWidth = defaults.sectorWidth
            gapSize = defaults.gapSize
            eccRate = defaults.eccRate

            bounds = get_data_bounds(page, sectorHeight, sectorWidth, gapSize, page_num, tmpdir)

            sectorNum = -1

            # For each sector, beginning and ending at its gaps
            sectorDamage = list()
            for each_bounds in bounds:
                sectorNum += 1
                # perc = str(int(100.0 * sectorNum / (sectorsHorizontal*sectorsVertical))) + "%"

                channelsList = get_normalized_channels_list(page, each_bounds, sectorHeight, sectorWidth,
                                                            page_num, sectorNum, tmpdir)

                # TODO: Calculate dynamically
                bucketNum = 40

                thresholdWeight = self.getThresholdWeight(channelsList, bucketNum)

                dataRows = Sector.getDataRowCount(sectorHeight, eccRate)

                s = SectorDecoder(
                    channelsList,
                    colorDepth,
                    sectorHeight,
                    sectorWidth,
                    dataRows,
                    eccRate,
                    thresholdWeight)

                outData, damage = self.getCorrectedData(s, dataRows, sectorWidth)

                if (tmpdir):
                    f = open(os.path.join(tmpdir, "outDataNewLineDelimited" + str(sectorNum) + ".txt"), "w")
                    for i in outData:
                        f.write(str(i) + " " + str(utils.intToBinaryList(ord(i), 8)) + "\n")
                    f.close()

                sectorDamage.append(damage)

                # Add data to output if sector is not metadata
                magicRow = DotRow.getMagicRowBytes(colorDepth, sectorWidth)
                if s.dataRows[:len(magicRow)] != magicRow:
                    dataStr += outData
                else:
                    # TODO: Use ColorSafeFileDecoder to organize and parse this
                    metadataStr += str(sectorNum) + "\n" + outData + "\n\n"

        if len(sectorDamage):
            self.sectorDamageAvg = sum(sectorDamage) / len(sectorDamage)
        else:
            self.sectorDamageAvg = 1.0

        # TODO: Need to place sectors in Page objects, then each page in a CSFile, then call CSFile.decode()

        dataStr = dataStr.rstrip(chr(0))

        self.dataStr = dataStr
        self.metadataStr = metadataStr

    @staticmethod
    def getThresholdWeight(channelsList, bucketNum):
        # TODO: Use sum of squares to find min

        shadeBuckets = list()
        for i in range(bucketNum + 1):
            shadeBuckets.append(0)

        # Get min and max vals for normalization
        for c in channelsList:
            shadeBucketNum = int(c.getAverageShade() * bucketNum)
            shadeBuckets[shadeBucketNum] += 1

        # Get shade maxima locations, starting from each side
        shadeMaximaLeft = 0
        for i in range(2, bucketNum):
            if shadeBuckets[i] < shadeBuckets[i - 1] and shadeBuckets[i] < shadeBuckets[i - 2]:
                shadeMaximaLeft = i - 1
                break

        shadeMaximaRight = bucketNum
        for i in range(2, bucketNum)[::-1]:
            if shadeBuckets[i] > shadeBuckets[i - 1] and shadeBuckets[i] > shadeBuckets[i - 2]:
                shadeMaximaRight = i
                break

        # Get shade minima between maxima
        # shadeMinimaVal = max(
        #     shadeBuckets[shadeMaximaLeft],
        #     shadeBuckets[shadeMaximaRight])

        # A good default, in case of a single maxima, or two very close
        shadeMinima = (shadeMaximaLeft + shadeMaximaRight) / 2

        # TODO: Re-enable, this improves threshold finding for scanned images
        # for i in range(shadeMaximaLeft + 1, shadeMaximaRight):
        #     if shadeBuckets[i] < shadeMinimaVal:
        #         shadeMinimaVal = shadeBuckets[i]
        #         shadeMinima = i

        thresholdWeight = float(shadeMinima) / bucketNum

        return thresholdWeight

    @staticmethod
    def getCorrectedData(s, dataRows, sectorWidth):
        outData = "".join([chr(i) for i in s.dataRows])

        # TODO: Why is ecc inverted?
        eccData = "".join([chr(0xff - i) for i in s.eccRows])

        # Perform error correction, return uncorrected RS block on failure
        correctedData = ""
        damage = 0
        dindex = 0
        eindex = 0
        for i, dbs in enumerate(s.dataBlockSizes):
            ebs = s.eccBlockSizes[i]
            rsBlockData = outData[dindex:dindex + dbs]
            rsBlockEccData = eccData[eindex:eindex + ebs]
            uncorrectedStr = rsBlockData + rsBlockEccData

            rsDecoder = RSCoder(dbs + ebs, dbs)

            correctedStr = rsBlockData

            # An empty or all-0's string is invalid.
            if len(uncorrectedStr) and any(ord(u)
                                           for u in uncorrectedStr):

                try:
                    rsOutput = rsDecoder.decode(uncorrectedStr)
                    if rsOutput and len(rsOutput):
                        correctedStr = rsOutput[0]
                        for corrIter, corrChar in enumerate(
                                rsOutput[0]):
                            if corrChar != uncorrectedStr[corrIter]:
                                damage += 1
                # More errors than can be corrected. Set damage to
                # total number of blocks.
                except RSCodecError:
                    damage = dataRows * sectorWidth / constants.ByteSize

            correctedData += correctedStr

            dindex += dbs
            eindex += ebs

        sectorDamage = float(damage) / (dataRows * sectorWidth / constants.ByteSize)

        return correctedData, sectorDamage


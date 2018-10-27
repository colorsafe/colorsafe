import os

from unireedsolomon import RSCoder, RSCodecError

from colorsafe import constants, defaults, exceptions, utils
from colorsafe.csdatastructures import ColorSafeImages, ColorChannels, Sector, DotRow
from colorsafe.debugutils import drawPage
from colorsafe.decoder.csdecoder import SectorDecoder, InputPage


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

        for pageNum in range(pages.totalPages):
            page = InputPage(pages, pageNum)

            # TODO: Use angles, not skew, for a more granular accuracy.

            # Get skews
            verticalSkew = self.findSkew(page, True)
            horizontalSkew = self.findSkew(page, False)

            # Vertical bounds are more accurate since the data will extend to the horizontal end of the page.
            # Retrieve them first and use them to clip the horizontal bound region to not check an empty page bottom.
            # TODO: Clip at the outer bounds of the image, for best accuracy. Scan could have whitespace to either side.
            verticalChannelShadeAvg = self.getChannelShadeAvg(page, verticalSkew, True)
            verticalBounds = self.findBounds(verticalChannelShadeAvg)

            if not len(verticalBounds):
                raise exceptions.DecodingError("No vertical bounds detected.")

            # TODO: Get the real bottom of the image. Currently this is simply the lowest inner sector bound.
            verticalEnd = verticalBounds[-1][-1]

            horizontalChannelShadeAvg = self.getChannelShadeAvg(page, horizontalSkew, False, verticalEnd)
            horizontalBounds = self.findBounds(horizontalChannelShadeAvg)

            if not len(horizontalBounds):
                raise exceptions.DecodingError("No horizontal bounds detected")

            if (tmpdir):
                f = open(os.path.join(tmpdir, "skewAndBounds.txt"), "w")
                f.write("verticalSkew " + str(verticalSkew))
                f.write("\rhorizontalSkew " + str(horizontalSkew))
                f.write("\rverticalBounds " + str(verticalBounds))
                f.write("\rhorizontalBounds " + str(horizontalBounds))
                f.write("\rverticalChannelShadeAvg " + str(verticalChannelShadeAvg))
                f.write("\rhorizontalChannelShadeAvg " + str(horizontalChannelShadeAvg))
                f.close()

            bounds = self.getSkewSectorBounds(verticalBounds, horizontalBounds, verticalSkew, horizontalSkew)

            if (tmpdir):
                converted_bounds = list()
                for y1, y2, x1, x2 in bounds:
                    converted_bounds.extend([(y1, x1), (y1, x2), (y2, x1), (y2, x2)])
                drawPage(page, tmpdir, "bounds", tuple(converted_bounds), None, (255, 0, 0))

            # TODO: Calculate dynamically
            # TODO: Override by command-line argument
            sectorHeight = defaults.sectorHeight
            sectorWidth = defaults.sectorWidth
            gapSize = defaults.gapSize
            eccRate = defaults.eccRate

            sectorNum = -1

            if (tmpdir):
                debug_dots = list()

            # For each sector, beginning and ending at its gaps
            sectorDamage = list()
            for topTemp, bottomTemp, leftTemp, rightTemp in bounds:
                sectorNum += 1
                # perc = str(int(100.0 * sectorNum / (sectorsHorizontal*sectorsVertical))) + "%"

                # Use page-average to calculate height/width, works better for small sector sizes
                # Rotation should even out on average
                heightPerDot = float(bottomTemp - topTemp + 1) / (sectorHeight + 2 * gapSize)
                widthPerDot = float(rightTemp - leftTemp + 1) / (sectorWidth + 2 * gapSize)

                if widthPerDot < 1.0:  # Less than 1.0x resolution, cannot get all dots
                    raise exceptions.DecodingError

                top, bottom, left, right = self.getRealGaps(page,
                                                            heightPerDot,
                                                            widthPerDot,
                                                            topTemp,
                                                            bottomTemp,
                                                            leftTemp,
                                                            rightTemp)

                rowsBoundaryChanges = self.getBoundaryChanges(page, left, right, top, bottom)
                columnsBoundaryChanges = self.getBoundaryChanges(page, top, bottom, left, right, False)

                rowDotStartLocations = self.dotStartLocations(widthPerDot,
                                                              rowsBoundaryChanges,
                                                              sectorWidth)
                columnDotStartLocations = self.dotStartLocations(widthPerDot,
                                                                 columnsBoundaryChanges,
                                                                 sectorHeight)

                if (tmpdir):
                    for x in rowDotStartLocations:
                        for y in columnDotStartLocations:
                            debug_dots.append((top + x, left + y))

                # TODO: Calculate dynamically
                bucketNum = 40

                channelsList = self.getChannelsList(page,
                                                    columnDotStartLocations,
                                                    rowDotStartLocations,
                                                    top,
                                                    left,
                                                    sectorHeight,
                                                    sectorWidth)
                channelsList = self.normalizeChannelsList(channelsList)

                if (tmpdir):
                    f = open(os.path.join(tmpdir, "normalizedChannels" + str(sectorNum) + ".txt"), "w")
                    for i in channelsList:
                        f.write(str(i.getChannels()) + "\r")
                    f.close()

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

        if tmpdir:
            drawPage(page, tmpdir, "dots", tuple(debug_dots), None, (255, 0, 0))

        if len(sectorDamage):
            self.sectorDamageAvg = sum(sectorDamage) / len(sectorDamage)
        else:
            self.sectorDamageAvg = 1.0

        # TODO: Need to place sectors in Page objects, then each page in a CSFile, then call CSFile.decode()

        dataStr = dataStr.rstrip(chr(0))

        self.dataStr = dataStr
        self.metadataStr = metadataStr

    @staticmethod
    def normalize(val, minVal, maxVal):
        if maxVal == minVal:
            raise exceptions.DecodingError

        return (val - minVal) / (maxVal - minVal)

    @staticmethod
    def getSectorBounds(
            page,
            leastAlong,
            mostAlong,
            leastPerp,
            mostPerp,
            gapThreshold,
            vertical=True,
            reverse=False):
        """Search within given rough sector bounds and return the true coordinate of the gap
        E.g. if looking for the real top gap coordinate, along is y and perp is x. Return y.
        """
        alongRange = range(leastAlong + 1, mostAlong + 1)
        if reverse:
            alongRange = alongRange[::-1]

        for along in alongRange:
            perpShadeSum = 0.0
            for perp in range(leastPerp, mostPerp + 1):
                y = along if vertical else perp
                x = perp if vertical else along

                if y < 0 or y >= page.height or x < 0 or x >= page.width:
                    break

                perpShadeSum += utils.average(page.getPixel(y, x))
            perpShadeSum /= (mostPerp - leastPerp)
            if perpShadeSum > gapThreshold:
                return along

    @staticmethod
    def findSkew(page, vertical=True, reverse=False):
        """Find the a grid image's skew, based on the vertical (or horizontal) boolean

        Vertical skew is the number of pixels skewed right on the bottom side (negative if left) if the top is constant
        Horizontal skew is the number of pixels skewed down on the right side (negative if up) if the left is constant
        """
        # TODO: Binary search through perp to find first boundary. This will improve speed.
        # TODO: Search for two or more skew lines to improve accuracy? Scale
        # isn't known yet, so this is tricky

        DEFAULT_BEST_SKEW = 0
        MAX_SHADE_VARIANCE = 0.1

        dataDensity = 0.5
        alongStep = 10  # TODO: Refine this

        # Get length of column (or row) and the length of the axis
        # perpendicular to it, row (or column)
        # Along the axis specified by the vertical bool
        alongLength = page.height if vertical else page.width
        # Perpendicular to the axis specified by the vertical bool
        perpLength = page.width if vertical else page.height

        maxSkew = max(int(constants.MaxSkewPerc * perpLength),
                      constants.MaxSkew)

        # For each angle, find the minimum shade in the first border
        minShade = 1.0
        minShadeIter = perpLength if not reverse else 0
        bestSkewShadeList = []
        for skew in range(-maxSkew, maxSkew + 1):
            slope = float(skew) / alongLength

            # Choose perpendicular range bounds such that sloped line will not
            # run off the page
            perpBounds = range(min(0, skew), perpLength - max(0, skew))
            if reverse:
                perpBounds = perpBounds[::-1]

            # TODO: Consider stepping perp/along 5-10 at a time for speedup
            for perpIter in perpBounds:
                # Don't check far past the first border coordinate, in order to
                # speed up execution
                if not reverse:
                    breakCond = (perpIter > minShadeIter + 2 * maxSkew)
                else:
                    breakCond = (perpIter < minShadeIter - 2 * maxSkew)

                if breakCond:
                    break

                skewLine = list()
                for alongIter in range(0, alongLength, alongStep):
                    perpValue = int(round(alongIter * slope)) + perpIter

                    if perpValue < 0 or perpValue >= perpLength:
                        skewLine = list()
                        break

                    x = perpValue if vertical else alongIter
                    y = alongIter if vertical else perpValue

                    pixelShade = utils.average(page.getPixel(y, x))
                    skewLine.append(pixelShade)

                if not len(skewLine):
                    continue

                # TODO: Normalize
                # Add all skews and shades to a list if they're smaller than the smallest shade (plus some variance)
                avgShade = sum(skewLine) / len(skewLine)
                if avgShade < minShade * (1 + MAX_SHADE_VARIANCE) and avgShade < dataDensity:
                    minShade = avgShade
                    bestSkewShadeList.append((skew, minShade))
                    minShadeIter = perpIter

        # The bestSkewShadeList will have many shades/skews not near the bottom, since above we started from 1.0 and
        # included all smaller shades along the way. We did that to reduce the list size here, where we take the average
        # of shades within the variance of the global minimum.
        globalMinShade = 1.0
        for skew, minShade in bestSkewShadeList:
            globalMinShade = min(globalMinShade, minShade)

        bestSkews = []
        for skew, minShade in bestSkewShadeList:
            if minShade < globalMinShade * (1 + MAX_SHADE_VARIANCE):
                bestSkews.append(skew)

        bestSkew = utils.average(bestSkews) if len(bestSkews) else DEFAULT_BEST_SKEW
        return bestSkew

    @staticmethod
    def getChannelShadeAvg(page, skew, vertical=True, perpEnd = None):
        """Get bounds including skew
        """
        perpStep = 3  # TODO: Refine this

        # Get length of column (or row) and the length of the axis
        # perpendicular to it, row (or column)
        # Along the axis specified by the vertical bool
        alongLength = page.height if vertical else page.width
        # Perpendicular, e.g. in the direction of the bounds. PerpEnd can replace this is supplied.
        perpLength = perpEnd if perpEnd else (page.width if vertical else page.height)

        slope = float(skew) / perpLength

        # Get all skew line shade sums
        channelShadeAvg = list()
        for alongIter in range(0, alongLength):
            alongShadeSum = 0

            # Sum all shades along the skew line
            perpLengthIterated = 0
            for perpIter in range(0, perpLength, perpStep):
                perpValue = int(round(perpIter * slope)) + alongIter

                # If coordinates are out of bounds of the image, use white pixels
                if perpValue < 0 or perpValue >= alongLength:
                    # TODO: Make all white, or else start at perp values that will all be contained in the image
                    # alongShadeSum = 1.0 * perpLength / perpStep  # White border

                    alongShadeSum += 1.0
                    continue

                y = perpValue if vertical else perpIter
                x = perpIter if vertical else perpValue

                pixelShade = utils.average(page.getPixel(y, x))
                alongShadeSum += pixelShade

            channelShadeAvg.append(alongShadeSum * perpStep / perpLength)

        return channelShadeAvg

    @staticmethod
    def getSkewSectorBounds(
            verticalBounds,
            horizontalBounds,
            verticalSkew,
            horizontalSkew):
        """Given skews, get skewed bounds from non-skewed ones
        """
        bounds = list()

        for top, bottom in verticalBounds:
            for left, right in horizontalBounds:
                bound = (top, bottom, left, right)
                bounds.append(bound)

        return bounds

    # TODO: Consider moving this logic to a new ChannelsGrid object
    # TODO: Set previousCount as average pixel width when called
    @staticmethod
    def findBounds(l, previousCount=6):
        """Given a 1D black and white grid matrix (one axis of a 2D grid matrix) return a list of beginnings and ends.
        A beginning is the first whitespace (gap) after any black border, and an end is the last whitespace (gap)
        before the next black border.

        Use whitespace after borders rather than searching for the data within each border, since the
        data may be empty or inconsistent. Borders are the most reliable unit of recognition.
        """
        minLengthSector = max(defaults.sectorWidth, defaults.sectorHeight)

        lowBorderThreshold = 0.35
        highGapThreshold = 0.65
        # Threshold for throwing out a value and using the mode end-begin diff
        # instead
        diffThreshold = 0.1

        # Trim leading/trailing whitespace for better min/max normalization
        borderBeginning = 0
        for i, val in enumerate(l):
            if ColorSafeImagesDecoder.normalize(val, min(l), max(l)) < highGapThreshold:
                borderBeginning = i
                break

        borderEnding = len(l)
        for i, val in reversed(list(enumerate(l))):
            if ColorSafeImagesDecoder.normalize(val, min(l), max(l)) < highGapThreshold:
                borderEnding = i
                break

        lTruncated = l[borderBeginning:borderEnding + 1]

        # TODO: Use top/bottom 10th percentiles to threshold, for better accuracy
        minVal = min(lTruncated)
        maxVal = max(lTruncated)

        begins = list()
        ends = list()

        # Find beginning border, and then all begin/end gaps that surround
        # sector data
        for i, val in enumerate(l):
            if i < borderBeginning or i > borderEnding:
                continue

            val = ColorSafeImagesDecoder.normalize(val, minVal, maxVal)

            # Look for expected values to cross thresholds anywhere in the last
            # previousCount values.
            previousVals = list()
            for shift in range(previousCount):
                prevIndex = i - shift - 1
                if prevIndex >= 0:
                    previousVals.append(
                        ColorSafeImagesDecoder.normalize(
                            l[prevIndex], minVal, maxVal))

            # Begins and ends matched, looking for new begin gap
            if len(begins) == len(ends):
                # Boundary where black turns white
                if val > highGapThreshold and any(
                        v < lowBorderThreshold for v in previousVals):
                    begins.append(i)
                    continue

            # More begins than ends, looking for new end gap
            if len(ends) < len(begins):
                # Boundary where white turns black
                if val < lowBorderThreshold and any(
                        v > highGapThreshold for v in previousVals):
                    if i >= begins[-1] + minLengthSector:
                        ends.append(i - 1)
                        continue

        # If begins and ends don't match, correct by cutting off excess
        # beginning
        if len(begins) > len(ends):
            begins = begins[0:len(ends)]

        # Correct bounds
        if len(begins) > 1:
            beginsDiffs = list()
            endsDiffs = list()
            for i in range(1, len(begins)):
                beginsDiffs.append(begins[i] - begins[i - 1])
                endsDiffs.append(ends[i] - ends[i - 1])

            beginsDiffsMode = max(beginsDiffs, key=beginsDiffs.count)
            endsDiffsMode = max(endsDiffs, key=endsDiffs.count)

            # TODO: Doesn't correct first begin or end - assumes first one is
            # correct
            for i in range(1, len(begins)):
                if abs(begins[i] - begins[i - 1]) / float(beginsDiffsMode) > diffThreshold:
                    begins[i] = begins[i - 1] + beginsDiffsMode

                if abs(ends[i] - ends[i - 1]) / float(endsDiffsMode) > diffThreshold:
                    ends[i] = ends[i - 1] + endsDiffsMode

        bounds = list()
        for i in range(0, len(begins)):
            bounds.append((begins[i], ends[i]))

        return bounds

    @staticmethod
    def getBoundaryChanges(page, begin, end, perp_begin, perp_end, rows = True):
        """ For all pixels in sector, mark and sum boundary changes for all rows or columns
        TODO: Generalize to multiple shades, e.g. shadesPerChannel = 2

        :param page
        :param begin:
        :param end:
        :param perp_begin:
        :param perp_end:
        :param rows
        :return:
        """

        BoundaryThreshold = 0.8

        boundaryChanges = list()

        for i in range(begin + 1, end + 1):
            allBoundaryChanges = 0
            for j in range(perp_begin, perp_end + 1):
                current = page.getPixel(j if rows else i, i if rows else j)
                previous = page.getPixel(j if rows else i - 1, i - 1 if rows else j)

                for k in range(len(current)):
                    bucketCurrent = (0 if current[k] < BoundaryThreshold else 1)
                    bucketPrevious = (0 if previous[k] < BoundaryThreshold else 1)

                    # Get white to black only, seems to be more
                    # consistent
                    if bucketCurrent != bucketPrevious and bucketCurrent == 0:
                        allBoundaryChanges += 1

            boundaryChanges.append(allBoundaryChanges)

        return boundaryChanges

    @staticmethod
    def dotStartLocations(widthPerDot, boundaryChanges, sectorLength):
        """Find the most likely dot start locations

        :param sectorLength SectorHeight for columns, SectorWidth for rows
        :return:
        """

        avgPixelsWidth = int(round(widthPerDot))

        if widthPerDot == 1.0:  # Exactly 1.0, e.g. original output, or perfectly scanned
            maxPixelsWidth = 1
        else:
            maxPixelsWidth = avgPixelsWidth + 1

        minPixelsWidth = max(
            avgPixelsWidth - 1,
            1)  # Cannot be less than 1

        dotStartLocations = list()
        currentLocation = 0
        for i in range(sectorLength):
            # TODO: Account for the gap, find initial data start
            mnw = minPixelsWidth if i else 0
            possible = boundaryChanges[currentLocation + mnw: currentLocation + maxPixelsWidth + (1 if i else 0)]
            if possible:
                index = possible.index(max(possible))
            else:
                index = 0
            currentLocation += index + mnw
            dotStartLocations.append(currentLocation)

        # For ending, add average width to the end so that dot
        # padding/fill is correct
        dotStartLocations.append(dotStartLocations[-1] + avgPixelsWidth)

        return dotStartLocations

    @staticmethod
    def getRealGaps(page, heightPerDot, widthPerDot, topTemp, bottomTemp, leftTemp, rightTemp):
        """Find real gaps, since small rotation across a large page may distort this.
        Look within one-dot unit of pixels away
        """
        bottommostTop = topTemp + int(round(heightPerDot))
        topmostTop = topTemp - int(round(heightPerDot))
        bottommostBottom = bottomTemp + int(round(heightPerDot))
        topmostBottom = bottomTemp - int(round(heightPerDot))

        rightmostLeft = leftTemp + int(round(widthPerDot))
        leftmostLeft = leftTemp - int(round(widthPerDot))
        rightmostRight = rightTemp + int(round(widthPerDot))
        leftmostRight = rightTemp - int(round(widthPerDot))

        gapThreshold = 0.75

        top = ColorSafeImagesDecoder.getSectorBounds(
            page,
            topmostTop,
            bottommostTop,
            rightmostLeft,
            leftmostRight,
            gapThreshold)

        bottom = ColorSafeImagesDecoder.getSectorBounds(
            page,
            topmostBottom,
            bottommostBottom,
            rightmostLeft,
            leftmostRight,
            gapThreshold,
            True,
            True)

        left = ColorSafeImagesDecoder.getSectorBounds(
            page,
            leftmostLeft,
            rightmostLeft,
            bottommostTop,
            topmostBottom,
            gapThreshold,
            False)

        right = ColorSafeImagesDecoder.getSectorBounds(
            page,
            leftmostRight,
            rightmostRight,
            bottommostTop,
            topmostBottom,
            gapThreshold,
            False,
            True)

        top = top if top else topTemp
        bottom = bottom if bottom else bottomTemp
        left = left if left else leftTemp
        right = right if right else rightTemp

        return top, bottom, left, right

    @staticmethod
    def getChannelsList(page, columnDotStartLocations, rowDotStartLocations, top, left, sectorHeight, sectorWidth):
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
                        pixel = page.getPixel(yPixel, xPixel)

                        dotPixels.append(pixel)

                # Average all pixels in the list, set into new
                # ColorChannel
                R, G, B = 0, 0, 0  # TODO: Generalize to channels, place in ColorChannels
                for dotPixel in dotPixels:
                    R1, G1, B1 = dotPixel
                    R += R1
                    G += G1
                    B += B1

                R /= len(dotPixels)
                G /= len(dotPixels)
                B /= len(dotPixels)
                c = ColorChannels(R, G, B)

                channelsList.append(c)

        return channelsList

    @staticmethod
    def normalizeChannelsList(channelsList):
        minVals = [1.0, 1.0, 1.0]
        maxVals = [0.0, 0.0, 0.0]

        # Get min and max vals for normalization
        for c in channelsList:
            vals = c.getChannels()
            for i, val in enumerate(vals):
                if val < minVals[i]:
                    minVals[i] = val
                if val > maxVals[i]:
                    maxVals[i] = val

        normalizedChannelsList = list()
        for i, channels in enumerate(channelsList):
            minVal = sum(minVals) / len(minVals)
            maxVal = sum(maxVals) / len(maxVals)

            if (minVal == maxVal):
                raise exceptions.DecodingError

            channels.subtractShade(minVal)
            channels.multiplyShade([1.0 / (maxVal - minVal)])

            normalizedChannelsList.append(channels)

        return normalizedChannelsList

    @staticmethod
    def getThresholdWeight(channelsList, bucketNum):
        shadeBuckets = list()
        for i in range(bucketNum):
            shadeBuckets.append(0)

        # Get min and max vals for normalization
        for c in channelsList:
            bucketNum = int(c.getAverageShade() * bucketNum) - 1
            shadeBuckets[bucketNum] += 1

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
        shadeMinimaVal = max(
            shadeBuckets[shadeMaximaLeft],
            shadeBuckets[shadeMaximaRight])

        # A good default, in case of a single maxima, or two very close
        shadeMinima = (shadeMaximaLeft + shadeMaximaRight) / 2

        for i in range(shadeMaximaLeft + 1, shadeMaximaRight):
            if shadeBuckets[i] < shadeMinimaVal:
                shadeMinimaVal = shadeBuckets[i]
                shadeMinima = i

        thresholdWeight = float(shadeMinima) / bucketNum - constants.DefaultThresholdWeight

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
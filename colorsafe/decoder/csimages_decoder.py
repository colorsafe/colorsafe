from unireedsolomon import RSCoder, RSCodecError

from colorsafe import constants, defaults, exceptions, utils
from colorsafe.csdatastructures import ColorSafeImages, ColorChannels, Sector, DotRow
from colorsafe.decoder.csdecoder import SectorDecoder


class InputPage:
    def __init__(self, pages, pageNum):
        self.pages = pages
        self.height = pages.height
        self.width = pages.width
        self.pageNum = pageNum

    def getPixel(self, y, x):
        return self.pages.getPagePixel(self.pageNum, y, x)


class ColorSafeImagesDecoder(ColorSafeImages):
    """A collection of saved ColorSafeFile objects, as images of working regions without outside borders or headers
    """

    def __init__(self, pages, colorDepth):
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

            # Get skews
            verticalSkew = self.findSkew(page, True)
            horizontalSkew = self.findSkew(page, False)

            verticalBounds = self.findSkewBounds(page, verticalSkew, True)
            horizontalBounds = self.findSkewBounds(page, horizontalSkew, False)

            bounds = self.getSkewSectorBounds(
                verticalBounds, horizontalBounds, verticalSkew, horizontalSkew)

            sectorsVertical = len(verticalBounds)
            sectorsHorizontal = len(horizontalBounds)

            # TODO: Move to this function's arguments
            sectorHeight = defaults.sectorHeight
            sectorWidth = defaults.sectorWidth
            gapSize = defaults.gapSize
            borderSize = defaults.borderSize
            eccRate = defaults.eccRate

            sectorNum = -1

            # For each sector, beginning and ending at its gaps
            sectorDamage = list()
            for topTemp, bottomTemp, leftTemp, rightTemp in bounds:
                sectorNum += 1
                # Use page-average to calculate height/width, works better for small sector sizes
                # Rotation should even out on average
                heightPerDot = float(bottomTemp - topTemp + 1) / (sectorHeight + 2 * gapSize)
                widthPerDot = float(rightTemp - leftTemp + 1) / (sectorWidth + 2 * gapSize)

                if widthPerDot < 1.0:  # Less than 1.0x resolution, cannot get all dots
                    raise exceptions.DecodingError

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

                gapThreshold = 0.75

                top = self.getSectorBounds(
                    page,
                    topmostTop,
                    bottommostTop,
                    rightmostLeft,
                    leftmostRight,
                    gapThreshold)
                bottom = self.getSectorBounds(
                    page,
                    topmostBottom,
                    bottommostBottom,
                    rightmostLeft,
                    leftmostRight,
                    gapThreshold,
                    True,
                    True)
                left = self.getSectorBounds(
                    page,
                    leftmostLeft,
                    rightmostLeft,
                    bottommostTop,
                    topmostBottom,
                    gapThreshold,
                    False)
                right = self.getSectorBounds(
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

                # For all pixels in sector, mark and sum boundary changes for all rows and columns
                # TODO: Generalize to multiple shades
                #shadesPerChannel = 2
                boundaryThreshold = 0.8

                rowsBoundaryChanges = list()
                for x in range(left + 1, right + 1):
                    allRowBoundaryChanges = 0
                    for y in range(top, bottom + 1):
                        current = page.getPixel(y, x)
                        previous = page.getPixel(y, x - 1)

                        for i in range(len(current)):
                            bucketCurrent = (
                                0 if current[i] < boundaryThreshold else 1)
                            bucketPrevious = (
                                0 if previous[i] < boundaryThreshold else 1)
                            # Get white to black only, seems to be more
                            # consistent
                            if bucketCurrent != bucketPrevious and bucketCurrent == 0:
                                allRowBoundaryChanges += 1

                    rowsBoundaryChanges.append(allRowBoundaryChanges)

                columnsBoundaryChanges = list()
                for y in range(top + 1, bottom + 1):
                    allColumnBoundaryChanges = 0
                    for x in range(left, right + 1):
                        current = page.getPixel(y, x)
                        previous = page.getPixel(y - 1, x)

                        for i in range(len(current)):
                            bucketCurrent = (
                                0 if current[i] < boundaryThreshold else 1)
                            bucketPrevious = (
                                0 if previous[i] < boundaryThreshold else 1)
                            # Get white to black only, seems to be more
                            # consistent
                            if bucketCurrent != bucketPrevious and bucketCurrent == 0:
                                allColumnBoundaryChanges += 1

                    columnsBoundaryChanges.append(allColumnBoundaryChanges)

                # Find the most likely dot start locations
                # TODO: Combine into one function
                avgPixelsWidth = int(round(widthPerDot))

                if widthPerDot == 1.0:  # Exactly 1.0, e.g. original output, or perfectly scanned
                    maxPixelsWidth = 1
                else:
                    maxPixelsWidth = avgPixelsWidth + 1

                minPixelsWidth = max(
                    avgPixelsWidth - 1,
                    1)  # Cannot be less than 1

                columnDotStartLocations = list()
                currentLocation = 0
                for i in range(sectorHeight):
                    # TODO: Account for the gap, find initial data start
                    mnw = minPixelsWidth if i else 0
                    possible = columnsBoundaryChanges[currentLocation +
                                                      mnw: currentLocation + maxPixelsWidth + (1 if i else 0)]
                    if possible:
                        index = possible.index(max(possible))
                    else:
                        index = 0
                    currentLocation += index + mnw
                    columnDotStartLocations.append(currentLocation)

                # For ending, add average width to the end so that dot
                # padding/fill is correct
                columnDotStartLocations.append(
                    columnDotStartLocations[-1] + avgPixelsWidth)

                rowDotStartLocations = list()
                currentLocation = 0
                for i in range(sectorWidth):
                    # TODO: Account for the gap, find initial data start
                    mnw = minPixelsWidth if i else 0
                    possible = rowsBoundaryChanges[currentLocation +
                                                   mnw: currentLocation +
                                                   maxPixelsWidth +
                                                   (1 if i else 0)]
                    if possible:
                        index = possible.index(max(possible))
                    else:
                        index = 0
                    currentLocation += index + mnw
                    rowDotStartLocations.append(currentLocation)

                # For ending, add average width to the end so that dot
                # padding/fill is correct
                rowDotStartLocations.append(
                    rowDotStartLocations[-1] + avgPixelsWidth)

                # perc = str(int(100.0 * sectorNum / (sectorsHorizontal*sectorsVertical))) + "%"

                minVals = [1.0, 1.0, 1.0]
                maxVals = [0.0, 0.0, 0.0]
                shadeBuckets = list()
                BucketNum = 40  # TODO: Calculate dynamically?
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

                        # Get min and max vals for normalization
                        vals = c.getChannels()
                        for i, val in enumerate(vals):
                            if val < minVals[i]:
                                minVals[i] = val
                            if val > maxVals[i]:
                                maxVals[i] = val

                        bucketNum = int(c.getAverageShade() * BucketNum) - 1
                        shadeBuckets[bucketNum] += 1

                for i, channels in enumerate(channelsList):
                    minVal = sum(minVals) / len(minVals)
                    maxVal = sum(maxVals) / len(maxVals)

                    if (minVal == maxVal):
                        raise exceptions.DecodingError

                    channels.subtractShade(minVal)
                    channels.multiplyShade([1.0 / (maxVal - minVal)])

                # Get shade maxima locations, starting from each side
                shadeMaximaLeft = 0
                for i in range(2, BucketNum):
                    if shadeBuckets[i] < shadeBuckets[i - 1] and shadeBuckets[i] < shadeBuckets[i - 2]:
                        shadeMaximaLeft = i - 1
                        break

                shadeMaximaRight = BucketNum
                for i in range(2, BucketNum)[::-1]:
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

                dataRows = Sector.getDataRowCount(sectorHeight, eccRate)
                thresholdWeight = float(shadeMinima) / BucketNum - constants.DefaultThresholdWeight
                s = SectorDecoder(
                    channelsList,
                    colorDepth,
                    sectorHeight,
                    sectorWidth,
                    dataRows,
                    eccRate,
                    thresholdWeight)

                outData = "".join([chr(i) for i in s.dataRows])
                # TODO: Why is ecc inverted?
                eccData = "".join([chr(0xff - i) for i in s.eccRows])

                # Perform error correction, return uncorrected RS block on
                # failure
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
                        rsOutput = None

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

                sectorDamage.append(
                    float(damage) / (dataRows * sectorWidth / constants.ByteSize))

                outData = correctedData

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

        # TODO: Need to place sectors in Page objects, then each page in a
        # CSFile, then call CSFile.decode()

        dataStr = dataStr.rstrip(chr(0))

        self.dataStr = dataStr
        self.metadataStr = metadataStr


    def normalize(self, val, minVal, maxVal):
        if (maxVal == minVal):
            raise exceptions.DecodingError

        return (val - minVal) / (maxVal - minVal)


    def getSectorBounds(
            self,
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
        bestSkew = 0
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
                avgShade = sum(skewLine) / len(skewLine)
                if avgShade < minShade and avgShade < dataDensity:
                    minShade = avgShade
                    bestSkew = skew
                    minShadeIter = perpIter

        return bestSkew

    def findSkewBounds(self, page, skew, vertical=True):
        """Get bounds including skew
        """
        perpStep = 3  # TODO: Refine this

        # Get length of column (or row) and the length of the axis
        # perpendicular to it, row (or column)
        # Along the axis specified by the vertical bool
        alongLength = page.height if vertical else page.width
        # Perpendicular, e.g. in the direction of the bounds
        perpLength = page.width if vertical else page.height
        slope = float(skew) / perpLength

        # Get all skew line shade sums
        channelShadeAvg = list()
        for alongIter in range(0, alongLength):
            alongShadeSum = 0

            # Sum all shades along the skew line
            for perpIter in range(0, perpLength, perpStep):
                perpValue = int(round(perpIter * slope)) + alongIter

                if perpValue < 0 or perpValue >= alongLength:
                    alongShadeSum = 1.0 * perpLength  # White border
                    skewLine = list()
                    break

                y = perpValue if vertical else perpIter
                x = perpIter if vertical else perpValue

                pixelShade = utils.average(page.getPixel(y, x))
                alongShadeSum += pixelShade

            channelShadeAvg.append(alongShadeSum * perpStep / perpLength)

        bounds = self.findBounds(channelShadeAvg)

        return bounds

    def getSkewSectorBounds(
            self,
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
    def findBounds(self, l, previousCount=6):
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
            if self.normalize(val, min(l), max(l)) < highGapThreshold:
                borderBeginning = i
                break

        borderEnding = len(l)
        for i, val in reversed(list(enumerate(l))):
            if self.normalize(val, min(l), max(l)) < highGapThreshold:
                borderEnding = i
                break

        lTruncated = l[borderBeginning:borderEnding + 1]
        minVal = min(lTruncated)
        maxVal = max(lTruncated)

        begins = list()
        ends = list()

        # Find beginning border, and then all begin/end gaps that surround
        # sector data
        for i, val in enumerate(l):
            if i < borderBeginning or i > borderEnding:
                continue

            val = self.normalize(val, minVal, maxVal)

            # Look for expected values to cross thresholds anywhere in the last
            # previousCount values.
            previousVals = list()
            for shift in range(previousCount):
                prevIndex = i - shift - 1
                if prevIndex >= 0:
                    previousVals.append(
                        self.normalize(
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
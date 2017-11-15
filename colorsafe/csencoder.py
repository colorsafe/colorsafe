#!/usr/bin/python

import cslib
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch, cm
from reportlab.lib.pagesizes import letter
import mmap
from PIL import Image
import math

# Defaults
colorDepth = 1
eccRate = 0.2

# All in dots
sectorHeight = 64
sectorWidth = 64
borderSize = 1
gapSize = 1

dotFillPixels = 1 # An integer representing the number of pixels colored in per dot per side.
pixelsPerDot = 2 # An integer representing the number of pixels representing a dot per side. Warning: Encoding processing time increases proportionally to this value

# For writing metadata
filename = "out"
fileExtension = "txt"

# For outputting temp files
OutputFilenameDefault = "out"

# A collection of saved ColorSafeFile objects, as images of working regions without outside borders or headers
class ColorSafeImageFiles:
    BorderColor = (0,0,0)
    OutputExtensionDefault = "png"

    def __init__(self, data, fullWorkingHeightPixels, fullWorkingWidthPixels, dotFillPixels = dotFillPixels, pixelsPerDot = pixelsPerDot, colorDepth = colorDepth, eccRate = eccRate, sectorHeight = sectorHeight, sectorWidth = sectorWidth, borderSize = borderSize, gapSize = gapSize, filename = filename, fileExtension = fileExtension):
        self.fullWorkingHeightPixels = fullWorkingHeightPixels
        self.fullWorkingWidthPixels = fullWorkingWidthPixels
        self.dotFillPixels = dotFillPixels
        self.pixelsPerDot = pixelsPerDot

        self.sectorHeight = sectorHeight
        self.sectorWidth = sectorWidth
        self.borderSize = borderSize
        self.gapSize = gapSize

        self.getImageProperties()

        self.csFile = cslib.ColorSafeFile(data, self.sectorsVertical, self.sectorsHorizontal, colorDepth = colorDepth, eccRate = eccRate, sectorHeight = sectorHeight, sectorWidth = sectorWidth, filename = filename, fileExtension = fileExtension)

        self.getImagePixels()

    # Calculate sector count based on maximum allowable in working region
    def getImageProperties(self):
        self.scale = self.pixelsPerDot

        # An integer representing the number of non-colored pixels representing a dot for respective sides.
        dotWhitespace = self.pixelsPerDot - self.dotFillPixels
        self.dotWhitespaceTop = int(math.floor(float(dotWhitespace)/2))
        self.dotWhitespaceBottom = int(math.ceil(float(dotWhitespace)/2))
        self.dotWhitespaceLeft = int(math.floor(float(dotWhitespace)/2))
        self.dotWhitespaceRight = int(math.ceil(float(dotWhitespace)/2))
        #print self.dotWhitespaceLeft, self.dotWhitespaceRight, self.dotWhitespaceTop, self.dotWhitespaceBottom, self.pixelsPerDot

        # In dots, excluding overlapping borders
        sectorHeightTotal = self.sectorHeight + self.borderSize + 2 * self.gapSize
        sectorWidthTotal = self.sectorWidth + self.borderSize + 2 * self.gapSize

        # Remove single extra non-overlapping border at the bottom-right of working region
        self.sectorsVertical = float(self.fullWorkingHeightPixels - self.scale*self.borderSize) / (self.scale*sectorHeightTotal)
        self.sectorsHorizontal = float(self.fullWorkingWidthPixels - self.scale*self.borderSize) / (self.scale*sectorWidthTotal)
        self.sectorsVertical = int ( math.floor(self.sectorsVertical) )
        self.sectorsHorizontal = int ( math.floor(self.sectorsHorizontal) )

        self.workingHeightPixels = (self.sectorsVertical * sectorHeightTotal + self.borderSize) * self.scale
        self.workingWidthPixels = (self.sectorsHorizontal * sectorWidthTotal + self.borderSize) * self.scale

    def getImagePixels(self):
        self.images = list()
        image = Image.new('RGB', (self.workingWidthPixels,self.workingHeightPixels), "white")
        pixels = image.load() # create the pixel map

        pixelCount = 0

        for pgi,page in enumerate(self.csFile.pages):
            for si,sector in enumerate(page.sectors):
                # Draw Data
                for ri,row in enumerate(sector.dataRows):
                    for pbi,dotByte in enumerate(row.dotBytes):
                        for pi,dot in enumerate(dotByte.dots):
                            sx = si % page.sectorsHorizontal
                            sy = si / page.sectorsHorizontal

                            gapHor = self.gapSize if sx==0 else (2*sx+1)*self.gapSize
                            borderHor = self.borderSize*(sx+1)

                            gapVer = self.gapSize if sy==0 else (2*sy+1)*self.gapSize
                            borderVer = self.borderSize*(sy+1)

                            x = sx*page.sectorWidth + cslib.Constants.ByteSize*pbi + pi + gapHor + borderHor
                            y = sy*page.sectorHeight + ri + gapVer + borderVer

                            x *= self.scale
                            y *= self.scale

                            pval = dot.getRGB()

                            for xi in range(self.dotWhitespaceLeft, self.pixelsPerDot-self.dotWhitespaceRight):
                                for yi in range(self.dotWhitespaceBottom, self.pixelsPerDot-self.dotWhitespaceTop):
                                    pixels[x+xi,y+yi] = pval

                            pixelCount += 1

                # Draw ECC data
                for ri,row in enumerate(sector.eccRows):
                    for pbi,dotByte in enumerate(row.dotBytes):
                        for pi,dot in enumerate(dotByte.dots):
                            sx = si % page.sectorsHorizontal
                            sy = si / page.sectorsHorizontal

                            gapHor = self.gapSize if sx==0 else (2*sx+1)*self.gapSize
                            borderHor = self.borderSize*(sx+1)

                            gapVer = self.gapSize if sy==0 else (2*sy+1)*self.gapSize
                            borderVer = self.borderSize*(sy+1)

                            dataHeight = sector.dataRowCount

                            x = sx*page.sectorWidth + cslib.Constants.ByteSize*pbi + pi + gapHor + borderHor
                            y = sy*page.sectorHeight + ri + gapVer + borderVer + dataHeight

                            x *= self.scale
                            y *= self.scale

                            pval = dot.getRGB()
                            pval = dot.getRGB()

                            for xi in range(self.dotWhitespaceLeft, self.pixelsPerDot-self.dotWhitespaceRight):
                                for yi in range(self.dotWhitespaceBottom, self.pixelsPerDot-self.dotWhitespaceTop):
                                    pixels[x+xi,y+yi] = pval

                            pixelCount += 1

            # Draw borders
            for bx in range(page.sectorsHorizontal+1):
                for by in range(self.workingHeightPixels):
                    gapHor = 2 * bx * self.gapSize
                    borderHor = bx * self.borderSize

                    x = bx * page.sectorWidth + gapHor + borderHor
                    x *= self.scale

                    for xi in range(0, self.scale):
                        pixels[x + xi, by] = self.BorderColor

            for bx in range(self.workingWidthPixels):
                for by in range(page.sectorsVertical+1):
                    gapVer = 2 * by * self.gapSize
                    borderVer = by * self.borderSize

                    y = by * page.sectorHeight + gapVer + borderVer
                    y *= self.scale

                    for yi in range(0, self.scale):
                        pixels[bx, y + yi] = self.BorderColor

            outputFilename = OutputFilenameDefault + str(pgi) + "." + self.OutputExtensionDefault

            # TODO: Remove temp image files, optionally
            image.save(outputFilename)

            self.images.append(outputFilename)

            print "File created: ", outputFilename

        print pixelCount, "pixels written"

class ColorSafePdfFile:
    # All in inches
    printerDpi = 100.0 # Printed dots per inch, not directly related to ColorSafe dots.
    pageWidth = 8.5
    pageHeight = 11

    bottomBorder = 0.1
    leftBorder = 0.1
    rightBorder = 0.1
    topBorder = 0.2
    headerPadding = 0.1

    PdfExtension = "pdf"

    # TODO: Support an encoding mode that has accurate dpi
    def __init__(self, data, pageHeight = pageHeight, pageWidth = pageWidth, dotFillPixels = dotFillPixels, pixelsPerDot = pixelsPerDot, colorDepth = colorDepth, eccRate = eccRate, sectorHeight = sectorHeight, sectorWidth = sectorWidth, borderSize = borderSize, gapSize = gapSize, filename = filename, fileExtension = fileExtension):

        self.pixelsPerDot = pixelsPerDot

        self.getPageProperties()

        # TODO: Get images ver/hor border adds, based on unused pixels leftover from sector divide, for centering
        self.csImages = ColorSafeImageFiles(data, self.fullWorkingHeightPixels, self.fullWorkingWidthPixels, dotFillPixels = dotFillPixels, pixelsPerDot = pixelsPerDot, colorDepth = colorDepth, eccRate = eccRate, sectorHeight = sectorHeight, sectorWidth = sectorWidth, borderSize = borderSize, gapSize = gapSize, filename = filename, fileExtension = fileExtension)

        self.getPdfFile()

    def getPageProperties(self):
        # Full working height, including all regions outside of borders
        fullWorkingHeightInches = self.pageHeight - self.topBorder - self.bottomBorder - self.headerPadding
        fullWorkingWidthInches = self.pageWidth - self.leftBorder - self.rightBorder
        self.fullWorkingHeightPixels = int( fullWorkingHeightInches * self.printerDpi * self.pixelsPerDot )
        self.fullWorkingWidthPixels = int( fullWorkingWidthInches * self.printerDpi * self.pixelsPerDot )

    def getPdfFile(self):
        headerPaddingPixels = self.headerPadding * self.printerDpi * self.pixelsPerDot
        pdfWidth = self.csImages.workingWidthPixels
        pdfHeight = self.csImages.workingHeightPixels+headerPaddingPixels
        headerYVal = pdfHeight - headerPaddingPixels/2

        c = canvas.Canvas(OutputFilenameDefault + "." + self.PdfExtension)
        c.setPageSize((pdfWidth,pdfHeight))

        # Draw without borders; printing program should add its own padding.
        for pgi,csImage in enumerate(self.csImages.images):
            c.drawImage(csImage, 0, 0)

            # TODO: Use font size
            headerString = "Page " + str(pgi)
            c.drawString(0, headerYVal, headerString)

            # Move to next page
            c.showPage()

        c.save()

class ColorSafeEncoder:
    def __init__(self, inputFile):
        fileHandle = open(inputFile)

        mm = mmap.mmap(fileHandle.fileno(), 0, prot=mmap.PROT_READ)

        pdfFile = ColorSafePdfFile(mm)

        fileHandle.close()


from PIL import Image
from reportlab.pdfgen import canvas
import mmap
import os

from colorsafe import defaults
from colorsafe.encoder.csimages_encoder import ColorSafeImagesEncoder


class ColorSafePdfFile:
    # All in inches
    # Printed dots per inch, not directly related to ColorSafe dots.
    printerDpi = 100.0
    pageWidth = 8.5
    pageHeight = 11

    borderTop = 0.2
    borderBottom = 0.1
    borderLeft = 0.1
    borderRight = 0.1
    headerPadding = 0.1

    ImageExtension = "png"
    PdfExtension = "pdf"
    FilenameFormat = "%s_%d.%s"

    def __init__(self,
                 data,
                 pageHeight=pageHeight,
                 pageWidth=pageWidth,
                 borderTop=borderTop,
                 borderBottom=borderBottom,
                 borderLeft=borderLeft,
                 borderRight=borderRight,
                 dotFillPixels=defaults.dotFillPixels,
                 pixelsPerDot=defaults.pixelsPerDot,
                 colorDepth=defaults.colorDepth,
                 eccRate=defaults.eccRate,
                 sectorHeight=defaults.sectorHeight,
                 sectorWidth=defaults.sectorWidth,
                 borderSize=defaults.borderSize,
                 gapSize=defaults.gapSize,
                 filename=defaults.filename,
                 printerDpi=printerDpi,
                 fileExtension=defaults.fileExtension,
                 outPath="",
                 saveImages=False,
                 noPdf=False):

        self.printerDpi = printerDpi
        self.pageHeight = pageHeight
        self.pageWidth = pageWidth
        self.borderTop = borderTop
        self.borderBottom = borderBottom
        self.borderLeft = borderLeft
        self.borderRight = borderRight

        self.pixelsPerDot = pixelsPerDot
        self.outPath = outPath

        self.getPageProperties()

        # TODO: Get images ver/hor border adds, based on unused pixels leftover
        # from sector divide, for centering
        csImages = ColorSafeImagesEncoder(data,
                                          self.fullWorkingHeightPixels,
                                          self.fullWorkingWidthPixels,
                                          dotFillPixels,
                                          pixelsPerDot,
                                          colorDepth,
                                          eccRate,
                                          sectorHeight,
                                          sectorWidth,
                                          borderSize,
                                          gapSize,
                                          filename,
                                          fileExtension)

        print "Max data per page:", str(csImages.csFile.maxData / 1000), "kB"

        grayscale = colorDepth == 1

        imageFilenames = list()
        for i, image in enumerate(csImages.images):
            outputFilename = os.path.join(
                outPath, self.FilenameFormat %
                (csImages.filename, i, self.ImageExtension))
            imageFilenames.append(outputFilename)

            colorMode = 'L' if grayscale else 'RGB'

            imagePIL = Image.new(colorMode, (len(image[0]), len(image)), "white")
            pixelsPIL = imagePIL.load()  # create the pixel map
            for y, row in enumerate(image):
                for x, dot in enumerate(row):
                    if (grayscale):
                        pixelsPIL[x, y] = (int(dot[0] * 255))
                    else:
                        pixelsPIL[x, y] = (int(dot[0] * 255),
                                           int(dot[1] * 255), int(dot[2] * 255))

            imagePIL.save(outputFilename)

        self.csImages = csImages

        if not noPdf:
            self.getPdfFile()

        for f in imageFilenames:
            if not saveImages:
                os.remove(f)
            else:
                print "Saved", f

    def getPageProperties(self):
        # Full working height, including all regions outside of borders
        fullWorkingHeightInches = self.pageHeight - \
            self.borderTop - self.borderBottom - self.headerPadding
        fullWorkingWidthInches = self.pageWidth - self.borderLeft - self.borderRight
        self.fullWorkingHeightPixels = int(
            fullWorkingHeightInches *
            self.printerDpi *
            self.pixelsPerDot)
        self.fullWorkingWidthPixels = int(
            fullWorkingWidthInches *
            self.printerDpi *
            self.pixelsPerDot)

    def getPdfFile(self):
        headerPaddingPixels = self.headerPadding * self.printerDpi * self.pixelsPerDot
        pdfWidth = self.csImages.workingWidthPixels
        pdfHeight = self.csImages.workingHeightPixels + headerPaddingPixels
        headerYVal = pdfHeight - headerPaddingPixels / 2

        pdfFilename = os.path.join(
            self.outPath,
            self.csImages.filename +
            "." +
            self.PdfExtension)
        c = canvas.Canvas(pdfFilename)
        c.setPageSize((pdfWidth, pdfHeight))

        # Draw without borders; printing program should add its own padding.
        for i, csImage in enumerate(self.csImages.images):
            imgFilename = self.FilenameFormat % (
                self.csImages.filename, i, self.ImageExtension)
            c.drawImage(imgFilename, 0, 0)

            # TODO: Use font size
            headerString = "Page " + str(i + 1)
            c.drawString(0, headerYVal, headerString)

            # Move to next page
            c.showPage()

        print "Saved", pdfFilename
        c.save()


class ColorSafeEncoder:
    def __init__(
            self,
            filename,
            colorDepth,
            pageHeight,
            pageWidth,
            borderTop,
            borderBottom,
            borderLeft,
            borderRight,
            dotFillPixels,
            pixelsPerDot,
            printerDpi,
            outPath,
            saveImages,
            noPdf):
        fileHandle = open(filename)

        mm = mmap.mmap(fileHandle.fileno(), 0, prot=mmap.PROT_READ)

        pdfFile = ColorSafePdfFile(mm,
                                   colorDepth=colorDepth,
                                   pageHeight=pageHeight,
                                   pageWidth=pageWidth,
                                   borderTop=borderTop,
                                   borderBottom=borderBottom,
                                   borderLeft=borderLeft,
                                   borderRight=borderRight,
                                   dotFillPixels=dotFillPixels,
                                   pixelsPerDot=pixelsPerDot,
                                   printerDpi=printerDpi,
                                   outPath=outPath,
                                   saveImages=saveImages,
                                   noPdf=noPdf)

        fileHandle.close()

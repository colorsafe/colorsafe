import math

from colorsafe import defaults
from colorsafe.csdatastructures import constants
from colorsafe.csdatastructures import ColorSafeImages
from colorsafe.encoder.csencoder import ColorSafeFileEncoder


class ColorSafeImagesEncoder(ColorSafeImages):
    """A collection of saved ColorSafeFile objects, as images of working regions without outside borders or headers
    """

    def __init__(self,
                 data,
                 full_working_height_pixels,
                 full_working_width_pixels,
                 dot_fill_pixels=defaults.dotFillPixels,
                 pixels_per_dot=defaults.pixelsPerDot,
                 color_depth=defaults.colorDepth,
                 ecc_rate=defaults.eccRate,
                 sector_height=defaults.sectorHeight,
                 sector_width=defaults.sectorWidth,
                 border_size=defaults.borderSize,
                 gap_size=defaults.gapSize,
                 filename=defaults.filename,
                 file_extension=defaults.fileExtension):
        """Convert ColorSafeFile into a list of formatted images, with borders and gaps, and scaled properly.
        """

        if not color_depth or color_depth < 0 or color_depth > constants.ColorDepthMax:
            color_depth = defaults.colorDepth

        if dot_fill_pixels < 0:
            dot_fill_pixels = defaults.dotFillPixels

        if pixels_per_dot < 0:
            pixels_per_dot = defaults.pixelsPerDot

        self.fullWorkingHeightPixels = full_working_height_pixels
        self.fullWorkingWidthPixels = full_working_width_pixels
        self.dotFillPixels = dot_fill_pixels
        self.pixelsPerDot = pixels_per_dot
        self.colorDepth = color_depth
        self.eccRate = ecc_rate
        self.sectorHeight = sector_height
        self.sectorWidth = sector_width
        self.borderSize = border_size
        self.gapSize = gap_size
        self.filename = filename
        self.fileExtension = file_extension

        # Calculate sector count based on maximum allowable in working region
        self.scale = self.pixelsPerDot

        # An integer representing the number of non-colored pixels representing
        # a dot for respective sides.
        dotWhitespace = self.pixelsPerDot - self.dotFillPixels
        self.dotWhitespaceTop = int(math.floor(float(dotWhitespace) / 2))
        self.dotWhitespaceBottom = int(math.ceil(float(dotWhitespace) / 2))
        self.dotWhitespaceLeft = int(math.floor(float(dotWhitespace) / 2))
        self.dotWhitespaceRight = int(math.ceil(float(dotWhitespace) / 2))

        # In dots, excluding overlapping borders
        self.sectorHeightTotal = self.sectorHeight + self.borderSize + 2 * self.gapSize
        self.sectorWidthTotal = self.sectorWidth + self.borderSize + 2 * self.gapSize

        # Remove single extra non-overlapping border at the bottom-right of
        # working region
        self.sectorsVertical = float(
            self.fullWorkingHeightPixels -
            self.scale *
            self.borderSize)
        self.sectorsVertical /= self.scale * self.sectorHeightTotal

        self.sectorsHorizontal = float(
            self.fullWorkingWidthPixels -
            self.scale *
            self.borderSize)
        self.sectorsHorizontal /= self.scale * self.sectorWidthTotal

        self.sectorsVertical = int(math.floor(self.sectorsVertical))
        self.sectorsHorizontal = int(math.floor(self.sectorsHorizontal))

        self.workingHeightPixels = (
            self.sectorsVertical * self.sectorHeightTotal + self.borderSize) * self.scale
        self.workingWidthPixels = (
            self.sectorsHorizontal * self.sectorWidthTotal + self.borderSize) * self.scale

        self.csFile = ColorSafeFileEncoder(data,
                                           self.sectorsVertical,
                                           self.sectorsHorizontal,
                                           self.colorDepth,
                                           self.eccRate,
                                           self.sectorHeight,
                                           self.sectorWidth,
                                           self.filename,
                                           self.fileExtension)

        self.images = self.color_safe_file_to_images(self.csFile)

    def color_safe_file_to_images(self, csFile):
        images = list()

        for page in csFile.pages:
            pixels = list()
            for row in range(self.workingHeightPixels):
                row = list()
                for column in range(self.workingWidthPixels):
                    row.append(constants.ColorWhite)
                pixels.append(row)

            for si, sector in enumerate(page.sectors):
                sx = si % page.sectorsHorizontal
                sy = si / page.sectorsHorizontal

                gapHor = self.gapSize * (2 * sx + 1)
                borderHor = self.borderSize * (sx + 1)

                gapVer = self.gapSize * (2 * sy + 1)
                borderVer = self.borderSize * (sy + 1)

                startHor = sx * page.sectorWidth + gapHor + borderHor
                startVer = sy * page.sectorHeight + gapVer + borderVer

                for ri, row in enumerate(sector.dataRows + sector.eccRows):
                    for dbi, dotByte in enumerate(row.dotBytes):
                        for di, dot in enumerate(dotByte.dots):
                            x = startHor + constants.ByteSize * dbi + di
                            y = startVer + ri

                            x *= self.scale
                            y *= self.scale

                            pval = dot.getChannels()

                            for xi in range(
                                    self.dotWhitespaceLeft,
                                    self.pixelsPerDot -
                                    self.dotWhitespaceRight):
                                for yi in range(
                                        self.dotWhitespaceBottom,
                                        self.pixelsPerDot - self.dotWhitespaceTop):
                                    pixels[y + yi][x + xi] = pval

                borderStartHor = startHor - self.gapSize - self.borderSize
                borderStartVer = startVer - self.gapSize - self.borderSize
                borderEndHor = borderStartHor + self.sectorWidthTotal
                borderEndVer = borderStartVer + self.sectorHeightTotal

                # TODO: Fix missing bottom-right-most pixel
                # Draw vertical borders
                for xscale in range(0, self.scale):
                    for bx in [
                            self.scale * borderStartHor + xscale,
                            self.scale * borderEndHor + xscale]:
                        for by in range(
                                self.scale * borderStartVer,
                                self.scale * borderEndVer):
                            pixels[by][bx] = defaults.borderColor

                # Draw horizontal borders
                for yscale in range(0, self.scale):
                    for bx in range(
                            self.scale * borderStartHor,
                            self.scale * borderEndHor):
                        for by in [
                                self.scale * borderStartVer + yscale,
                                self.scale * borderEndVer + yscale]:
                            pixels[by][bx] = defaults.borderColor

            images.append(pixels)

        return images

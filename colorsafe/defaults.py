from colorsafe import constants

colorDepth = 1
eccRate = 0.2

# All in dots
sectorHeight = 64
sectorWidth = 64
borderSize = 1
gapSize = 1  # TODO: Consider splitting to left,right,top,bottom to remove 1&2 numbers from various functions

# An integer representing the number of pixels colored in per dot per side.
dotFillPixels = 3

# An integer representing the number of pixels representing a dot per side.
# Warning: Encoding processing time increases proportionally to this value
pixelsPerDot = 4

filename = "out"
fileExtension = "txt"

borderColor = constants.ColorBlack

__version__ = '0.1.0.dev6'

ByteSize = 8

Byte00 = 0b00000000
Byte11 = 0b11111111
Byte55 = 0b01010101
ByteAA = 0b10101010
MagicByte = 0b10011001

ColorChannels = 3  # R, G, B, and all secondary combinations
ColorChannels1 = 1  # Shades of gray only
ColorChannels2 = 2  # Primary subtractive colors, CMYK

ColorDepthMax = 2 ** ByteSize - 1

ColorValueMax = 2 ** ByteSize - 1
ColorBlack = (0, 0, 0)
ColorWhite = (ColorValueMax, ColorValueMax, ColorValueMax)

DataMode = 1
ECCMode = 1

MagicRowHeight = 1

MajorVersion = 0
MinorVersion = 1
RevisionVersion = 0

RSBlockSizeMax = 2 ** ByteSize - 1

TotalPagesMaxBytes = 8  # 8 bytes per page maximum for the total-pages field

MaxSkew = 5
MaxSkewPerc = 0.002

DefaultThresholdWeight = 0.5

HalfPixel = 0.5

from colorsafe.constants import MagicByte, DefaultThresholdWeight

from colorsafe import constants
from colorsafe.csdatastructures import ColorChannels, Sector
from colorsafe.decoder.csdecoder import DotDecoder, DotByteDecoder, DotRowDecoder
from colorsafe.encoder.csencoder import DotEncoder, DotRowEncoder, DotByteEncoder

# Dot


def test_dot_encode_colordepth1():
    dot = DotEncoder([1])
    assert dot.getChannels() == (1.0, 1.0, 1.0)

    dot = DotEncoder([0])
    assert dot.getChannels() == (0.0, 0.0, 0.0)


def test_dot_encode_colordepth2():
    # White
    dot = DotEncoder([0, 0])
    assert dot.getChannels() == (1.0, 1.0, 1.0)

    # Magenta
    dot = DotEncoder([0, 1])
    assert dot.getChannels() == (1.0, 0.0, 1.0)

    # Cyan
    dot = DotEncoder([1, 0])
    assert dot.getChannels() == (0, 1.0, 1.0)

    # Yellow
    dot = DotEncoder([1, 1])
    assert dot.getChannels() == (1.0, 1.0, 0)

    dot = DotEncoder([1, 1, 0, 0])
    assert dot.getChannels() == (0, 1.0 / 3.0, 1.0 / 3.0)


def test_dot_encode_colordepth3():
    dot = DotEncoder([0, 0, 0])
    assert dot.getChannels() == (0.0, 0.0, 0.0)

    dot = DotEncoder([1, 0, 1])
    assert dot.getChannels() == (1.0, 0.0, 1.0)

    dot = DotEncoder([1, 1, 1])
    assert dot.getChannels() == (1.0, 1.0, 1.0)

    dot = DotEncoder([1, 0, 0, 0, 1, 1])
    assert dot.getChannels() == (85.0 / constants.ColorDepthMax, 0, 1.0)

    dot = DotEncoder([1, 1, 1, 1, 1, 1, 1, 1, 1])
    assert dot.getChannels() == (1.0, 1.0, 1.0)


def test_dot_decode_colordepth1():
    dot = DotDecoder(ColorChannels(1.0, 1.0, 1.0), 1, DefaultThresholdWeight)
    assert dot.bitList == [1]

    dot = DotDecoder(ColorChannels(0.0, 0.0, 0.0), 1, DefaultThresholdWeight)
    assert dot.bitList == [0]

    dot = DotDecoder(ColorChannels(0.25, 0.25, 0.25), 1, 0.5)
    assert dot.bitList == [0]

    dot = DotDecoder(ColorChannels(0.95, 0.95, 0.95), 1, 0.5)
    assert dot.bitList == [1]

    dot = DotDecoder(ColorChannels(0.93, 0.95, 0.91), 1, 0.5)
    assert dot.bitList == [1]

    dot = DotDecoder(ColorChannels(0.05, 0.1, 0.07), 1, 0.5)
    assert dot.bitList == [0]

    dot = DotDecoder(ColorChannels(0.05, 0.0, 0.0), 1, 0.5)
    assert dot.bitList == [0]

    dot = DotDecoder(ColorChannels(1.0, 1.0, 0.9), 1, 0.5)
    assert dot.bitList == [1]


def test_dot_decode_colordepth2():
    dot = DotDecoder(ColorChannels(1.0, 1.0, 1.0), 2, DefaultThresholdWeight)
    assert dot.bitList == [0, 0]

    dot = DotDecoder(ColorChannels(0.0, 1.0, 1.0), 2, DefaultThresholdWeight)
    assert dot.bitList == [1, 0]

    dot = DotDecoder(ColorChannels(1.0, 1.0, 0.0), 2, DefaultThresholdWeight)
    assert dot.bitList == [1, 1]

    dot = DotDecoder(ColorChannels(0, 63.0 / constants.ColorDepthMax, 63.0 / constants.ColorDepthMax), 4, DefaultThresholdWeight)
    assert dot.bitList == [1, 1, 0, 0]


def test_dot_decode_colordepth3():
    dot = DotDecoder(ColorChannels(0, 0, 0), 3, DefaultThresholdWeight)
    assert dot.bitList == [0, 0, 0]

    dot = DotDecoder(ColorChannels(1.0, 0, 1.0), 3, DefaultThresholdWeight)
    assert dot.bitList == [1, 0, 1]

    dot = DotDecoder(ColorChannels(1.0, 1.0, 1.0), 3, DefaultThresholdWeight)
    assert dot.bitList == [1, 1, 1]

    dot = DotDecoder(ColorChannels(1.0 / 3.0, 0.0, 1.0), 6, DefaultThresholdWeight)
    assert dot.bitList == [1, 0, 0, 0, 1, 1]

    dot = DotDecoder(ColorChannels(1.0, 1.0, 1.0), 9, DefaultThresholdWeight)
    assert dot.bitList == [1, 1, 1, 1, 1, 1, 1, 1, 1]

# DotByte


def test_dotByte_encode():
    dotByte = DotByteEncoder([0xFF], 1)
    assert len(dotByte.dots) == constants.ByteSize
    assert dotByte.dots[0].getChannels() == (1.0, 1.0, 1.0)

    dotByte = DotByteEncoder([0xFF, 0xFF], 2)
    assert len(dotByte.dots) == constants.ByteSize
    assert dotByte.dots[0].getChannels() == (1.0, 1.0, 0.0)

    dotByte = DotByteEncoder([0xFF, 0xFF, 0xFF], 3)
    assert len(dotByte.dots) == constants.ByteSize
    assert dotByte.dots[0].getChannels() == (1.0, 1.0, 1.0)

    dotByte = DotByteEncoder([0xFF, 0xFF, 0xFF], 6)
    assert len(dotByte.dots) == constants.ByteSize
    assert dotByte.dots[0].getChannels() == (1.0, 1.0 / 3.0, 0.0)


def test_dotByte_decode():
    c = ColorChannels(1.0, 1.0, 1.0)
    dotByte = DotByteDecoder([c] * constants.ByteSize, 1, DefaultThresholdWeight)
    assert dotByte.bytesList == [0xFF]

    c = ColorChannels(1.0, 1.0, 0.0)
    dotByte = DotByteDecoder([c] * constants.ByteSize, 2, DefaultThresholdWeight)
    assert dotByte.bytesList == [0xFF, 0xFF]

    c = ColorChannels(1.0, 1.0, 1.0)
    dotByte = DotByteDecoder([c] * constants.ByteSize, 3, DefaultThresholdWeight)
    assert dotByte.bytesList == [0xFF, 0xFF, 0xFF]

    c = ColorChannels(1.0, 1.0 / 3.0, 0.0)
    dotByte = DotByteDecoder([c] * constants.ByteSize, 6, DefaultThresholdWeight)
    assert dotByte.bytesList == [0xFF, 0xFF, 0xFF, 0x00, 0x00, 0x00]

    c = [
        ColorChannels(0, 0, 0),
        ColorChannels(0, 0, 0),
        ColorChannels(1, 1, 1),
        ColorChannels(1, 1, 1),
    ]
    dotByte = DotByteDecoder(c * 2, 1, DefaultThresholdWeight)
    assert dotByte.bytesList == [0b11001100]

    # Blurred image
    c = [
        ColorChannels(0.05, 0.05, 0.05),
        ColorChannels(0.05, 0.05, 0.05),
        ColorChannels(0.95, 0.95, 0.95),
        ColorChannels(0.95, 0.95, 0.95),
    ]
    dotByte = DotByteDecoder(c * 2, 1, DefaultThresholdWeight)
    assert dotByte.bytesList == [0b11001100]


# DotRow


def test_dotRow_encode():
    dotRow = DotRowEncoder([85, 170, 85, 170], 2, 16, 0, False)
    assert dotRow.dotBytes[0].dots[0].getChannels() == (0.0, 1.0, 1.0)

    dotRow = DotRowEncoder([85, 170, 85, 170], 2, 16, 0, True)
    assert dotRow.dotBytes[0].dots[0].getChannels() == (1.0, 0.0, 1.0)


def test_dotRow_decode():
    c = ColorChannels(1.0, 0.0, 1.0)
    dotRow = DotRowDecoder([c] * 16, 2, 16, 0, 0.5, False)
    assert dotRow.bytesList == [0, 255, 0, 255]

    c = ColorChannels(0.9, 0.1, 0.9)
    dotRow = DotRowDecoder([c] * 16, 2, 16, 0, 0.5, False)
    assert dotRow.bytesList == [0, 255, 0, 255]

    c = [
        ColorChannels(0.0, 0.0, 0.0),
        ColorChannels(0.0, 0.0, 0.0),
        ColorChannels(1.0, 1.0, 1.0),
        ColorChannels(1.0, 1.0, 1.0),
    ]
    dotRow = DotRowDecoder(c * 4, 1, 16, 0, 0.5, True)
    assert dotRow.bytesList == [MagicByte, MagicByte]

    # Randomly blurred image
    c = [
        ColorChannels(0.05, 0.1, 0.07),
        ColorChannels(0.05, 0.0, 0.0),
        ColorChannels(1.0, 1.0, 0.9),
        ColorChannels(0.93, 0.95, 0.91),
    ]
    dotRow = DotRowDecoder(c * 4, 1, 16, 0, 0.5, True)
    assert dotRow.bytesList == [MagicByte, MagicByte]

    c = [
        ColorChannels(1.0, 1.0, 1.0),
        ColorChannels(0.0, 0.0, 0.0),
        ColorChannels(0.25, 0.25, 0.25),
        ColorChannels(1.0, 1.0, 1.0),
        ColorChannels(0.8, 0.8, 0.8),
        ColorChannels(0.0, 0.0, 0.0),
        ColorChannels(0.0, 0.0, 0.0),
        ColorChannels(0.0, 0.0, 0.0),
        ColorChannels(0.0, 0.0, 0.0),
        ColorChannels(0.8, 0.8, 0.8),
        ColorChannels(0.25, 0.25, 0.25),
        ColorChannels(1.0, 1.0, 1.0),
        ColorChannels(1.0, 1.0, 1.0),
        ColorChannels(0.75, 0.75, 0.75),
        ColorChannels(0.0, 0.0, 0.0),
        ColorChannels(0.25, 0.25, 0.25)
    ]
    dotRow = DotRowDecoder(c, 1, 16, 0, 0.5, True)
    assert dotRow.bytesList == [ord('L'), ord('o')]

    c = [
        ColorChannels(0.4375, 0.4375, 0.4375),
        ColorChannels(1.0, 1.0, 1.0),
        ColorChannels(0.8125, 0.8125, 0.8125),
        ColorChannels(0.1875, 0.1875, 0.1875),
        ColorChannels(0.0, 0.0, 0.0),
        ColorChannels(0.0, 0.0, 0.0),
        ColorChannels(0.0, 0.0, 0.0),
        ColorChannels(0.0, 0.0, 0.0),
        ColorChannels(0.0, 0.0, 0.0),
        ColorChannels(0.0, 0.0, 0.0),
        ColorChannels(0.0, 0.0, 0.0),
        ColorChannels(0.25, 0.25, 0.25),
        ColorChannels(1.0, 1.0, 1.0),
        ColorChannels(0.75, 0.75, 0.75),
        ColorChannels(0.0, 0.0, 0.0),
        ColorChannels(0.25, 0.25, 0.25)
    ]
    dotRow = DotRowDecoder(c * 4, 1, 16, 0, 0.5, True)
    assert dotRow.bytesList == [ord('S'), ord('e')]

    # Color depth 2
    c = [
        ColorChannels(1.0, 0.0, 1.0),
        ColorChannels(0.0, 1.0, 1.0),
        ColorChannels(1.0, 1.0, 1.0),
        ColorChannels(1.0, 0.0, 1.0),
        ColorChannels(1.0, 0.0, 1.0),
        ColorChannels(1.0, 1.0, 1.0),
        ColorChannels(1.0, 1.0, 1.0),
        ColorChannels(1.0, 1.0, 1.0),
        ColorChannels(0.0, 1.0, 1.0),
        ColorChannels(0.0, 1.0, 1.0),
        ColorChannels(0.0, 1.0, 1.0),
        ColorChannels(1.0, 1.0, 0.0),
        ColorChannels(1.0, 0.0, 1.0),
        ColorChannels(1.0, 1.0, 1.0),
        ColorChannels(1.0, 1.0, 1.0),
        ColorChannels(1.0, 1.0, 1.0)]

    dotRow = DotRowDecoder(c, 2, 16, 0, 0.5, True)
    assert dotRow.bytesList == [ord('W'), ord('L'), ord('Z'), ord('M')]


def test_sector_get_block_sizes_color_1():
    color_depth = 1
    dataRowCount, eccRowCount, rsBlockSizes, dataBlockSizes, eccBlockSizes = \
        Sector.get_block_sizes(64, 64, color_depth, 0.2)

    assert dataRowCount == 52
    assert eccRowCount == 11
    assert sum(rsBlockSizes) == (dataRowCount + eccRowCount) * 64 * 1 / 8
    assert sum(dataBlockSizes) == dataRowCount * 64 * 1 / 8
    assert sum(eccBlockSizes) == eccRowCount * 64 * 1 / 8

    assert rsBlockSizes == [252, 252]
    assert dataBlockSizes == [208, 208]
    assert eccBlockSizes == [44, 44]


def test_sector_get_block_sizes_color_2():
    color_depth = 2
    dataRowCount, eccRowCount, rsBlockSizes, dataBlockSizes, eccBlockSizes = \
        Sector.get_block_sizes(64, 64, color_depth, 0.2)

    assert dataRowCount == 52
    assert eccRowCount == 11
    assert sum(rsBlockSizes) == (dataRowCount + eccRowCount) * 64 * color_depth / 8
    assert sum(dataBlockSizes) == dataRowCount * 64 * color_depth / 8
    assert sum(eccBlockSizes) == eccRowCount * 64 * color_depth / 8

    assert rsBlockSizes == [255, 255, 249, 249]
    assert dataBlockSizes == [210, 210, 206, 206]
    assert eccBlockSizes == [45, 45, 43, 43]


def test_sector_get_block_sizes_color_3():
    color_depth = 3
    dataRowCount, eccRowCount, rsBlockSizes, dataBlockSizes, eccBlockSizes = \
        Sector.get_block_sizes(64, 64, color_depth, 0.2)

    assert dataRowCount == 52
    assert eccRowCount == 11
    assert sum(rsBlockSizes) == (dataRowCount + eccRowCount) * 64 * color_depth / 8
    assert sum(dataBlockSizes) == dataRowCount * 64 * color_depth / 8
    assert sum(eccBlockSizes) == eccRowCount * 64 * color_depth / 8

    assert rsBlockSizes == [255, 255, 255, 255, 246, 246]
    assert dataBlockSizes == [210, 210, 210, 210, 204, 204]
    assert eccBlockSizes == [45, 45, 45, 45, 42, 42]

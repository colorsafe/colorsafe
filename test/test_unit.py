from colorsafe.colorsafe import Constants, ColorChannels, Dot, DotByte, DotRow

MaxColorVal = 255

# Dot
def test_dot_encode_colordepth1():
    dot = Dot()
    dot.encode([1]) 
    assert dot.getChannels() == (1.0,1.0,1.0)

    dot.encode([0]) 
    assert dot.getChannels() == (0.0,0.0,0.0)

def test_dot_encode_colordepth2():
    dot = Dot()

    # White
    dot.encode([0,0]) 
    assert dot.getChannels() == (1.0,1.0,1.0)

    # Magenta
    dot.encode([0,1])
    assert dot.getChannels() == (1.0,0.0,1.0)

    # Cyan
    dot.encode([1,0]) 
    assert dot.getChannels() == (0,1.0,1.0)

    # Yellow
    dot.encode([1,1])
    assert dot.getChannels() == (1.0,1.0,0)

    dot.encode([1,1, 0,0])
    assert dot.getChannels() == (0, 1.0/3.0, 1.0/3.0)

def test_dot_encode_colordepth3():
    dot = Dot()

    dot.encode([0,0,0])
    assert dot.getChannels() == (0.0,0.0,0.0)

    dot.encode([1,0,1])
    assert dot.getChannels() == (1.0,0.0,1.0)

    dot.encode([1,1,1])
    assert dot.getChannels() == (1.0,1.0,1.0)

    dot.encode([1,0, 0,0, 1,1])
    assert dot.getChannels() == (85.0/MaxColorVal,0,1.0)

    dot.encode([1,1,1, 1,1,1, 1,1,1])
    assert dot.getChannels() == (1.0,1.0,1.0)

def test_dot_decode_colordepth1():
    dot = Dot()

    dot.decode(ColorChannels(1.0,1.0,1.0),1)
    assert dot.bitList == [1]

    dot.decode(ColorChannels(0.0,0.0,0.0),1)
    assert dot.bitList == [0]

    dot.decode(ColorChannels(94.0/MaxColorVal,94.0/MaxColorVal,94.0/MaxColorVal),7)
    assert dot.bitList == [1,1,1,1,0,1,0]

def test_dot_decode_colordepth2():
    dot = Dot()

    dot.decode(ColorChannels(1.0,1.0,1.0),2)
    assert dot.bitList == [0,0]

    dot.decode(ColorChannels(0.0,1.0,1.0),2)
    assert dot.bitList == [1,0]

    dot.decode(ColorChannels(1.0,1.0,0.0),2)
    assert dot.bitList == [1,1]

    dot.decode(ColorChannels(0,63.0/MaxColorVal,63.0/MaxColorVal),4)
    assert dot.bitList == [1,1, 0,0]

def test_dot_decode_colordepth3():
    dot = Dot()

    dot.decode(ColorChannels(0,0,0),3)
    assert dot.bitList == [0,0,0]

    dot.decode(ColorChannels(1.0,0,1.0),3)
    assert dot.bitList == [1,0,1]

    dot.decode(ColorChannels(1.0,1.0,1.0),3)
    assert dot.bitList == [1,1,1]

    dot.decode(ColorChannels(1.0/3.0,0.0,1.0),6)
    assert dot.bitList == [1,0, 0,0, 1,1]

    dot.decode(ColorChannels(1.0,1.0,1.0),9)
    assert dot.bitList == [1,1,1, 1,1,1, 1,1,1]

# DotByte
def test_dotByte_encode():
    dotByte = DotByte()   

    dotByte.encode([0xFF],1)
    assert len(dotByte.dots) == Constants.ByteSize
    assert dotByte.dots[0].getChannels() == (1.0,1.0,1.0)

    dotByte.encode([0xFF,0xFF],2)
    assert len(dotByte.dots) == Constants.ByteSize
    assert dotByte.dots[0].getChannels() == (1.0,1.0,0.0)

    dotByte.encode([0xFF,0xFF,0xFF],3)
    assert len(dotByte.dots) == Constants.ByteSize
    assert dotByte.dots[0].getChannels() == (1.0,1.0,1.0)

    dotByte.encode([0xFF,0xFF,0xFF],6)
    assert len(dotByte.dots) == Constants.ByteSize
    assert dotByte.dots[0].getChannels() == (1.0, 1.0/3.0, 0.0)

def test_dotByte_decode():
    dotByte = DotByte()   
    dot = Dot()

    c = ColorChannels(1.0,1.0,1.0)
    dotByte.decode([c]*Constants.ByteSize, 1)
    assert dotByte.bytesList == [0xFF]

    c = ColorChannels(1.0,1.0,0.0)
    dotByte.decode([c]*Constants.ByteSize, 2)
    assert dotByte.bytesList == [0xFF,0xFF]

    c = ColorChannels(1.0,1.0,1.0)
    dotByte.decode([c]*Constants.ByteSize, 3)
    assert dotByte.bytesList == [0xFF,0xFF,0xFF]

    c = ColorChannels(1.0,1.0/3.0,0.0)
    dotByte.decode([c]*Constants.ByteSize, 6)
    assert dotByte.bytesList == [0xFF,0xFF,0xFF,0x00,0x00,0x00]

# DotRow
def test_dotRow_encode():
    dotRow = DotRow()

    dotRow.encode([85,170,85,170],2,16,0,False)
    assert dotRow.dotBytes[0].dots[0].getChannels() == (0.0,1.0,1.0)

    dotRow.encode([85,170,85,170],2,16,0,True)
    assert dotRow.dotBytes[0].dots[0].getChannels() == (1.0,0.0,1.0)

def test_dotRow_decode():
    dotRow = DotRow()

    c = ColorChannels(1.0,0.0,1.0)
    data = dotRow.decode([c]*16,2,16,0,False)
    assert data == [85,170,85,170]


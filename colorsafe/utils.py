def average(l):
    return sum(l) / len(l)


def binaryListToVal(l):
    """Takes a list of binary values, return an int corresponding to their value.
    """
    place = 1
    val = 0
    for i in l:
        val += place * i
        place = place << 1
    return val


def binaryListToFloat(l):
    """Takes a list of binary values, returns a float corresponding to their fractional value.
    """
    f = float(binaryListToVal(l)) / ((1 << len(l)) - 1)
    return f


def floatToBinaryList(f, bits):
    """Takes a float f, returns a list of binary values with a length of bits.
    """
    num = int(round(float(f) * ((1 << bits) - 1)))

    ret = list()
    for i in range(bits):
        ret.append(num >> i & 1)

    return ret


def intToBinaryList(num, bits):
    """Takes an int, returns a list of its binary number with length bits.
    """
    ret = list()

    for i in range(bits):
        ret.append(num >> i & 1)

    return ret


def lowThreshold(colorDepth):
    return (0.5 / (1 << colorDepth))


def highThreshold(colorDepth):
    return 1 - lowThreshold(colorDepth)
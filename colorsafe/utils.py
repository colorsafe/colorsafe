import operator


def average(l):
    return sum(l) / len(l)


def median(l):
    l_sort = sorted(l)
    index = (len(l) - 1) / 2

    return l_sort[index] if len(l) % 2 else average([l_sort[index], l_sort[index + 1]])


def threshold(val, high, low):
    if high == low:
        # TODO: Throw error
        pass

    return float(val - low) / (high - low)


def standard_deviation_squared(l):
    if len(l) < 2:
        # TODO: Throw error
        pass

    return sum(map(lambda x: (x - average(l)) ** 2, l)) / (len(l) - 1)


def weighted_standard_deviation_squared(l):
    if len(l) < 2:
        # TODO: Throw error
        pass

    w_sum = sum(map(lambda (x, w): w, l))
    l_avg = sum(map(lambda (x, w): x * w, l)) / w_sum
    return sum(map(lambda (x, w): ((x - l_avg) * w) ** 2, l)) / (w_sum ** 2)


def sum_of_squares(l):
    return sum(map(lambda x: x ** 2, l))


def remove_index(l, i):
    if len(l) < 0:
        # TODO: Throw error
        pass

    return l[:i] + l[(i+1):]


def flatten_lists(l):
    return reduce(operator.concat, l)


def list_to_starts_and_ends(l):
    """
    Return a tuple for each sequential pair of numbers.

    :param l: Input list, e.g. [0,1,2]
    :return: Output list, e.g. [(0, 1), (1, 2)]
    """
    out = list()
    reduce((lambda start, end: out.append((start, end)) or end), l)
    return out


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
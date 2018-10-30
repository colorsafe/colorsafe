import math
import os
import sys

from colorsafe.debugutils import draw_page

from colorsafe import exceptions, utils
from colorsafe.csdatastructures import ColorChannels


def get_normalized_channels_list(page, data_bounds, sector_height, sector_width, sectorNum, tmpdir):
    if tmpdir:
        tmpdir_bounds = os.path.join(str(tmpdir), "channels")
        try:
            os.mkdir(tmpdir_bounds)
        except OSError:
            pass
        tmpdir = tmpdir_bounds

    top, bottom, left, right = data_bounds

    channels_list = get_channels_list(page,
                                      top,
                                      bottom,
                                      left,
                                      right,
                                      sector_height,
                                      sector_width,
                                      sectorNum,
                                      tmpdir)

    normalized_channels_list = normalizeChannelsList(channels_list)

    if (tmpdir):
        f = open(os.path.join(tmpdir, "normalized_channels_" + str(sectorNum) + ".txt"), "w")
        for i in channels_list:
            f.write(str(i.getChannels()) + "\r")
        f.close()

    return normalized_channels_list


def get_channels_list(page, top, bottom, left, right, sector_height, sector_width, sector_num, tmpdir):
    # TODO: Use bilinear interpolation to get pixel values instead
    total_pixels_height = bottom - top + 1
    total_pixels_width = right - left + 1

    pixels_per_dot_width = float(total_pixels_height) / float(sector_height)
    pixels_per_dot_height = float(total_pixels_width) / float(sector_width)

    if tmpdir:
        all_pixels_and_weight = list()

    # For each dot in the sector
    channels_list = list()
    for y in range(sector_height):
        for x in range(sector_width):
            # Center halfway through the dot, y + 0.5 and x + 0.5
            y_center = pixels_per_dot_height * (y + 0.5) + top
            x_center = pixels_per_dot_width * (x + 0.5) + left

            y_min = y_center - pixels_per_dot_height / 2
            y_max = y_center + pixels_per_dot_height / 2
            x_min = x_center - pixels_per_dot_width / 2
            x_max = x_center + pixels_per_dot_width / 2

            pixels_and_weight = list()
            weight_sum = 0.0

            y_pixel_min = int(math.floor(y_min))
            y_pixel_max = int(math.floor(y_max))
            x_pixel_min = int(math.floor(x_min))
            x_pixel_max = int(math.floor(x_max))
            for y_pixel in range(y_pixel_min, y_pixel_max + 1):
                for x_pixel in range(x_pixel_min, x_pixel_max + 1):
                    pixel = page.get_pixel(y_pixel, x_pixel)

                    weight = 1.0

                    if y_pixel > y_max - 1:
                        weight *= (y_max % 1)

                    if y_pixel < y_min:
                        weight *= ((1 - y_min) % 1)

                    if x_pixel > x_max - 1:
                        weight *= (x_max % 1)

                    if x_pixel < x_min:
                        weight *= ((1 - x_min) % 1)

                    weight_sum += weight

                    pixels_and_weight.append((pixel, weight, y_pixel, x_pixel))

            if tmpdir:
                all_pixels_and_weight.append((y, x, pixels_and_weight))

            number_of_channels = len(page.get_pixel(0, 0))
            channels_sum = [0] * number_of_channels

            for pixel, weight, y_pixel, x_pixel in pixels_and_weight:
                for i in range(number_of_channels):
                    channels_sum[i] += pixel[i] * weight

            channels_avg = map(lambda i: i / weight_sum, channels_sum)
            channels_list.append(channels_avg)

    if tmpdir:
        f = open(os.path.join(tmpdir, "all_pixels_and_weight_" + str(sector_num) + ".txt"), "w")
        for y, x, pixels_and_weight in all_pixels_and_weight:
            f.write(str(y) + "," + str(x) + ":\r")
            for i in pixels_and_weight:
                f.write("    " + str(i) + "\r")
        f.close()

    color_channels_list = map(lambda i: ColorChannels(*i), channels_list)

    return color_channels_list


def normalizeChannelsList(channelsList):
    minVals = [1.0, 1.0, 1.0]
    maxVals = [0.0, 0.0, 0.0]

    # Get min and max vals for normalization
    for c in channelsList:
        vals = c.getChannels()
        for i, val in enumerate(vals):
            if val < minVals[i]:
                minVals[i] = val
            if val > maxVals[i]:
                maxVals[i] = val

    normalizedChannelsList = list()
    for i, channels in enumerate(channelsList):
        minVal = sum(minVals) / len(minVals)
        maxVal = sum(maxVals) / len(maxVals)

        if minVal == maxVal:
            raise exceptions.DecodingError("No variance detected in the data. All channels are the same color.")

        channels.subtractShade(minVal)
        channels.multiplyShade([1.0 / (maxVal - minVal)])

        normalizedChannelsList.append(channels)

    return normalizedChannelsList

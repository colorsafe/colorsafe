import math
import os

from colorsafe.debugutils import draw_page

from colorsafe import constants, exceptions
from colorsafe.csdatastructures import ColorChannels


def get_normalized_channels_list(page, data_bounds, sector_height, sector_width, page_num, sector_num, tmpdir):
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
                                      page_num,
                                      sector_num,
                                      tmpdir)

    normalized_channels_list = normalizeChannelsList(channels_list)

    if (tmpdir):
        f = open(os.path.join(tmpdir, "normalized_channels_" + str(page_num) + "_" + str(sector_num) + ".txt"), "w")
        for i in channels_list:
            f.write(str(i.getChannels()) + "\r")
        f.close()

    return normalized_channels_list


def get_pixels_and_weight(y, x, top, bottom, left, right, sector_height, sector_width, page):
    # TODO: Improve speed by not getting values that would add an insigificant amount to weight

    total_pixels_height = bottom - top + 1
    total_pixels_width = right - left + 1

    pixels_per_dot_width = float(total_pixels_width) / float(sector_width)
    pixels_per_dot_height = float(total_pixels_height) / float(sector_height)

    # Center halfway through the dot
    y_center = pixels_per_dot_height * (y + constants.HalfPixel) + top
    x_center = pixels_per_dot_width * (x + constants.HalfPixel) + left

    # Don't use coordinates outside the page bounds
    y_min = max(y_center - pixels_per_dot_height / 2, 0)
    y_max = min(y_center + pixels_per_dot_height / 2, page.height - 1)
    x_min = max(x_center - pixels_per_dot_width / 2, 0)
    x_max = min(x_center + pixels_per_dot_width / 2, page.width - 1)

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

            y_diff = abs(y_pixel + constants.HalfPixel - y_center)
            x_diff = abs(x_pixel + constants.HalfPixel - x_center)

            if y_diff > 0.5:
                weight *= 1 / ((2 * y_diff) ** 2)

            if x_diff > 0.5:
                weight *= 1 / ((2 * x_diff) ** 2)

            pixels_and_weight.append((pixel, weight, y_pixel, x_pixel))
            weight_sum += weight

    return pixels_and_weight, weight_sum, y_center, x_center


def get_channels_list(page, top, bottom, left, right, sector_height, sector_width, page_num, sector_num, tmpdir):
    # TODO: Would bilinear interpolation be more accurate?

    if tmpdir:
        all_pixels_and_weight = list()

    # For each dot in the sector
    channels_list = list()
    for y in range(sector_height):
        for x in range(sector_width):

            pixels_and_weight, weight_sum, y_center, x_center = get_pixels_and_weight(y,
                                                                                      x,
                                                                                      top,
                                                                                      bottom,
                                                                                      left,
                                                                                      right,
                                                                                      sector_height,
                                                                                      sector_width,
                                                                                      page)

            if tmpdir:
                all_pixels_and_weight.append((y, x, pixels_and_weight, y_center, x_center))

            number_of_channels = len(page.get_pixel(0, 0))
            channels_sum = [0] * number_of_channels

            for pixel, weight, y_pixel, x_pixel in pixels_and_weight:
                for i in range(number_of_channels):
                    channels_sum[i] += pixel[i] * weight

            channels_avg = map(lambda i: i / weight_sum, channels_sum)
            channels_list.append(channels_avg)

    if tmpdir:
        pixels_centers = list()
        pixels_colors = list()

        f = open(os.path.join(tmpdir, "all_pixels_and_weight_" + str(page_num) + "_" + str(sector_num) + ".txt"), "w")
        for y, x, pixels_and_weight, y_center, x_center in all_pixels_and_weight:
            f.write(str(y) + "," + str(x) + " (" + str(y_center) + "," + str(x_center) + "):\r")
            for i in pixels_and_weight:
                pixel, weight, y_pixel, x_pixel = i
                f.write("    " + str((y_pixel, x_pixel, pixel, weight)) + "\r")

                pixels_centers.append((int(math.floor(y_center)), int(math.floor(x_center))))
                if not x % 2 and not y % 2:
                    pixels_colors.append((y_pixel, x_pixel, (255 - int(weight * 255), 255, 255)))
        f.close()

        draw_page(page, tmpdir, "pixels_sampling_" + str(page_num) + "_" + str(sector_num), None, None, pixels_colors)
        draw_page(page, tmpdir, "pixels_centers_" + str(page_num) + "_" + str(sector_num), pixels_centers, None, None)

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

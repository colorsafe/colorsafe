import operator
import os
import sys
from copy import copy

from colorsafe.debugutils import draw_page

from colorsafe import constants, defaults, exceptions, utils
from colorsafe.decoder.csdecoder_getchannels import get_pixels_and_weight


def get_data_bounds(page, sector_height, sector_width, gap_size, page_num, tmpdir):
    if tmpdir:
        tmpdir_bounds = os.path.join(str(tmpdir), "bounds_" + str(page_num))
        os.mkdir(tmpdir_bounds)
        tmpdir = tmpdir_bounds

    bounds = get_bounds(page, tmpdir)

    data_bounds = list()
    debug_data_bounds = list()

    for top_temp, bottom_temp, left_temp, right_temp in bounds:

        height_per_dot = float(bottom_temp - top_temp + 1) / (sector_height + 2 * gap_size)
        width_per_dot = float(right_temp - left_temp + 1) / (sector_width + 2 * gap_size)

        if height_per_dot < 1.0 or width_per_dot < 1.0:
            raise exceptions.DecodingError("Image has less than 1.0x resolution, cannot get all dots.")

        data_bound = get_real_sector_data_boundaries(page,
                                                     height_per_dot,
                                                     width_per_dot,
                                                     top_temp,
                                                     bottom_temp,
                                                     left_temp,
                                                     right_temp)

        if (top_temp, bottom_temp, left_temp, right_temp) != data_bound:
            corrected_data_bound = correct_data_bound(data_bound, sector_height, sector_width, page)

            data_bounds.append(corrected_data_bound)
        else:
            # No data found within the bounds - this sector is most likely not valid or readable, so don't add it
            pass


        if tmpdir:
            top, bottom, left, right = data_bound
            debug_data_bounds.extend([(top, left), (top, right), (bottom, left), (bottom, right)])

    if tmpdir:
        draw_page(page, tmpdir, "data_bounds", tuple(debug_data_bounds), None)

    return data_bounds


def get_bounds(page, tmpdir):
    # Calculate vertical bounds first - more accurate since data typically extends the entire width of a page
    page_y_begin = find_beginning_or_ending(page, True, False)
    page_y_end = find_beginning_or_ending(page, True, True)
    page_x_begin = find_beginning_or_ending(page, False, False, page_y_begin, page_y_end)
    page_x_end = find_beginning_or_ending(page, False, True, page_y_begin, page_y_end)

    page_y_length = page_y_end - page_y_begin
    page_x_length = page_x_end - page_x_begin

    # TODO: Come up a better heuristic
    vertical_page_subdivisions = 4 + max(page_y_length - 128, 0) / 128
    horizontal_page_subdivisions = 4 + max(page_x_length - 128, 0) / 128

    horizontal_sub_borders_all = list()
    for y_sub in range(vertical_page_subdivisions):
        y_min = int(page_y_length * float(y_sub) / vertical_page_subdivisions) + page_y_begin
        y_max = int(page_y_length * float(y_sub + 1) / vertical_page_subdivisions) + page_y_begin
        x_min = page_x_begin
        x_max = page_x_end
        subset_page_bounds = (x_min, x_max, y_min, y_max)
        horizontal_sub_borders = find_border_points_subset_page(page, subset_page_bounds, False)
        horizontal_sub_borders_all.append(horizontal_sub_borders)

    vertical_sub_borders_all = list()
    for x_sub in range(horizontal_page_subdivisions):
        x_min = int(page_x_length * float(x_sub) / horizontal_page_subdivisions) + page_x_begin
        x_max = int(page_x_length * float(x_sub + 1) / horizontal_page_subdivisions) + page_x_begin
        y_min = page_y_begin
        y_max = page_y_end
        subset_page_bounds = (y_min, y_max, x_min, x_max)
        vertical_sub_borders = find_border_points_subset_page(page, subset_page_bounds, True)
        vertical_sub_borders_all.append(vertical_sub_borders)

    clean_vertical_borders = clean_and_infer_borders(vertical_sub_borders_all, False)
    clean_horizontal_borders = clean_and_infer_borders(horizontal_sub_borders_all, True)

    # Transpose lists so each borders points are within 1 list, not spread across all lists
    # NOTE: Transposing turns the vertical sub-borders into a list of horizontal lines, and vice-versa
    horizontal_borders = transpose_and_infer(clean_vertical_borders, True)
    vertical_borders = transpose_and_infer(clean_horizontal_borders, False)

    horizontal_border_angles_lines = infer_border_angled_lines(horizontal_borders, False)
    vertical_border_angled_lines = infer_border_angled_lines(vertical_borders, True)

    intersections = get_intersections(vertical_border_angled_lines, horizontal_border_angles_lines)

    bounds = list()

    for top_left, top_right, bottom_left, bottom_right in intersections:
        # TODO: These seem mixed up, but it works...
        left = utils.average([top_left[0], top_right[0]])
        right = utils.average([bottom_left[0], bottom_right[0]])
        top = utils.average([top_left[1], bottom_left[1]])
        bottom = utils.average([top_right[1], bottom_right[1]])
        bounds.append((top, bottom, left, right))

    if tmpdir:
        dots = list()
        for h in horizontal_borders:
            dots.extend(h)
        draw_page(page, tmpdir, "horizontal_borders", tuple(dots), None)

        dots = list()
        for v in vertical_borders:
            dots.extend(v)
        draw_page(page, tmpdir, "vertical_borders", tuple(dots), None)

        f = open(os.path.join(tmpdir, "get_bounds_data.txt"), "w")

        f.write("page_y_begin " + str(page_y_begin))
        f.write("\rpage_y_end " + str(page_y_end))
        f.write("\rpage_x_begin " + str(page_x_begin))
        f.write("\rpage_x_end " + str(page_x_end))

        f.write("\r\rhorizontal_sub_borders_all " + str(horizontal_sub_borders_all))
        f.write("\rvertical_sub_borders_all " + str(vertical_sub_borders_all))

        f.write("\r\rclean_vertical_borders " + str(clean_vertical_borders))
        f.write("\rclean_horizontal_borders " + str(clean_horizontal_borders))

        f.write("\r\rvertical_borders " + str(vertical_borders))
        f.write("\rhorizontal_borders " + str(horizontal_borders))

        f.write("\r\rhorizontal_border_angles_lines " + str(horizontal_border_angles_lines))
        f.write("\rvertical_border_angled_lines " + str(vertical_border_angled_lines))

        f.write("\r\rintersections " + str(intersections))

        f.write("\r\rbounds " + str(bounds))

        f.close()

        border_coordinates = list()
        for slope, intercept in horizontal_border_angles_lines:
            y1 = intercept
            y2 = intercept + slope*page.width
            border_coordinates.append((y1, 0, y2, page.width-1))

        for slope, intercept in vertical_border_angled_lines:
            x1 = intercept
            x2 = intercept + slope*page.height
            border_coordinates.append((0, x1, page.height-1, x2))

        draw_page(page, tmpdir, "border_lines", None, tuple(border_coordinates))

    if tmpdir:
        converted_bounds = list()
        for y1, y2, x1, x2 in bounds:
            converted_bounds.extend([(y1, x1), (y1, x2), (y2, x1), (y2, x2)])
        draw_page(page, tmpdir, "bounds", tuple(converted_bounds), None)

    return bounds


def find_beginning_or_ending(page, vertical, reverse, perp_min_override=None, perp_max_override=None):
    """
    :param page: Page to find beginning (or ending) of
    :param vertical: True if vertical beginning (or ending), False if horizontal
    :param reverse: True if beginning, False if ending
    :return: Coordinate of beginning (or ending)
    """
    low_border_threshold = 0.80
    max_skew = 3

    along_min = 0
    perp_min = perp_min_override if perp_min_override else 0

    along_max = page.height if vertical else page.width
    perp_max = perp_max_override if perp_max_override else page.width if vertical else page.height

    # TODO: Replace the first part with page.get_perpendicular_shade_averages()
    along_range = range(along_min, along_max)
    if reverse:
        along_range = along_range[::-1]

    for along_iter in along_range:
        perp_sum = 0
        for perp_iter in range(perp_min, perp_max):
            y = along_iter if vertical else perp_iter
            x = perp_iter if vertical else along_iter

            shade = utils.average(page.get_pixel(y, x))
            perp_sum += shade
        perp_avg = perp_sum / (perp_max - perp_min)

        if perp_avg < low_border_threshold:
            # Add a buffer equal to the max skew.
            along_border = along_iter + (1 if reverse else -1) * max_skew

            # Don't exceed the page boundaries.
            along_border = max(min(along_border, (page.height if vertical else page.width) - 1), 0)

            return along_border

    # TODO: Throw decoding error
    return -1


def find_border_points_subset_page(page, sub_bounds, vertical):
    low_border_threshold = 0.20
    min_border_difference = 32

    borders = list()

    along_min, along_max, perp_min, perp_max = sub_bounds

    border_started = False
    last_perp_avg = -1

    # TODO: Replace the first part with page.get_perpendicular_shade_averages()
    along_iter = along_min
    while along_iter <= along_max:
        perp_sum = 0
        for perp_iter in range(perp_min, perp_max + 1):
            y = along_iter if vertical else perp_iter
            x = perp_iter if vertical else along_iter

            shade = utils.average(page.get_pixel(y, x))
            perp_sum += shade
        perp_avg = perp_sum / (perp_max - perp_min + 1)

        # If the border has started, find a local darkest point in the border
        if border_started and perp_avg > last_perp_avg:
            border_started = False

            along_coordinate = along_iter - 1
            perp_coordinate = (perp_max + perp_min) / 2

            y = along_coordinate if vertical else perp_coordinate
            x = perp_coordinate if vertical else along_coordinate
            borders.append((y, x))

            along_iter += min_border_difference - 1
            continue

        # Check darkness to start the border (or if we're at the end of the range, end on a border)
        if perp_avg <= low_border_threshold:
            if along_iter == along_max:
                along_coordinate = along_iter
                perp_coordinate = (perp_max + perp_min) / 2

                y = along_coordinate if vertical else perp_coordinate
                x = perp_coordinate if vertical else along_coordinate
                borders.append((y, x))

                break

            border_started = True
            last_perp_avg = perp_avg

        along_iter += 1

    return borders


def clean_and_infer_borders(sub_borders_all, vertical):
    # Transpose lists so each borders points are within 1 list, not spread across all lists
    # TODO: Clean up and infer sub borders before transposing - unequal lists are clipped.

    initial_points = list()
    perp_points = list()
    new_sub_borders_all = list()
    along_diffs_all = list()
    for sub_borders in sub_borders_all:
        if not sub_borders or not len(sub_borders):
            continue

        initial_points.append(sub_borders[0][1] if vertical else sub_borders[0][0])
        perp_points.append(sub_borders[0][0] if vertical else sub_borders[0][1])

        along_diffs = list()
        along_points = list()
        for y, x in sub_borders:
            along = x if vertical else y

            if len(along_points):
                along_diffs.append(along - along_points[-1])

            along_points.append(along)

        along_diffs_all.append(along_diffs)

    along_diffs_flat = reduce(operator.concat, along_diffs_all)
    if len(along_diffs_flat) < 3:
        return map(list, zip(*sub_borders_all))

    along_diffs_flat_std = utils.standard_deviation_squared(along_diffs_flat)

    # Begin clean-up - mark boundaries that can be merged
    # TODO: This needs to account for multiple merged diffs
    # e.g. differentiate [25,75,27,75,100,100,100] and [25,25,25,25,100,100,100]
    for all_iter, along_diffs in enumerate(along_diffs_all):
        along_diffs_others = reduce(operator.concat, utils.remove_index(along_diffs_all, all_iter))

        if len(along_diffs) < 2:
            new_sub_borders_all.append(sub_borders_all[all_iter])
            continue

        # Combine two sequential along-diff values if they reduce the standard deviation of the list
        merge_indexes = list()

        for along_iter in range(1, len(along_diffs)):
            diff = along_diffs[along_iter]
            diff_previous = along_diffs[along_iter - 1]

            # Merge diff1 and diff2 in the list
            lrem = utils.remove_index(along_diffs, along_iter - 1)
            lrem[along_iter - 1] = diff_previous + diff

            # If merging those diffs would lower the overall standard deviation, then mark it for merge
            # TODO: Refine tolerance factor
            tolerance = 0.9
            if utils.standard_deviation_squared(lrem + along_diffs_others) < along_diffs_flat_std * tolerance:
                if not (len(merge_indexes) and merge_indexes[-1] == along_iter - 1):
                    merge_indexes.append(along_iter)

        along_diffs_clean = copy(along_diffs)

        # Merge diffs
        # TODO: Could probably just use along_points
        i = 0
        while i < len(merge_indexes):
            index = merge_indexes[i]
            add = along_diffs_clean.pop(index-1)
            along_diffs_clean[index-1] += add
            merge_indexes = map(lambda x: x - 1, merge_indexes)

            i += 1

        # Turn diffs to new along points
        new_along_points = [initial_points[all_iter]]
        for i in range(len(along_diffs_clean)):
            new_along_points.append(sum(along_diffs_clean[:i+1]) + initial_points[all_iter])

        if vertical:
            new_sub_borders = map(lambda x: (perp_points[all_iter], x), new_along_points)
        else:
            new_sub_borders = map(lambda y: (y, perp_points[all_iter]), new_along_points)

        new_sub_borders_all.append(new_sub_borders)

    return new_sub_borders_all


def transpose_and_infer(borders_all, vertical):
    max_val = 0
    min_val = sys.maxint
    for borders in borders_all:
        for y, x in borders:
            max_val = max(y if vertical else x, max_val)
            min_val = min(y if vertical else x, min_val)

    approximate_max_sectors = 15.0

    max_diff = (max_val - min_val) / (2.0 * approximate_max_sectors)

    transposed_list = list()
    for borders in borders_all:
        for y, x in borders:
            coord = (y, x)
            val = y if vertical else x

            inserted = False
            for inserted_borders_index in range(len(transposed_list)):
                inserted_borders = transposed_list[inserted_borders_index]
                for y_ins, x_ins in inserted_borders:
                    ins_val = y_ins if vertical else x_ins
                    if ins_val - max_diff < val < ins_val + max_diff:
                        transposed_list[inserted_borders_index].append(coord)

                        inserted = True
                        break
                if inserted:
                    break

            if not inserted:
                transposed_list.append([coord])

    # Sort first by second value, then by first
    sorted_transposed_list = sorted(transposed_list, key=lambda val: val[0][0 if vertical else 1])
    for i in range(len(sorted_transposed_list)):
        sorted_transposed_list[i] = sorted(sorted_transposed_list[i], key=lambda val: val[1 if vertical else 0])

    return sorted_transposed_list


def remove_outliers(l):
    """
    Remove all values in l whose presence increases the overall standard deviation of the list
    :param l: Input list
    :return: Corrected list
    """
    MIN_LIST_LENGTH = 2

    if len(l) <= MIN_LIST_LENGTH:
        return l

    tolerance = 0.95  # TODO: Determine this heuristically

    # Sort by increasing distance from mean, since only removing the largest outliers in a list affects its variance.
    l_med = utils.median(l)
    l = sorted(l, key=lambda x: abs(x - l_med))

    std = utils.standard_deviation_squared(l)
    for i in range(0, len(l))[::-1]:
        newstd = utils.standard_deviation_squared(utils.remove_index(l, i))
        if newstd < std * tolerance:
            l.pop(i)

            if len(l) <= MIN_LIST_LENGTH:
                break

            std = utils.standard_deviation_squared(l)
            continue

    return l


def infer_border_angled_lines(border_points_list, vertical):
    """
    Get slope and x-intercept if vertical border points, or slope and y-intercept if horizontal.

    This method currently uses a simple average.

    TODO: A least squares fit would be more accurate (removing outlier influence, for example)

    :param border_points_list: List of border points, e.g. [[(0,10),(0,20),(0,30)],[(101,10),(102,20),(103,30)]]
    :return: List of inferred angled lines, params slope and intercept, e.g. [(0,0), (0.1,100)]
    """
    border_angled_lines = list()
    for border_points in border_points_list:
        while None in border_points:
            border_points.remove(None)

        if not border_points or not len(border_points) > 1:
            continue

        slope_list = list()
        intercept_list = list()

        # Don't just look at adjacent pairs, which could have small along-differences that amplify the slope
        # Look at all n*(n-1) combinations of points, which are more likely to be far apart with smaller slopes
        for i in range(len(border_points) - 1):
            for j in range(i+1, len(border_points)):
                y1, x1 = border_points[i]
                y2, x2 = border_points[j]
                if vertical:
                    if y1 != y2:
                        slope = float(x2 - x1) / float(y2 - y1)
                        slope_list.append(slope)
                        intercept_list.append(x1 - slope * y1)
                else:
                    if x1 != x2:
                        slope = float(y2 - y1) / float(x2 - x1)
                        slope_list.append(slope)
                        intercept_list.append(y1 - slope * x1)

        corrected_slope_list = remove_outliers(slope_list) if len(slope_list) > 2 else slope_list
        corrected_intercept_list = remove_outliers(intercept_list) if len(intercept_list) > 2 else intercept_list

        slope = utils.average(corrected_slope_list)
        intercept = utils.average(corrected_intercept_list)

        border_angled_lines.append((slope, intercept))

    return border_angled_lines


def get_coordinates(v_value, h_value):
    vertical_slope, vertical_intercept = v_value
    horizontal_slope, horizontal_intercept = h_value

    y = vertical_slope * horizontal_intercept + vertical_intercept / (
            1 - vertical_slope * horizontal_slope)
    x = horizontal_slope * vertical_intercept + horizontal_intercept / (
            1 - vertical_slope * horizontal_slope)

    return int(y), int(x)


def get_intersections(vertical_border_angled_lines, horizontal_border_angles_lines):
    """
    y = vertical_slope * x + vertical_intercept
    x = horizontal_slope * y + horizontal_intercept

    Solving for these gives the intersection points:
    y = vertical_slope * horizontal_intercept + vertical_intercept / (1 - vertical_slope * horizontal_slope)
    x = horizontal_slope * vertical_intercept + horizontal_intercept / (1 - vertical_slope * horizontal_slope)

    :param vertical_border_angled_lines: List of vertical slopes and intercepts
    :param horizontal_border_angles_lines: List of horizontal slopes and intercepts
    :return: List of intersection points
    """

    intersections = list()
    for h_index, h_value in enumerate(horizontal_border_angles_lines[1:], 1):
        for v_index, v_value in enumerate(vertical_border_angled_lines[1:], 1):
            v_value_prev = vertical_border_angled_lines[v_index - 1]
            h_value_prev = horizontal_border_angles_lines[h_index - 1]

            top_left = get_coordinates(v_value_prev, h_value_prev)
            top_right = get_coordinates(v_value_prev, h_value)
            bottom_left = get_coordinates(v_value, h_value_prev)
            bottom_right = get_coordinates(v_value, h_value)

            intersections.append((top_left, top_right, bottom_left, bottom_right))

    return intersections


def get_real_sector_data_boundary(page, leastAlong, mostAlong, leastPerp, mostPerp, vertical, reverse):
    """Search within given rough sector bounds and return the true coordinate of the gap
    E.g. if looking for the real top gap coordinate, along is y and perp is x. Return y.
    """
    perp_shades = page.get_perpendicular_shade_averages(leastAlong, mostAlong, leastPerp, mostPerp, vertical, reverse)

    dataIndex = 0

    brightestShade = max(perp_shades)
    firstGapIndex = perp_shades.index(brightestShade)
    darkestShadeAfterGap = min(perp_shades[firstGapIndex:])

    if brightestShade == darkestShadeAfterGap:
        return dataIndex

    # TODO: Improve this value
    gapToDataTolerance = 0.4

    # Get the closest value that has a sizeable drop from the max of all previous shades
    # This only works if the initial shade is assumed to be the darkest part of the border
    for perpIndex, perpShade in enumerate(perp_shades[firstGapIndex:], firstGapIndex):
        thresholdedPerpShade = utils.threshold(perpShade, brightestShade, darkestShadeAfterGap)
        if thresholdedPerpShade < 1 - gapToDataTolerance:
            dataIndex = perpIndex
            break

    dataBound = dataIndex + leastAlong if not reverse else mostAlong - dataIndex

    return dataBound


def get_real_sector_data_boundaries(page, heightPerDot, widthPerDot, topmost, bottommost, leftmost, rightmost):
    """Find real data boundaries.
    Look within two-dot unit of pixels away, only looking inwards since input bounds will be within a border
    """

    # Search just past the boundary and gaps
    max_dots_away = defaults.borderSize + defaults.gapSize + 2

    bottommostTop = topmost + int(round(max_dots_away * heightPerDot))
    topmostBottom = bottommost - int(round(max_dots_away * heightPerDot))
    rightmostLeft = leftmost + int(round(max_dots_away * widthPerDot))
    leftmostRight = rightmost - int(round(max_dots_away * widthPerDot))

    # TODO: First find gap, then find data (or else a blurry line could count as data)
    top = get_real_sector_data_boundary(
        page,
        topmost,
        bottommostTop,
        rightmostLeft,
        leftmostRight,
        True,
        False)

    bottom = get_real_sector_data_boundary(
        page,
        topmostBottom,
        bottommost,
        rightmostLeft,
        leftmostRight,
        True,
        True)

    left = get_real_sector_data_boundary(
        page,
        leftmost,
        rightmostLeft,
        bottommostTop,
        topmostBottom,
        False,
        False)

    right = get_real_sector_data_boundary(
        page,
        leftmostRight,
        rightmost,
        bottommostTop,
        topmostBottom,
        False,
        True)

    top = top if top else topmost
    bottom = bottom if bottom else bottommost
    left = left if left else leftmost
    right = right if right else rightmost

    return top, bottom, left, right


def correct_one_data_bound(data_bound, sector_height, sector_width, page, right_else_bottom):
    """
    Get the corrected data bound for right or bottom data bound. The bound passed in will be found by looking where
    the pixels start, but the encoding may have each dot filled partially; the partial pixels will be in the top-left.
    Thus, we find the right or bottom bound where the pixels begin, since whitespace won't be counted, and decoding will
    be shifted off slightly. There is no way to look for dots without a timing pattern, and looking for pixels is wrong.

    To fix this, look for a bound that optimizes some rows or columns to have a weighted standard deviation as
    small as possible. This happens when dots and whitespace overlap as little as possible within the row or column,
    e.g. each dot is filled with pixels that have minimal variance.

    An encoded timing pattern would simplify this, at the expense of allowing less data to be encoded.

    TODO: Support shades
    TODO: Search for larger than 1 pixel modifier to support dots with > 1 whitespace pixel
    TODO: For normal (blurred) data, relaxing the low_data threshold that generates data_bound to get a better bound

    :param data_bound: The data bounds found by looking where pixels begin.
    :param sector_height: Dot height of sector
    :param sector_width: Dot width of sector
    :param page: Page to be decoded
    :param right_else_bottom: True for right, False for bottom
    :return: The correct bound modifier, either right or bottom
    """

    top, bottom, left, right = data_bound

    min_sum_weighted_stds = sys.maxint
    best_modifier = 0

    divisions = 4
    modifier_possibilites = map(lambda i: float(i) / divisions, range(divisions + 1))

    for bound_modifier in modifier_possibilites:
        weighted_stds = list()

        # Right bound
        along_max = sector_height if right_else_bottom else sector_width
        along_division = 4

        perp_max = sector_width if right_else_bottom else sector_height
        for along_iter in range(0, along_max, along_max / along_division):
            for perp_iter in range(0, perp_max):
                x = perp_iter if right_else_bottom else along_iter
                y = along_iter if right_else_bottom else perp_iter

                right_modifier = bound_modifier if right_else_bottom else 0
                bottom_modifier = bound_modifier if not right_else_bottom else 0

                pixels_and_weight, weight_sum, y_center, x_center = get_pixels_and_weight(y,
                                                                                          x,
                                                                                          top,
                                                                                          bottom + bottom_modifier,
                                                                                          left,
                                                                                          right + right_modifier,
                                                                                          sector_height,
                                                                                          sector_width,
                                                                                          page)

                for i in range(0, constants.ColorChannels):
                    shade_and_weight = map(lambda (pixel, weight, _, __): (pixel[i], weight), pixels_and_weight)
                    weighted_std = utils.weighted_standard_deviation_squared(shade_and_weight)
                    weighted_stds.append(weighted_std)

        sum_weighted_stds = sum(weighted_stds)

        if sum_weighted_stds < min_sum_weighted_stds:
            min_sum_weighted_stds = sum_weighted_stds
            best_modifier = bound_modifier

        continue

    return best_modifier


def correct_data_bound(data_bound, sector_height, sector_width, page):
    top, bottom, left, right = data_bound

    right_modifier = correct_one_data_bound(data_bound, sector_height, sector_width, page, True)
    bottom_modifier = correct_one_data_bound(data_bound, sector_height, sector_width, page, False)

    return (top, bottom + bottom_modifier, left, right + right_modifier)

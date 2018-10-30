from colorsafe import utils


class InputPages:
    def __init__(self, totalPages, height, width):
        self.totalPages = totalPages
        self.height = height
        self.width = width

    def getPagePixel(self, page, y, x):
        """For caller to implement"""
        pass


class InputPage:
    def __init__(self, pages, pageNum):
        self.pages = pages
        self.height = pages.height
        self.width = pages.width
        self.pageNum = pageNum

    def get_pixel(self, y, x):
        return self.pages.getPagePixel(self.pageNum, y, x)

    def get_perpendicular_shade_averages(self, least_along, most_along, least_perp, most_perp, vertical, reverse):
        """
        For a section of this page, return a list of shade averages in the along direction. The shade averages will be
        the average of the perpendicular channels at each point in the along direction.

        Thus this will essentially collapse the shades into one summarized list in the along direction.

        Example input (if Y is vertical, X is horizontal):
        [[100, 100, 100]
         [0,   0,   0  ]
         [50,  50,  50 ]]

        Example output along vertical:
        [100, 0, 50]

        Example output along horizontal:
        [75, 75, 75]

        TODO: The reverse argument can be removed and replaced by simply having least_along be greater than most_along

        :param least_along: Least valued point in the along direction
        :param most_along: Most values poitn in the along direction
        :param least_perp: Least valued point in the perpendicular direction
        :param most_perp: Least valued point in the perpendicular direction
        :param vertical: True if the along direction is vertical, False if the along direction if horizontal
        :param reverse: True to traverse from most to least, False to traverse from least to most
        :return: A list of the perpendicular shade averages in the along direction within the bounds.
        """
        along_range = range(least_along, most_along + 1)
        if reverse:
            along_range = along_range[::-1]

        perp_shade_avgs = list()
        for along in along_range:
            perp_shade_sum = 0.0
            for perp in range(least_perp, most_perp + 1):
                y = along if vertical else perp
                x = perp if vertical else along

                if y < 0 or y >= self.height or x < 0 or x >= self.width:
                    break

                perp_shade_sum += utils.average(self.get_pixel(y, x))

            perp_shade_avg = perp_shade_sum / (most_perp - least_perp + 1)
            perp_shade_avgs.append(perp_shade_avg)

        return perp_shade_avgs

import operator
import os

from PIL import ImageDraw, Image


def drawPage(page, tmpdir, filename, pixels=None, lines=None, color=(0, 0, 0)):
    """
    Draw page with additional pixels and lines for debugging purposes
    :param page: InputPage type
    :param pixels: ((y, x), (y, x))
    :param lines: ((y1, x1, y2, x2), ...)
    :param color: (r, g, b)
    :return:
    """

    image = Image.new('RGB', (page.width, page.height), (255,) * 4)
    image_pixels = image.load()  # create the pixel map

    # Draw image
    for y in range(page.height):
        for x in range(page.width):
            pixel = page.getPixel(int(y), int(x))
            pixel = tuple(map(operator.mul, pixel, (255,) * 3))
            pixel = tuple(map(int, pixel))
            image_pixels[int(x), int(y)] = pixel

    if pixels:
        for y, x in pixels:
            image_pixels[x, y] = color

    if lines:
        draw = ImageDraw.Draw(image)
        for y1, x1, y2, x2 in lines:
            draw.line((x1, y1, x2, y2), fill=color)

    image.save(os.path.join(tmpdir, filename + ".png"))
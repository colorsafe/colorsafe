import operator
import os

from PIL import ImageDraw, Image


def draw_page(page, tmpdir, filename, pixels=None, lines=None, pixels_colors=None):
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
            pixel = page.get_pixel(int(y), int(x))
            pixel = tuple(map(operator.mul, pixel, (255,) * 3))
            pixel = tuple(map(int, pixel))
            image_pixels[int(x), int(y)] = pixel

    if pixels:
        for pixel in pixels:
            if pixel:
                y, x = pixel
                if page.width > x >= 0 and page.height > y >= 0:
                    image_pixels[x, y] = (255, 0, 0)

    if lines:
        draw = ImageDraw.Draw(image)
        for y1, x1, y2, x2 in lines:
            draw.line((x1, y1, x2, y2), fill=(255, 0, 0))

    if pixels_colors:
        for pixel_color in pixels_colors:
            if pixel_color:
                y, x, color = pixel_color
                if page.width > x >= 0 and page.height > y >= 0:
                    image_pixels[x, y] = color

    image.save(os.path.join(tmpdir, filename + ".png"))

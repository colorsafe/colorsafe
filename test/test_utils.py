import random
import string

import PIL
import glob
import os

from PIL import Image, ImageFilter

from colorsafe.constants import MagicByte


def get_random_string(n, seed=None):
    random.seed(seed)
    return ''.join(chr(random.randint(0, 2 ** 7 - 1)) for _ in xrange(n))


def get_random_alphanumeric_string(n, seed=None):
    random.seed(seed)
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in xrange(n))


texts = {"lorem":
         "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Phasellus sollicitudin tincidunt diam id gravida."
         "Integer gravida risus quis purus bibendum volutpat. Fusce nec scelerisque ipsum. Curabitur nec augue ac"
         "nulla aliquet gravida ut quis justo. Aliquam sagittis nec arcu consectetur fermentum. Duis consectetur"
         "convallis pharetra. Nullam porttitor mi quis risus rhoncus malesuada nec vitae ex. Nunc non mattis justo."
         "Sed pellentesque, nulla vitae sagittis pulvinar, massa dui pellentesque sapien, vel dignissim lorem nisi sit"
         "amet augue. Nam rhoncus leo non urna sodales, vitae elementum magna viverra. Aliquam aliquam eu neque vel"
         "dictum. Nulla fermentum placerat elit. Vivamus non augue congue, maximus sem non, mollis nulla. Donec non"
         "elit purus.",
         "magic_bytes": chr(MagicByte) * 1000,
         "random_const_3000": get_random_alphanumeric_string(3000, 0),
         "random_const_20000": get_random_alphanumeric_string(20000, 0)}


def modify(alter, *args):
    return lambda tmpdir: modify_tmpdir(tmpdir, alter, *args)


def modify_tmpdir(tmpdir, alter, *args):
    out_image_name_wildcard = "out_*.png"
    altered_image_name_wildcard = "altered_*.png"
    out_image_name_prefix = "out"
    altered_image_name_prefix = "altered"

    filenames = glob.glob(
        os.path.join(
            str(tmpdir),
            out_image_name_wildcard))

    for filename in filenames:
        try:
            img = Image.open(filename)

            out = alter(img, *args)

            altered_file_name = filename.replace(out_image_name_prefix, altered_image_name_prefix)
            out.convert(img.mode).save(altered_file_name)
        except IOError:
            print "ERROR: File {} is not a valid image file".format(filename)
            return

    return altered_image_name_wildcard


def no_modify(tmpdir):
    out_image_name_wildcard = "out_*.png"
    return out_image_name_wildcard


def rotate_image(image, angle):

    image2 = image.convert('RGBA')

    rotated_image = image2.rotate(angle, expand=1)
    rotated_image2 = Image.new('RGBA', rotated_image.size, (255,) * 4)

    # Create a composite image using the alpha layer of the rotated_image as a mask
    return Image.composite(rotated_image, rotated_image2, rotated_image)


def offset_partial(image, width_factor, height_factor):
    # Half pixel offset in x and y
    resize = image.resize((int(image.width * width_factor), int(image.height * height_factor)), PIL.Image.BICUBIC)

    resize2 = PIL.ImageChops.offset(resize, 1, yoffset=1)
    blend1 = PIL.ImageChops.blend(resize, resize2, 0.5)
    blend2 = PIL.ImageChops.blend(resize, blend1, 0.5)
    return blend2


def gaussian_blur_image(image, radius):

    return image.filter(ImageFilter.GaussianBlur(radius=radius))


def shift_image(image, yoffset):

    return PIL.ImageChops.offset(image, 0, yoffset=yoffset)


def resize_image(image, width_factor, height_factor):

    out = image.resize((int(image.width * width_factor), int(image.height * height_factor)), PIL.Image.BICUBIC)

    return out

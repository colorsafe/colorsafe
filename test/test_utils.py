import PIL
import glob
import os

from PIL import Image, ImageFilter

from colorsafe.constants import MagicByte

in_file_name = "text.txt"
out_file_name = "out.txt"
metadata_file_name = "metadata.txt"
out_image_name_wildcard = "out_*.png"
altered_image_name_wildcard = "altered_*.png"
out_image_name_prefix = "out"
altered_image_name_prefix = "altered"

texts = {"lorem":
         "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Phasellus sollicitudin tincidunt diam id gravida."
         "Integer gravida risus quis purus bibendum volutpat. Fusce nec scelerisque ipsum. Curabitur nec augue ac"
         "nulla aliquet gravida ut quis justo. Aliquam sagittis nec arcu consectetur fermentum. Duis consectetur"
         "convallis pharetra. Nullam porttitor mi quis risus rhoncus malesuada nec vitae ex. Nunc non mattis justo."
         "Sed pellentesque, nulla vitae sagittis pulvinar, massa dui pellentesque sapien, vel dignissim lorem nisi sit"
         "amet augue. Nam rhoncus leo non urna sodales, vitae elementum magna viverra. Aliquam aliquam eu neque vel"
         "dictum. Nulla fermentum placerat elit. Vivamus non augue congue, maximus sem non, mollis nulla. Donec non"
         "elit purus.",
         "magic_bytes": chr(MagicByte) * 1000}
# TODO: Test a unicode string case

image_alterations = {"none": lambda tmpdir: out_image_name_wildcard,
                     "rotate0.1": lambda tmpdir: modify_image(tmpdir, rotate_image, 0.2),
                     "gaussian_blur0.2": lambda tmpdir: modify_image(tmpdir, gaussian_blur_image, 0.2),
                     "shift10": lambda tmpdir: modify_image(tmpdir, shift_image, 10),
                     "resize2.1x": lambda tmpdir: modify_image(tmpdir, resize_image, 2.1)
                     }


def modify_image(tmpdir, alter_image_function, *alter_function_args):
    filenames = glob.glob(
        os.path.join(
            str(tmpdir),
            out_image_name_wildcard))

    for filename in filenames:
        try:
            img = Image.open(filename)

            out = alter_image_function(img, alter_function_args)

            altered_file_name = filename.replace(out_image_name_prefix, altered_image_name_prefix)
            out.convert(img.mode).save(altered_file_name)
        except IOError:
            print "ERROR: File {} is not a valid image file".format(filename)
            return

    return altered_image_name_wildcard


def rotate_image(image, args):
    angle = args[0]

    image2 = image.convert('RGBA')

    rotated_image = image2.rotate(angle, expand=1)
    rotated_image2 = Image.new('RGBA', rotated_image.size, (255,) * 4)

    # Create a composite image using the alpha layer of the rotated_image as a mask
    return Image.composite(rotated_image, rotated_image2, rotated_image)


def gaussian_blur_image(image, args):
    radius = args[0]

    return image.filter(ImageFilter.GaussianBlur(radius=radius))


def shift_image(image, args):
    yoffset = args[0]

    return PIL.ImageChops.offset(image, 0, yoffset=yoffset)


def resize_image(image, args):
    factor = args[0]

    out = image.resize((int(image.width * factor), int(image.height * factor)), PIL.Image.BICUBIC)
    out2 = image.resize((int(out.width * (1 / factor)), int(out.height * (1 / factor))), PIL.Image.BICUBIC)

    return out2

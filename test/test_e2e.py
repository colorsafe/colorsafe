from PIL import Image, ImageFilter
import glob
import os
import pytest
import random

from colorsafe.constants import MagicByte

from colorsafe.exceptions import DecodingError, EncodingError

from colorsafe import utils
from colorsafe.decoder.csdecoder_manager import ColorSafeDecoder
from colorsafe.encoder.csencoder_manager import ColorSafeEncoder

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
# TODO: Parametrize all tests with multiple color-depths


def rotate_image(tmpdir, angle):
    filenames = glob.glob(
        os.path.join(
            str(tmpdir),
            out_image_name_wildcard))

    for filename in filenames:
        try:
            img = Image.open(filename)
            img2 = img.convert('RGBA')

            rot = img2.rotate(angle, expand=1)
            rot2 = Image.new('RGBA', rot.size, (255,) * 4)

            # create a composite image using the alpha layer of rot as a mask
            out = Image.composite(rot, rot2, rot)

            altered_file_name = filename.replace(out_image_name_prefix, altered_image_name_prefix)
            out.convert(img.mode).save(altered_file_name)
        except IOError:
            print "ERROR: File {} is not a valid image file".format(filename)
            return

    return altered_image_name_wildcard


def gaussian_blur_image(tmpdir, radius):
    filenames = glob.glob(
        os.path.join(
            str(tmpdir),
            out_image_name_wildcard))

    for filename in filenames:
        try:
            img = Image.open(filename)
            out = img.filter(ImageFilter.GaussianBlur(radius=radius))

            altered_file_name = filename.replace(out_image_name_prefix, altered_image_name_prefix)
            out.convert(img.mode).save(altered_file_name)
        except IOError:
            print "ERROR: File {} is not a valid image file".format(filename)
            return

    return altered_image_name_wildcard


image_alterations = {"none": lambda tmpdir: out_image_name_wildcard,
                     "rotate0.1": lambda tmpdir: rotate_image(tmpdir, 0.1),
                     "gaussian_blur0.2": lambda tmpdir: gaussian_blur_image(tmpdir, 0.2)
                     }


params_random = {
    ("random_data", 1, 3, 3, 1, 1, 100, "random", "none"),
    ("random_data_2_ppd", 1, 3, 3, 2, 2, 100, "random", "none"),
}

RANDOM_TEST_TRIALS = 3


@pytest.mark.parametrize('execution_number', range(RANDOM_TEST_TRIALS))
@pytest.mark.parametrize(
    "test_name,"
    "color_depth,"
    "page_height,"
    "page_width,"
    "dot_fill_pixels,"
    "pixels_per_dot,"
    "printer_dpi,"
    "text_index,"
    "image_alteration",
    params_random)
def test_e2e_random(execution_number,
                    tmpdir,
                    test_name,
                    color_depth,
                    page_height,
                    page_width,
                    dot_fill_pixels,
                    pixels_per_dot,
                    printer_dpi,
                    text_index,
                    image_alteration):

    # TODO: Test a random unicode string case
    def get_random_string():
        return ''.join(chr(random.randint(0, 2 ** 7 - 1)) for i in range(1000))

    texts['random'] = get_random_string()
    test_e2e(tmpdir,
             test_name,
             color_depth,
             page_height,
             page_width,
             dot_fill_pixels,
             pixels_per_dot,
             printer_dpi,
             text_index,
             image_alteration)


# Params: Test Name, Colors, Height, Width, DFP, PPD, DPI, Text index
params = [
    ("standard", 1, 11, 8.5, 1, 1, 100, "lorem", "none"),
    ("smaller_page", 1, 3, 3, 1, 1, 100, "lorem", "none"),
    ("2_ppd_1_dfp", 1, 3, 3, 1, 2, 100, "lorem", "none"),
    ("4_ppd_4_dfp", 1, 3, 3, 4, 4, 100, "lorem", "none"),
    ("150_dpi", 1, 3, 3, 1, 1, 150, "lorem", "none"),
    ("color_2", 2, 3, 3, 1, 1, 100, "lorem", "none"),
    ("color_3", 3, 3, 3, 1, 1, 100, "lorem", "none"),
    ("blur_2", 1, 3, 3, 1, 1, 100, "lorem", "gaussian_blur0.2"),
    ("blur_2_dfp_2", 1, 3, 3, 2, 2, 100, "lorem", "gaussian_blur0.2"),
    # ("rotate_0.1", 1, 3, 3, 4, 4, 100, "lorem", "rotate0.1"),  # TODO: Fix this test
]


@pytest.mark.parametrize(
    "test_name,"
    "color_depth,"
    "page_height,"
    "page_width,"
    "dot_fill_pixels,"
    "pixels_per_dot,"
    "printer_dpi,"
    "text_index,"
    "image_alteration",
    params)
def test_e2e(tmpdir,
             test_name,
             color_depth,
             page_height,
             page_width,
             dot_fill_pixels,
             pixels_per_dot,
             printer_dpi,
             text_index,
             image_alteration):  # Use text index, not text, to avoid an extremely large PyTest test name
    """Encode a text file, then decode it and compare the contents to the original file.

    :param test_name Test name, to make it easier to associate pytest results with the test they belong to.
    """

    border_top = 0.2
    border_bottom = border_left = border_right = 0.1

    # Encoding
    in_file = tmpdir.join(in_file_name)

    in_data = texts[text_index]
    in_file.write(in_data)

    if (tmpdir):
        f = open(os.path.join(str(tmpdir), "inDataNewLineDelimited.txt"), "w")
        for i in in_data:
            f.write(str(i) + " " + str(utils.intToBinaryList(ord(i), 8)) + "\n")
        f.close()

    ColorSafeEncoder(
        str(in_file),
        color_depth,
        page_height,
        page_width,
        border_top,
        border_bottom,
        border_left,
        border_right,
        dot_fill_pixels,
        pixels_per_dot,
        printer_dpi,
        str(tmpdir),
        True,
        True)

    # Alterations
    desired_wildcard = image_alterations[image_alteration](tmpdir)

    # Decoding
    out_file = tmpdir.join(out_file_name)
    metadata_file = tmpdir.join(metadata_file_name)

    altered_image_paths = glob.glob(
        os.path.join(
            str(tmpdir),
            desired_wildcard))

    assert altered_image_paths > 0

    ColorSafeDecoder(altered_image_paths, color_depth, str(out_file), str(metadata_file), str(tmpdir))

    out_file_contents = out_file.read()

    assert len(out_file_contents) > 0

    # Check for correctness
    assert texts[text_index] == out_file_contents


def test_e2e_paper_too_small(tmpdir):
    with pytest.raises(EncodingError):
        test_e2e(tmpdir, "standard", 1, 0, 0, 1, 1, 100, "lorem", "none")

# def test_e2e_magic_bytes(tmpdir):
#     with pytest.raises(DecodingError):
#         test_e2e(tmpdir, "standard", 1, 3, 3, 1, 1, 100, "magic_bytes", "none")

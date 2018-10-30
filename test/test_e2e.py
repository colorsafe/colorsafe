import glob
import os
import pytest
import random

from colorsafe.exceptions import EncodingError

from colorsafe import utils
from colorsafe.decoder.csdecoder_manager import ColorSafeDecoder
from colorsafe.encoder.csencoder_manager import ColorSafeEncoder
from test_utils import texts, in_file_name, image_alterations, out_file_name, metadata_file_name

COLOR_DEPTH_RANGE = range(1, 4)
DEBUG = False

RANDOM_TEST_TRIALS = 3

params_random = {
    ("random_data", "random", "none", 3, 3, 1, 1, 100),
    ("random_data_2_ppd", "random", "none", 3, 3, 2, 2, 100),
}


# TODO: Fix for color depths 2 and 3
@pytest.mark.parametrize('execution_number', range(RANDOM_TEST_TRIALS))
@pytest.mark.parametrize(
    "color_depth",
    range(1, 2))
@pytest.mark.parametrize(
    "test_name,"
    "text_index,"
    "image_alteration,"
    "page_height,"
    "page_width,"
    "dot_fill_pixels,"
    "pixels_per_dot,"
    "printer_dpi",
    params_random)
def test_e2e_random(execution_number,
                    tmpdir,
                    test_name,
                    text_index,
                    image_alteration,
                    color_depth,
                    page_height,
                    page_width,
                    dot_fill_pixels,
                    pixels_per_dot,
                    printer_dpi
                    ):

    # TODO: Test a random unicode string case
    def get_random_string():
        return ''.join(chr(random.randint(0, 2 ** 7 - 1)) for i in range(1000))

    texts['random'] = get_random_string()
    test_e2e(tmpdir,
             test_name,
             text_index,
             image_alteration,
             color_depth,
             page_height,
             page_width,
             dot_fill_pixels,
             pixels_per_dot,
             printer_dpi
             )


# Params: Test Name, Colors, Height, Width, DFP, PPD, DPI, Text index
params = [
    ("standard", "lorem", "none", 11, 8.5, 1, 1, 100),
    ("smaller_page", "lorem", "none", 3, 3, 1, 1, 100),
    ("2_ppd_1_dfp", "lorem", "none", 3, 3, 1, 2, 100),
    ("4_ppd_4_dfp", "lorem", "none", 3, 3, 4, 4, 100),
    ("150_dpi", "lorem", "none", 3, 3, 1, 1, 150),
    ("blur_2", "lorem", "gaussian_blur0.2", 3, 3, 1, 1, 100),
    ("blur_2_dfp_2", "lorem", "gaussian_blur0.2", 3, 3, 2, 2, 100),
    ("rotate_0.1", "lorem", "rotate0.1", 3, 3, 4, 4, 100),
    ("shift_10", "lorem", "shift10", 3, 3, 1, 1, 100),  # TODO: Test more data rows here, e.g. a bigger string
    # ("resize_2.1x", "lorem", "resize2.1x", 3, 3, 1, 1, 100), # TODO: Fix this, decoding needs bilinear interpolation
]


@pytest.mark.parametrize(
    "color_depth",
    COLOR_DEPTH_RANGE)
@pytest.mark.parametrize(
    "test_name,"
    "text_index,"
    "image_alteration,"
    "page_height,"
    "page_width,"
    "dot_fill_pixels,"
    "pixels_per_dot,"
    "printer_dpi",
    params)
def test_e2e(tmpdir,
             test_name,
             text_index,  # Use text index, not text, to avoid an extremely large PyTest test name
             image_alteration,
             color_depth,
             page_height,
             page_width,
             dot_fill_pixels,
             pixels_per_dot,
             printer_dpi
             ):
    """Encode a text file, then decode it and compare the contents to the original file.

    :param test_name Test name, to make it easier to associate pytest results with the test they belong to.
    """

    border_top = 0.2
    border_bottom = border_left = border_right = 0.1

    # Encoding
    in_file = tmpdir.join(in_file_name)

    in_data = texts[text_index]
    in_file.write(in_data)

    if DEBUG and tmpdir:
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

    ColorSafeDecoder(altered_image_paths, color_depth, str(out_file), str(metadata_file), str(tmpdir) if DEBUG else None)

    out_file_contents = out_file.read()

    assert len(out_file_contents) > 0

    # Check for correctness
    assert texts[text_index] == out_file_contents


def test_e2e_paper_too_small(tmpdir):
    with pytest.raises(EncodingError):
        test_e2e(tmpdir, "standard", "lorem", "none", 1, 0, 0, 1, 1, 100)

# def test_e2e_magic_bytes(tmpdir):
#     with pytest.raises(DecodingError):
#         test_e2e(tmpdir, "standard", "magic_bytes", "none", 1, 3, 3, 1, 1, 100)

import glob
import os

import pytest

from colorsafe.exceptions import EncodingError

from colorsafe import utils
from colorsafe.decoder.csdecoder_manager import ColorSafeDecoder
from colorsafe.encoder.csencoder_manager import ColorSafeEncoder
from test_utils import texts, get_random_string, gaussian_blur_image, modify, shift_image, rotate_image, resize_image, \
    no_modify, offset_partial

# TODO: Try a local threshold, rather than sector-wide, for better decoding results.

COLOR_DEPTH_MIN = 1
COLOR_DEPTH_MAX = 3
COLOR_DEPTH_RANGE = range(COLOR_DEPTH_MIN, COLOR_DEPTH_MAX + 1)
DEBUG = False

RANDOM_TEST_TRIALS = 2

params_random = {
    ("random_1000", "random_1000", no_modify, 3, 3, 1, 1, 100),
    # ("random_1000_2_ppd", "random_1000", no_modify, 3, 3, 2, 2, 100),  # TODO: This test is flaky
}


@pytest.mark.parametrize('execution_number', range(RANDOM_TEST_TRIALS))
@pytest.mark.parametrize(
    "color_depth",
    COLOR_DEPTH_RANGE)
@pytest.mark.parametrize(
    "test_name,"
    "text_index,"
    "modify,"
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
                    modify,
                    color_depth,
                    page_height,
                    page_width,
                    dot_fill_pixels,
                    pixels_per_dot,
                    printer_dpi
                    ):

    # TODO: Test a random unicode string case

    texts['random_1000'] = get_random_string(1000)

    test_e2e(tmpdir,
             test_name,
             text_index,
             modify,
             color_depth,
             page_height,
             page_width,
             dot_fill_pixels,
             pixels_per_dot,
             printer_dpi
             )


# Params: Test Name, Colors, Height, Width, DFP, PPD, DPI, Text index
params = [
    ("ansi_letter", "lorem", no_modify, 11, 8.5, 1, 1, 100),
    ("smaller_page", "lorem", no_modify, 3, 3, 1, 1, 100),
    ("multiple_rows", "random_const_3000", no_modify, 3, 3, 1, 1, 100),
    ("multiple_pages", "random_const_20000", no_modify, 3, 3, 1, 1, 100),  # TODO: This works, but pages not filled in
    ("2_ppd_1_dfp", "lorem", no_modify, 3, 3, 1, 2, 100),
    ("4_ppd_4_dfp", "lorem", no_modify, 3, 3, 4, 4, 100),
    ("150_dpi", "lorem", no_modify, 3, 3, 1, 1, 150),
    ("blur_0.2", "lorem", modify(gaussian_blur_image, 0.2), 3, 3, 1, 1, 100),
    ("blur_0.2_dfp_2", "lorem", modify(gaussian_blur_image, 0.2), 3, 3, 2, 2, 100),
    ("rotate_0.2", "lorem", modify(rotate_image, 0.2), 3, 3, 4, 4, 100),
    ("shift_10", "lorem", modify(shift_image, 10), 3, 3, 1, 1, 100),
    ("offset_partial", "lorem", modify(offset_partial, 3.045, 2.981), 3, 3, 1, 1, 100),
    ("resize_2x", "lorem", modify(resize_image, 2, 2), 3, 3, 1, 1, 100),
    ("resize_2.5x", "lorem", modify(resize_image, 2.5, 2.5), 3, 3, 1, 1, 100),
    ("resize_3x", "lorem", modify(resize_image, 3, 3), 3, 3, 1, 1, 100),
    ("resize_2.5x_3x", "lorem", modify(resize_image, 2.5, 3), 3, 3, 1, 1, 100),
]


@pytest.mark.parametrize(
    "color_depth",
    COLOR_DEPTH_RANGE)
@pytest.mark.parametrize(
    "test_name,"
    "text_index,"
    "modify,"
    "page_height,"
    "page_width,"
    "dot_fill_pixels,"
    "pixels_per_dot,"
    "printer_dpi",
    params)
def test_e2e(tmpdir,
             test_name,
             text_index,  # Use text index, not text, to avoid an extremely large PyTest test name
             modify,
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

    in_file_name = "text.txt"
    out_file_name = "out.txt"
    metadata_file_name = "metadata.txt"

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
    desired_wildcard = modify(tmpdir)

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

from PIL import Image
from colorsafe import ColorSafeEncoder, ColorSafeDecoder
import glob
import os
import pytest
import random

in_file_name = "text.txt"
out_file_name = "out.txt"
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

         "random": ''.join(chr(random.randint(0, 2 ** 7 - 1)) for i in range(1000))}  # Random ASCII string


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


image_alterations = {"none": lambda tmpdir: out_image_name_wildcard,
                     "rotate1": lambda tmpdir: rotate_image(tmpdir, 1)
                     }

# Params:  Colors, Height, Width, DFP, PPD, DPI, Text index
params = [(1, 11, 8.5, 1, 1, 100, "lorem", "none"),  # Standard case
          (1, 3, 3, 1, 1, 100, "lorem", "none"),  # Smaller page
          (1, 3, 3, 1, 2, 100, "lorem", "none"),  # 2 Pixels-per-dot
          (1, 3, 3, 1, 1, 150, "lorem", "none"),  # 150 DPI
          (2, 3, 3, 1, 1, 100, "lorem", "none"),  # color-depth = 2
          (3, 3, 3, 1, 1, 100, "lorem", "none"),  # color-depth = 3
          (1, 3, 3, 1, 1, 100, "random", "none"),  # Random string, TODO: This test is flaky
          # (1, 3, 3, 4, 4, 100, "lorem", "rotate1"),  # Rotated by 1 degree, TODO: Fix this test
          ]


@pytest.mark.parametrize(
    "color_depth,page_height,page_width,dot_fill_pixels,pixels_per_dot,printer_dpi,text_index,image_alteration",
    params)
def test_encode_decode(tmpdir,
                       color_depth,
                       page_height,
                       page_width,
                       dot_fill_pixels,
                       pixels_per_dot,
                       printer_dpi,
                       text_index,
                       image_alteration):  # Use text index, not text, to avoid an extremely large PyTest test name
    """Encode a text file, then decode it and compare the contents to the original file.
    """

    border_top = 0.2
    border_bottom = border_left = border_right = 0.1

    # Encoding
    in_file = tmpdir.join(in_file_name)
    in_file.write(texts[text_index])

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

    altered_image_paths = glob.glob(
        os.path.join(
            str(tmpdir),
            desired_wildcard))

    assert altered_image_paths > 0

    ColorSafeDecoder(altered_image_paths, color_depth, str(out_file), False)

    out_file_contents = out_file.read()

    assert len(out_file_contents) > 0

    # Check for correctness
    assert texts[text_index] == out_file_contents


# def test_encode_decode_paper_too_small(tmpdir):
#     with pytest.raises(colorsafe.DecodingError):
#         test_encode_decode(tmpdir, 1, 2, 2, 1, 1, 100, 0)

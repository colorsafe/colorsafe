from colorsafe import ColorSafeEncoder, ColorSafeDecoder, colorsafe
import glob
import os
import pytest
import random

texts = ["Lorem ipsum dolor sit amet, consectetur adipiscing elit. Phasellus sollicitudin tincidunt diam id gravida."
         "Integer gravida risus quis purus bibendum volutpat. Fusce nec scelerisque ipsum. Curabitur nec augue ac"
         "nulla aliquet gravida ut quis justo. Aliquam sagittis nec arcu consectetur fermentum. Duis consectetur"
         "convallis pharetra. Nullam porttitor mi quis risus rhoncus malesuada nec vitae ex. Nunc non mattis justo."
         "Sed pellentesque, nulla vitae sagittis pulvinar, massa dui pellentesque sapien, vel dignissim lorem nisi sit"
         "amet augue. Nam rhoncus leo non urna sodales, vitae elementum magna viverra. Aliquam aliquam eu neque vel"
         "dictum. Nulla fermentum placerat elit. Vivamus non augue congue, maximus sem non, mollis nulla. Donec non"
         "elit purus.",
         ''.join(chr(random.randint(0, 2 ** 7 - 1)) for i in range(1000))]  # Random ASCII string

# Params:  Colors, Height, Width, DFP, PPD, DPI, Text index
params = [(1, 11, 8.5, 1, 1, 100, 0),  # Standard case
          (1, 3, 3, 1, 1, 100, 0),  # Smaller page
          (1, 3, 3, 1, 2, 100, 0),  # 2 Pixels-per-dot
          (1, 3, 3, 1, 1, 150, 0),  # 150 DPI
          (2, 3, 3, 1, 1, 100, 0),  # color-depth = 2
          (3, 3, 3, 1, 1, 100, 0),  # color-depth = 3
          (1, 3, 3, 1, 1, 100, 1),  # Random string
          ]


@pytest.mark.parametrize("color_depth,page_height,page_width,dot_fill_pixels,pixels_per_dot,printer_dpi,text_index",
                         params)
def test_encode_decode(tmpdir,
                       color_depth,
                       page_height,
                       page_width,
                       dot_fill_pixels,
                       pixels_per_dot,
                       printer_dpi,
                       text_index):  # Use text index, not text, to avoid an extremely large PyTest test name
    """Encode a text file, then decode it and compare the contents to the original file.
    """
    in_file_name = "text.txt"
    out_file_name = "out.txt"
    out_image_name_wildcard = "out_*.png"

    border_top = 0.2
    border_bottom = border_left = border_right = 0.1

    # Encoding
    in_file = tmpdir.join(in_file_name)
    in_file.write(texts[text_index])

    ColorSafeEncoder(str(in_file), color_depth, page_height, page_width, border_top, border_bottom, border_left,
                     border_right, dot_fill_pixels, pixels_per_dot, printer_dpi, str(tmpdir), True, True)

    # Decoding
    out_file = tmpdir.join(out_file_name)

    out_image_paths = glob.glob(os.path.join(str(tmpdir), out_image_name_wildcard))

    assert out_image_paths > 0

    ColorSafeDecoder(out_image_paths, color_depth, str(out_file), False)

    out_file_contents = out_file.read()

    assert len(out_file_contents) > 0

    # Check for correctness
    assert texts[text_index] == out_file_contents


# def test_encode_decode_paper_too_small(tmpdir):
#     with pytest.raises(colorsafe.DecodingError):
#         test_encode_decode(tmpdir, 1, 2, 2, 1, 1, 100, 0)

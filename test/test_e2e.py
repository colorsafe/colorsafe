from colorsafe import ColorSafeEncoder, ColorSafeDecoder
import os
import pytest


text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Phasellus sollicitudin tincidunt diam id gravida." \
       "Integer gravida risus quis purus bibendum volutpat. Fusce nec scelerisque ipsum. Curabitur nec augue ac" \
       "nulla aliquet gravida ut quis justo. Aliquam sagittis nec arcu consectetur fermentum. Duis consectetur" \
       "convallis pharetra. Nullam porttitor mi quis risus rhoncus malesuada nec vitae ex. Nunc non mattis justo." \
       "Sed pellentesque, nulla vitae sagittis pulvinar, massa dui pellentesque sapien, vel dignissim lorem nisi sit" \
       "amet augue. Nam rhoncus leo non urna sodales, vitae elementum magna viverra. Aliquam aliquam eu neque vel" \
       "dictum. Nulla fermentum placerat elit. Vivamus non augue congue, maximus sem non, mollis nulla. Donec non" \
       "elit purus."

# Test defaults
defaults = [(1, 11, 8.5, 0.2, 0.1, 0.1, 0.1, 1, 1, 100, ["out_0.png"], "out.txt")]


@pytest.mark.parametrize("color_depth,page_height,page_width,border_top,border_bottom,border_left,border_right,"
                         "dot_fill_pixels,pixels_per_dot,printer_dpi,out_image_names,out_file_name",
                         defaults)
def test_encode_decode(tmpdir, color_depth, page_height, page_width, border_top, border_bottom, border_left,
                       border_right, dot_fill_pixels, pixels_per_dot, printer_dpi,
                       out_image_names, out_file_name):
    """Encode a text file, then decode it and compare the contents to the original file.
    """
    in_file_name = "text.txt"

    in_file = tmpdir.join(in_file_name)
    in_file.write(text)

    ColorSafeEncoder(str(in_file), color_depth, page_height, page_width, border_top, border_bottom, border_left,
                     border_right, dot_fill_pixels, pixels_per_dot, printer_dpi, str(tmpdir), True, True)

    out_file = tmpdir.join(out_file_name)

    out_image_paths = list()
    for name in out_image_names:
        out_image_path = tmpdir.join(name)
        out_image_paths.append(str(out_image_path))

    ColorSafeDecoder(out_image_paths, color_depth, str(out_file), False)

    out_file_contents = out_file.read()

    assert len(out_file_contents) > 0
    assert text == out_file_contents
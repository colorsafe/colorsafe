from colorsafe.decoder.csdecoder_getbounds import infer_border_angled_lines, remove_outliers, transpose_and_infer


def test_remove_outliers():
    slope_list = [0.0, 0.7339, 0.0, 0.0, 1.4545, 0.0, 0.0, -1.4545, -0.7272, 0.0]

    expected_corrected_slope_list = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    corrected_slope_list = remove_outliers(slope_list)

    assert expected_corrected_slope_list == corrected_slope_list


def test_remove_outliers_big():
    intercept_list = [330.4035087719298, 246.70044052863437, 218.04985337243403, 203.75604395604395, 195.25,
                      189.52492668621701, 185.4704402515723, 182.24532453245325, 179.87781036168133, 178.0, 176.4496,
                      175.16874541452677, 173.9790115098172, 173.04902576995602, 172.25, 171.54455445544554,
                      170.9223602484472, 27.265486725663717, 26.12775330396476, 25.75073313782991, 25.56387665198238,
                      25.450704225352112, 25.375917767988252, 25.0, 25.0, 25.0, 25.0, 25.0, 24.81217901687454,
                      24.826675693974273, 24.838993710691824, 24.849765258215964, 24.85918591859186] + ([24] * 100)

    expected_corrected_intercept_list = ([24]) * 100

    corrected_intercept_list = remove_outliers(intercept_list)

    assert expected_corrected_intercept_list == corrected_intercept_list


def test_infer_border_angled_lines_horizontal():
    horizontal_borders = [
        [(3, 48), (3, 146), (3, 244), (3, 341), (3, 439), (3, 537), (3, 635), (3, 732), (3, 830), (3, 928), (3, 1026)],
        [(271, 48), (271, 146), (271, 244), (271, 341), (271, 439), (271, 537), (271, 635), (271, 732), (271, 830),
         (271, 928), (271, 1026)]]

    expected_horizontal_border_angles_lines = [(0.0, 3.0), (0.0, 271.0)]

    horizontal_border_angles_lines = infer_border_angled_lines(horizontal_borders, False)

    assert expected_horizontal_border_angles_lines == horizontal_border_angles_lines


def test_infer_border_angled_lines_vertical1():
    vertical_borders = [[(27, 3), (81, 3), (136, 3), (191, 3), (246, 3)],
                        [(27, 271), (81, 271), (136, 271), (191, 271), (246, 271)],
                        [(27, 539), (81, 539), (136, 619), (191, 539), (246, 539)],
                        [(27, 807), (81, 807), (136, 807), (191, 807), (246, 807)],
                        [(27, 1075), (81, 1075), (136, 1075), (191, 1075), (246, 1075)]]

    expected_vertical_border_angled_lines = [(0.0, 3.0), (0.0, 271.0), (0.0, 539),
                                             (0.0, 807.0),
                                             (0.0, 1075.0)]
    vertical_border_angled_lines = infer_border_angled_lines(vertical_borders, True)

    assert expected_vertical_border_angled_lines == vertical_border_angled_lines


def test_infer_border_angled_lines_vertical2():
    vertical_borders = [
        [(142, 161), (256, 25), (369, 24), (483, 24), (597, 24), (710, 24), (824, 24), (937, 24), (1051, 25),
         (1165, 25), (1278, 25), (1392, 25), (1505, 25), (1619, 26), (1733, 26), (1846, 26), (1960, 26), (2074, 26)]]

    expected_vertical_border_angled_lines = [(0.0011298489551477484, 23.608754280666897)]
    vertical_border_angled_lines = infer_border_angled_lines(vertical_borders, True)

    assert expected_vertical_border_angled_lines == vertical_border_angled_lines


def test_tranpose_infer_horizontal():
    horizontal_borders = [[],
                          [(0, 80), (0, 133), (0, 243)],
                          [(67, 26), (67, 83), (67, 133), (67, 187), (67, 241)],
                          [(134, 27), (134, 79), (134, 190)],
                          [(134, 240)]]

    expected_bounds = [[(67, 26), (134, 27)],
                       [(0, 80), (67, 83), (134, 79)],
                       [(0, 133), (67, 133)],
                       [(67, 187), (134, 190)],
                       [(0, 243), (67, 241), (134, 240)]]

    bounds = transpose_and_infer(horizontal_borders, False)

    assert expected_bounds == bounds


def test_tranpose_infer_vertical():
    horizontal_borders = [[],
                          [(80, 0), (133, 0), (243, 0)],
                          [(26, 67), (83, 67), (133, 67), (187, 67), (241, 67)],
                          [(27, 134), (79, 134), (190, 134)],
                          [(240, 134)]]

    expected_bounds = [[(26, 67), (27, 134)],
                       [(80, 0), (83, 67), (79, 134)],
                       [(133, 0), (133, 67)],
                       [(187, 67), (190, 134)],
                       [(243, 0), (241, 67), (240, 134)]]

    bounds = transpose_and_infer(horizontal_borders, True)

    assert expected_bounds == bounds

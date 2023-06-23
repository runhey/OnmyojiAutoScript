# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey


def _merge_area(area1, area2):
    xa1, ya1, xa2, ya2 = area1
    xb1, yb1, xb2, yb2 = area2
    return min(xa1, xb1), min(ya1, yb1), max(xa2, xb2), max(ya2, yb2)

def merge_area(areas: list[tuple]) -> tuple:
    """
    合并多个区域
    :param areas:
    :return:
    """
    if not areas:
        return 0, 0, 0, 0
    area = areas[0]
    for i in range(1, len(areas)):
        area = _merge_area(area, areas[i])
    return area


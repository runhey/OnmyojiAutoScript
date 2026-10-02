"""
Tests for script.misc.op.area

Point and Area are tuple subclasses with a large geometry API. Alasio has no
reference tests for them; the expectations below were derived from the source.
"""
import pytest

from script.misc.op import Area, Point


class TestPointConstruction:
    def test_is_a_tuple(self):
        point = Point((1, 2))
        assert isinstance(point, tuple)
        assert tuple(point) == (1, 2)

    def test_zero_and_one(self):
        assert Point.zero() == (0, 0)
        assert Point.one() == (1, 1)
        assert isinstance(Point.zero(), Point)


class TestPointAsInt:
    def test_rounds_by_default(self):
        assert Point((1.4, 2.6)).as_int() == (1, 3)

    def test_truncates_when_disabled(self):
        assert Point((1.9, -1.9)).as_int(round_value=False) == (1, -1)

    def test_returns_a_point(self):
        assert isinstance(Point((1.4, 2.6)).as_int(), Point)


class TestPointAccessors:
    def test_x_and_y(self):
        point = Point((3, 4))
        assert point.x == 3
        assert point.y == 4

    def test_with_x(self):
        assert Point((3, 4)).with_x(9) == (9, 4)

    def test_with_y(self):
        assert Point((3, 4)).with_y(9) == (3, 9)

    def test_move(self):
        assert Point((3, 4)).move(Point((10, -2))) == (13, 2)

    def test_move_axis(self):
        assert Point((3, 4)).move_x(10) == (13, 4)
        assert Point((3, 4)).move_y(10) == (3, 14)


class TestPointArithmetic:
    def test_add(self):
        assert Point((1, 2)) + Point((3, 4)) == (4, 6)
        assert Point((1, 2)) + 3 == (4, 5)
        assert 3 + Point((1, 2)) == (4, 5)

    def test_sub(self):
        assert Point((1, 2)) - Point((3, 4)) == (-2, -2)
        assert Point((1, 2)) - 3 == (-2, -1)
        assert 3 - Point((1, 2)) == (2, 1)

    def test_mul(self):
        assert Point((1, 2)) * Point((3, 4)) == (3, 8)
        assert Point((1, 2)) * 3 == (3, 6)
        assert 3 * Point((1, 2)) == (3, 6)

    def test_true_div(self):
        assert Point((4, 6)) / 2 == (2, 3)
        assert Point((4, 6)) / Point((2, 3)) == (2, 2)
        assert 2 / Point((4, 2)) == (0.5, 1.0)

    def test_floor_div(self):
        assert Point((7, 8)) // 3 == (2, 2)
        assert 7 // Point((2, 4)) == (3, 1)

    def test_mod(self):
        assert Point((7, 8)) % 3 == (1, 2)

    def test_neg_and_abs(self):
        assert -Point((1, -2)) == (-1, 2)
        assert abs(Point((-1, -2))) == (1, 2)

    def test_result_is_a_point(self):
        assert isinstance(Point((1, 2)) + 1, Point)


class TestPointVectorMath:
    def test_magnitude(self):
        assert Point((3, 4)).magnitude() == 5.0

    def test_normalize(self):
        assert Point((3, 4)).normalize() == (0.6, 0.8)

    def test_normalize_zero_vector(self):
        assert Point((0, 0)).normalize() == (0, 0)

    def test_dot(self):
        assert Point((1, 2)).dot(Point((3, 4))) == 11

    def test_cross(self):
        assert Point((1, 2)).cross(Point((3, 4))) == -2


class TestPointBounds:
    def test_is_in_screen_includes_the_bounds(self):
        assert Point((0, 0)).is_in_screen((10, 10)) is True
        assert Point((10, 10)).is_in_screen((10, 10)) is True

    def test_is_in_screen_rejects_outside(self):
        assert Point((11, 5)).is_in_screen((10, 10)) is False
        assert Point((-1, 5)).is_in_screen((10, 10)) is False

    def test_is_in_area(self):
        area = Area((2, 3, 10, 20))
        assert Point((2, 3)).is_in_area(area) is True
        assert Point((10, 20)).is_in_area(area) is True
        assert Point((11, 20)).is_in_area(area) is False

    def test_limit_in_screen(self):
        assert Point((-5, 200)).limit_in_screen((100, 100)) == (0, 100)
        assert Point((50, 60)).limit_in_screen((100, 100)) == (50, 60)

    def test_limit_in_area(self):
        area = Area((10, 10, 20, 20))
        assert Point((0, 0)).limit_in_area(area) == (10, 10)
        assert Point((50, 50)).limit_in_area(area) == (20, 20)
        assert Point((15, 15)).limit_in_area(area) == (15, 15)


class TestPointDistance:
    def test_distance_to_point(self):
        assert Point((0, 0)).distance_to(Point((3, 4))) == 5.0

    def test_distance_to_area_uses_the_closest_point(self):
        assert Point((0, 0)).distance_to(Area((3, 4, 10, 10))) == 5.0

    def test_distance_to_area_is_zero_when_inside(self):
        assert Point((5, 5)).distance_to(Area((3, 4, 10, 10))) == 0.0

    def test_distance_x_to(self):
        assert Point((0, 0)).distance_x_to(Point((7, 3))) == 7
        assert Point((0, 0)).distance_x_to(Area((0, 0, 3, 3))) == 0
        assert Point((10, 0)).distance_x_to(Area((0, 0, 3, 3))) == 7

    def test_distance_y_to(self):
        assert Point((0, 0)).distance_y_to(Point((3, -4))) == 4
        assert Point((0, 10)).distance_y_to(Area((0, 0, 3, 3))) == 7

    def test_manhattan_to_point(self):
        assert Point((0, 0)).manhattan_to(Point((5, -3))) == 8

    def test_manhattan_to_area(self):
        assert Point((0, 0)).manhattan_to(Area((3, 4, 10, 10))) == 7


class TestPointToPositive:
    def test_negative_values_are_mirrored_from_resolution(self):
        assert Point((-10, -20)).to_positive((100, 100)) == (90, 80)

    def test_all_positive_returns_self(self):
        point = Point((50, 60))
        assert point.to_positive((100, 100)) is point


class TestAreaConstruction:
    def test_is_a_tuple(self):
        area = Area((0, 0, 10, 20))
        assert isinstance(area, tuple)
        assert tuple(area) == (0, 0, 10, 20)

    def test_zero_and_one(self):
        assert Area.zero() == (0, 0, 0, 0)
        assert Area.one() == (1, 1, 1, 1)

    def test_from_xywh(self):
        assert Area.from_xywh((10, 20, 30, 40)) == (10, 20, 40, 60)

    def test_to_xywh(self):
        assert Area((10, 20, 40, 60)).to_xywh() == (10, 20, 30, 40)

    def test_from_size(self):
        assert Area.from_size((100, 50)) == (0, 0, 100, 50)


class TestAreaAsInt:
    def test_rounds_by_default(self):
        assert Area((1.4, 2.6, 3.4, 4.6)).as_int() == (1, 3, 3, 5)

    def test_truncates_when_disabled(self):
        assert Area((1.9, 2.9, -1.9, 4.9)).as_int(round_value=False) == (1, 2, -1, 4)


class TestAreaEdges:
    def test_xy_properties(self):
        area = Area((1, 2, 3, 4))
        assert (area.x1, area.y1, area.x2, area.y2) == (1, 2, 3, 4)

    def test_with_edges(self):
        area = Area((1, 2, 3, 4))
        assert area.with_x1(9) == (9, 2, 3, 4)
        assert area.with_y1(9) == (1, 9, 3, 4)
        assert area.with_x2(9) == (1, 2, 9, 4)
        assert area.with_y2(9) == (1, 2, 3, 9)

    def test_corners(self):
        area = Area((0, 0, 10, 20))
        assert area.upperleft == (0, 0)
        assert area.upperright == (10, 0)
        assert area.bottomleft == (0, 20)
        assert area.bottomright == (10, 20)

    def test_size_and_center(self):
        area = Area((10, 20, 40, 80))
        assert area.size() == (30, 60)
        assert area.center() == (25, 50)


class TestAreaWithCorner:
    def test_with_corners_keep_size(self):
        area = Area((0, 0, 10, 20))
        target = Point((100, 100))
        assert area.with_upperleft(target) == (100, 100, 110, 120)
        assert area.with_upperright(target) == (90, 100, 100, 120)
        assert area.with_bottomleft(target) == (100, 80, 110, 100)
        assert area.with_bottomright(target) == (90, 80, 100, 100)

    def test_with_center_keeps_size(self):
        assert Area((0, 0, 10, 20)).with_center(Point((100, 100))) == (95, 90, 105, 110)


class TestAreaValid:
    def test_needs_a_positive_size(self):
        assert Area((0, 0, 1, 1)).valid is True
        assert Area((0, 0, 0, 1)).valid is False
        assert Area((0, 0, 1, 0)).valid is False
        assert Area.one().valid is False


class TestAreaContainment:
    def test_is_in_screen(self):
        assert Area((0, 0, 100, 100)).is_in_screen((100, 100)) is True
        assert Area((0, 0, 101, 100)).is_in_screen((100, 100)) is False
        assert Area((-1, 0, 10, 10)).is_in_screen((100, 100)) is False

    def test_is_in_area(self):
        assert Area((2, 2, 3, 3)).is_in_area(Area((0, 0, 10, 10))) is True
        assert Area((2, 2, 11, 3)).is_in_area(Area((0, 0, 10, 10))) is False

    def test_limit_in_screen(self):
        assert Area((-5, -5, 150, 150)).limit_in_screen((100, 100)) == (0, 0, 100, 100)

    def test_limit_in_area(self):
        assert Area((-5, -5, 50, 50)).limit_in_area(Area((0, 0, 10, 10))) == (0, 0, 10, 10)

    def test_is_intersect_area(self):
        assert Area((0, 0, 10, 10)).is_intersect_area(Area((5, 5, 15, 15))) is True
        assert Area((0, 0, 10, 10)).is_intersect_area(Area((20, 20, 30, 30))) is False
        # touching edges still count as an intersection
        assert Area((0, 0, 10, 10)).is_intersect_area(Area((10, 10, 20, 20))) is True


class TestAreaTransform:
    def test_move(self):
        area = Area((10, 20, 30, 40))
        assert area.move(Point((5, -5))) == (15, 15, 35, 35)
        assert area.move_x(5) == (15, 20, 35, 40)
        assert area.move_y(-5) == (10, 15, 30, 35)

    def test_move_onto_upperleft(self):
        assert Area((1, 2, 3, 4)).move_onto_upperleft(Area((10, 20, 99, 99))) == (11, 22, 13, 24)

    def test_inset_outset(self):
        area = Area((10, 20, 30, 40))
        assert area.inset(2) == (12, 22, 28, 38)
        assert area.outset(2) == (8, 18, 32, 42)

    def test_inset_outset_xy(self):
        area = Area((10, 20, 30, 40))
        assert area.inset_xy((1, 3)) == (11, 23, 29, 37)
        assert area.outset_xy((1, 3)) == (9, 17, 31, 43)


class TestAreaAlign:
    def test_align_left_right(self):
        area = Area((0, 0, 10, 20))
        assert area.align_left(100) == (100, 0, 110, 20)
        assert area.align_right(100) == (90, 0, 100, 20)

    def test_align_top_bottom(self):
        area = Area((0, 0, 10, 20))
        assert area.align_top(100) == (0, 100, 10, 120)
        assert area.align_bottom(100) == (0, 80, 10, 100)

    def test_align_center(self):
        area = Area((0, 0, 10, 20))
        assert area.align_center_x(100) == (95, 0, 105, 20)
        assert area.align_center_y(100) == (0, 90, 10, 110)
        assert area.align_center(100, 100) == (95, 90, 105, 110)


class TestAreaDistance:
    def test_distance_to_point(self):
        area = Area((0, 0, 10, 10))
        assert area.distance_to(Point((15, 5))) == 5.0
        assert area.distance_to(Point((5, 5))) == 0.0

    def test_distance_to_area(self):
        area = Area((0, 0, 10, 10))
        assert area.distance_to(Area((13, 14, 20, 20))) == 5.0
        assert area.distance_to(Area((5, 5, 15, 15))) == 0.0

    def test_distance_axis_to_point(self):
        area = Area((0, 0, 10, 10))
        assert area.distance_x_to(Point((15, 5))) == 5
        assert area.distance_y_to(Point((15, 5))) == 0
        assert area.distance_x_to(Point((5, 5))) == 0

    def test_manhattan_to_point(self):
        assert Area((0, 0, 10, 10)).manhattan_to(Point((15, 14))) == 9

    def test_manhattan_to_area(self):
        assert Area((0, 0, 10, 10)).manhattan_to(Area((13, 14, 20, 20))) == 7


class TestAreaToPositive:
    def test_negative_values_are_mirrored(self):
        assert Area((-10, -20, 50, 60)).to_positive((100, 100)) == (90, 80, 50, 60)

    def test_all_positive_returns_self(self):
        area = Area((1, 2, 3, 4))
        assert area.to_positive((100, 100)) is area

class Point(tuple):
    @classmethod
    def zero(cls) -> "Point":
        return cls((0, 0))

    @classmethod
    def one(cls) -> "Point":
        return cls((1, 1))

    def as_int(self, round_value=True) -> "Point":
        """
        Ensure X Y are integer
        """
        x, y = self
        if round_value:
            return Point((int(round(x)), int(round(y))))
        else:
            return Point((int(x), int(y)))

    @property
    def x(self) -> int:
        return self[0]

    @property
    def y(self) -> int:
        return self[1]

    def with_x(self, x: int) -> "Point":
        """
        Set x
        """
        return Point((x, self[1]))

    def with_y(self, y: int) -> "Point":
        """
        Set y
        """
        return Point((self[0], y))

    def move(self, vector: "Point") -> "Point":
        """
        Move point
        """
        return Point((self[0] + vector[0], self[1] + vector[1]))

    def move_x(self, value) -> "Point":
        """
        Move point along X axis
        """
        return Point((self[0] + value, self[1]))

    def move_y(self, value) -> "Point":
        """
        Move point along Y axis
        """
        return Point((self[0], self[1] + value))

    def __add__(self, other):
        if isinstance(other, Point):
            # point + point
            return Point((self[0] + other[0], self[1] + other[1]))
        else:
            # point + number
            return Point((self[0] + other, self[1] + other))

    def __sub__(self, other):
        if isinstance(other, Point):
            return Point((self[0] - other[0], self[1] - other[1]))
        else:
            return Point((self[0] - other, self[1] - other))

    def __mul__(self, other):
        if isinstance(other, Point):
            return Point((self[0] * other[0], self[1] * other[1]))
        else:
            return Point((self[0] * other, self[1] * other))

    def __truediv__(self, other):
        if isinstance(other, Point):
            return Point((self[0] / other[0], self[1] / other[1]))
        else:
            return Point((self[0] / other, self[1] / other))

    def __floordiv__(self, other):
        if isinstance(other, Point):
            return Point((self[0] // other[0], self[1] // other[1]))
        else:
            return Point((self[0] // other, self[1] // other))

    def __mod__(self, other):
        if isinstance(other, Point):
            return Point((self[0] % other[0], self[1] % other[1]))
        else:
            return Point((self[0] % other, self[1] % other))

    def __neg__(self):
        return Point((-self[0], -self[1]))

    def __abs__(self):
        return Point((abs(self[0]), abs(self[1])))

    def __radd__(self, other):
        return self.__add__(other)

    def __rsub__(self, other):
        if isinstance(other, Point):
            return Point((other[0] - self[0], other[1] - self[1]))
        else:
            return Point((other - self[0], other - self[1]))

    def __rmul__(self, other):
        return self.__mul__(other)

    def __rtruediv__(self, other):
        if isinstance(other, Point):
            return Point((other[0] / self[0], other[1] / self[1]))
        else:
            return Point((other / self[0], other / self[1]))

    def __rfloordiv__(self, other):
        if isinstance(other, Point):
            return Point((other[0] // self[0], other[1] // self[1]))
        else:
            return Point((other // self[0], other // self[1]))

    def magnitude(self) -> float:
        """
        Calculate the magnitude (length) of the point vector
        """
        return (self[0] ** 2 + self[1] ** 2) ** 0.5

    def normalize(self) -> "Point":
        """
        Return a normalized point (unit vector)
        """
        mag = self.magnitude()
        if mag == 0:
            return Point((0, 0))
        return Point((self[0] / mag, self[1] / mag))

    def dot(self, other: "Point") -> float:
        """
        Dot product with another point
        """
        return self[0] * other[0] + self[1] * other[1]

    def cross(self, other: "Point") -> float:
        """
        2D cross product (returns scalar z-component)
        """
        return self[0] * other[1] - self[1] * other[0]

    def is_in_screen(self, res: "tuple[int, int]") -> bool:
        """
        Check if the point is within (0, 0, resolution_x - 1, resolution_y - 1)
        """
        px, py = self
        rx, ry = res
        return 0 <= px <= rx and 0 <= py <= ry

    def is_in_area(self, area: "Area") -> bool:
        """
        Check if the point is within the area
        """
        px, py = self
        x1, y1, x2, y2 = area
        return x1 <= px <= x2 and y1 <= py <= y2

    def limit_in_screen(self, res: "tuple[int, int]") -> "Point":
        """
        Limit area within (0, 0, resolution_x, resolution_y)
        """
        px, py = self
        rx, ry = res
        if px < 0:
            px = 0
        if px > rx:
            px = rx
        if py < 0:
            py = 0
        if py > ry:
            py = ry
        return Point((px, py))

    def limit_in_area(self, area: "Area") -> "Point":
        """
        Limit point within area
        """
        px, py = self
        x1, y1, x2, y2 = area
        if px < x1:
            px = x1
        if px > x2:
            px = x2
        if py < y1:
            py = y1
        if py > y2:
            py = y2
        return Point((px, py))

    def distance_to(self, target: "Point | Area") -> float:
        """
        Euclidean distance to target
        For Area target, calculates distance to the closest point on the area
        """
        px, py = self
        if isinstance(target, Area):
            x1, y1, x2, y2 = target
            if px < x1:
                closest_x = x1
            elif px > x2:
                closest_x = x2
            else:
                closest_x = px
            if py < y1:
                closest_y = y1
            elif py > y2:
                closest_y = y2
            else:
                closest_y = py
            dx = px - closest_x
            dy = py - closest_y
            return (dx * dx + dy * dy) ** 0.5
        else:
            tx, ty = target
            dx = px - tx
            dy = py - ty
            return (dx * dx + dy * dy) ** 0.5

    def distance_x_to(self, target: "Point | Area") -> int:
        """
        X-axis distance to target
        For Area target, calculates X distance to the closest edge
        """
        px, py = self
        if isinstance(target, Area):
            x1, y1, x2, y2 = target
            if px < x1:
                return x1 - px
            elif px > x2:
                return px - x2
            else:
                return 0
        else:
            tx, ty = target
            dx = px - tx
            if dx < 0:
                dx = -dx
            return dx

    def distance_y_to(self, target: "Point | Area") -> int:
        """
        Y-axis distance to target
        For Area target, calculates Y distance to the closest edge
        """
        px, py = self
        if isinstance(target, Area):
            x1, y1, x2, y2 = target
            if py < y1:
                return y1 - py
            elif py > y2:
                return py - y2
            else:
                return 0
        else:
            tx, ty = target
            dy = py - ty
            if dy < 0:
                dy = -dy
            return dy

    def manhattan_to(self, target: "Point | Area") -> int:
        """
        Manhattan distance to target
        For Area target, calculates Manhattan distance to the closest point on the area
        """
        px, py = self
        if isinstance(target, Area):
            x1, y1, x2, y2 = target
            # Calculate closest_x
            if px < x1:
                closest_x = x1
            elif px > x2:
                closest_x = x2
            else:
                closest_x = px
            # Calculate closest_y
            if py < y1:
                closest_y = y1
            elif py > y2:
                closest_y = y2
            else:
                closest_y = py
            # Calculate distances
            dx = px - closest_x
            if dx < 0:
                dx = -dx
            dy = py - closest_y
            if dy < 0:
                dy = -dy
            return dx + dy
        else:
            tx, ty = target
            dx = px - tx
            if dx < 0:
                dx = -dx
            dy = py - ty
            if dy < 0:
                dy = -dy
            return dx + dy

    def to_positive(self, res: "tuple[int, int]") -> "Point":
        """
        Convert negative indices to positive indices based on resolution
        Similar to Python's negative indexing for arrays

        For a resolution (width, height):
        - Negative x value is converted: x -> width + x
        - Negative y value is converted: y -> height + y
        - Positive values remain unchanged

        Example:
            res = (100, 100)
            Point((-10, -20)).to_positive(res) -> Point((90, 80))
            Point((-1, -1)).to_positive(res) -> Point((99, 99))
            Point((50, 60)).to_positive(res) -> Point((50, 60))
        """
        px, py = self
        if px >= 0 and py >= 0:
            return self
        rx, ry = res
        if px < 0:
            px = rx + px
        if py < 0:
            py = ry + py
        return Point((px, py))


class Area(tuple):
    @classmethod
    def zero(cls) -> "Area":
        return cls((0, 0, 0, 0))

    @classmethod
    def one(cls) -> "Area":
        return cls((1, 1, 1, 1))

    def as_int(self, round_value=True) -> "Area":
        """
        Ensure X Y are integer
        """
        x1, y1, x2, y2 = self
        if round_value:
            return Area((int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))))
        else:
            return Area((int(x1), int(y1), int(x2), int(y2)))

    @classmethod
    def from_xywh(cls, xywh: "tuple[int, int, int, int]") -> "Area":
        """
        Convert a xywh area to xyxy area
        """
        x, y, w, h = xywh
        return cls((x, y, x + w, y + h))

    def to_xywh(self) -> "tuple[int, int, int, int]":
        """
        Convert xyxy area to xywh format
        """
        x1, y1, x2, y2 = self
        return x1, y1, x2 - x1, y2 - y1

    @classmethod
    def from_size(cls, size: "tuple[int, int]") -> "Area":
        """
        Convert size (x, y) to Area((0, 0, x, y))
        """
        x, y = size
        return Area((0, 0, x, y))

    @property
    def x1(self) -> int:
        return self[0]

    @property
    def y1(self) -> int:
        return self[1]

    @property
    def x2(self) -> int:
        return self[2]

    @property
    def y2(self) -> int:
        return self[3]

    def with_x1(self, x: int) -> "Area":
        """
        Set left boundary (x1)
        """
        return Area((x, self[1], self[2], self[3]))

    def with_y1(self, y: int) -> "Area":
        """
        Set top boundary (y1)
        """
        return Area((self[0], y, self[2], self[3]))

    def with_x2(self, x: int) -> "Area":
        """
        Set right boundary (x2)
        """
        return Area((self[0], self[1], x, self[3]))

    def with_y2(self, y: int) -> "Area":
        """
        Set bottom boundary (y2)
        """
        return Area((self[0], self[1], self[2], y))

    @property
    def upperleft(self) -> "Point":
        return Point((self[0], self[1]))

    @property
    def upperright(self) -> "Point":
        return Point((self[2], self[1]))

    @property
    def bottomleft(self) -> "Point":
        return Point((self[0], self[3]))

    @property
    def bottomright(self) -> "Point":
        return Point((self[2], self[3]))

    def with_upperleft(self, point: "Point") -> "Area":
        """
        Set upper-left corner position, maintaining size
        """
        x1, y1, x2, y2 = self
        px, py = point
        width = x2 - x1
        height = y2 - y1
        return Area((px, py, px + width, py + height))

    def with_upperright(self, point: "Point") -> "Area":
        """
        Set upper-right corner position, maintaining size
        """
        x1, y1, x2, y2 = self
        px, py = point
        width = x2 - x1
        height = y2 - y1
        return Area((px - width, py, px, py + height))

    def with_bottomleft(self, point: "Point") -> "Area":
        """
        Set bottom-left corner position, maintaining size
        """
        x1, y1, x2, y2 = self
        px, py = point
        width = x2 - x1
        height = y2 - y1
        return Area((px, py - height, px + width, py))

    def with_bottomright(self, point: "Point") -> "Area":
        """
        Set bottom-right corner position, maintaining size
        """
        x1, y1, x2, y2 = self
        px, py = point
        width = x2 - x1
        height = y2 - y1
        return Area((px - width, py - height, px, py))

    def with_center(self, point: "Point") -> "Area":
        """
        Set center position, maintaining size
        """
        x1, y1, x2, y2 = self
        cx, cy = point
        half_width = (x2 - x1) // 2
        half_height = (y2 - y1) // 2
        return Area((cx - half_width, cy - half_height, cx + half_width, cy + half_height))

    @property
    def valid(self) -> bool:
        """
        Area should be at least 1x1, otherwise invalid
        """
        x1, y1, x2, y2 = self
        return x2 > x1 and y2 > y1

    def is_in_screen(self, res: "tuple[int, int]") -> bool:
        """
        Check if area is within (0, 0, resolution_x, resolution_y)
        """
        x1, y1, x2, y2 = self
        rx, ry = res
        return 0 <= x1 and 0 <= y1 and 0 <= x2 and 0 <= y2 and x1 <= rx and y1 <= ry and x2 <= rx and y2 <= ry

    def is_in_area(self, area: "Area") -> bool:
        """
        Check if area is within another area
        """
        x1, y1, x2, y2 = self
        ax1, ay1, ax2, ay2 = area
        return (ax1 <= x1 and ay1 <= y1 and ax1 <= x2 and ay1 <= y2
                and x1 <= ax2 and y1 <= ay2 and x2 <= ax2 and y2 <= ay2)

    def limit_in_screen(self, res: "tuple[int, int]") -> "Area":
        """
        Limit area within (0, 0, resolution_x, resolution_y)
        """
        x1, y1, x2, y2 = self
        rx, ry = res
        if x1 < 0:
            x1 = 0
        if y1 < 0:
            y1 = 0
        if x2 < 0:
            x2 = 0
        if y2 < 0:
            y2 = 0
        if x1 > rx:
            x1 = rx
        if y1 > ry:
            y1 = ry
        if x2 > rx:
            x2 = rx
        if y2 > ry:
            y2 = ry
        return Area((x1, y1, x2, y2))

    def limit_in_area(self, area: "Area") -> "Area":
        """
        Limit area within another area
        """
        x1, y1, x2, y2 = self
        ax1, ay1, ax2, ay2 = area
        if x1 < ax1:
            x1 = ax1
        if y1 < ay1:
            y1 = ay1
        if x2 < ax1:
            x2 = ax1
        if y2 < ay1:
            y2 = ay1
        if x1 > ax2:
            x1 = ax2
        if y1 > ay2:
            y1 = ay2
        if x2 > ax2:
            x2 = ax2
        if y2 > ay2:
            y2 = ay2
        return Area((x1, y1, x2, y2))

    def is_intersect_area(self, area: "Area") -> bool:
        """
        Check if this area intersects with another area
        https://www.yiiven.cn/rect-is-intersection.html
        """
        x1, y1, x2, y2 = self
        ax1, ay1, ax2, ay2 = area
        diff_x = ax2 + ax1 - x2 - x1
        if diff_x < 0:
            diff_x = -diff_x
        diff_y = ay2 + ay1 - y2 - y1
        if diff_y < 0:
            diff_y = -diff_y
        return diff_x <= x2 - x1 + ax2 - ax1 and diff_y <= y2 - y1 + ay2 - ay1

    def move(self, vector: "Point") -> "Area":
        """
        Moves the area by the given vector
        """
        x1, y1, x2, y2 = self
        vx, vy = vector
        return Area((x1 + vx, y1 + vy, x2 + vx, y2 + vy))

    def move_x(self, value) -> "Area":
        """
        Move area along X axis
        """
        x1, y1, x2, y2 = self
        return Area((x1 + value, y1, x2 + value, y2))

    def move_y(self, value) -> "Area":
        """
        Move area along Y axis
        """
        x1, y1, x2, y2 = self
        return Area((x1, y1 + value, x2, y2 + value))

    def move_onto_upperleft(self, area) -> "Area":
        """
        Move area onto the upperleft of another area
        Equivalent to:
            self.move(area.upperleft)
        """
        x1, y1, x2, y2 = self
        ax1, ay1, _, _ = area
        return Area((x1 + ax1, y1 + ay1, x2 + ax1, y2 + ay1))

    def inset(self, value: int) -> "Area":
        """
        Shrinks the area by padding amount on all sides
        Note that you may get an invalid area after inset
        """
        x1, y1, x2, y2 = self
        return Area((x1 + value, y1 + value, x2 - value, y2 - value))

    def outset(self, value: int) -> "Area":
        """
        Expands the area by padding amount on all sides
        """
        x1, y1, x2, y2 = self
        return Area((x1 - value, y1 - value, x2 + value, y2 + value))

    def inset_xy(self, point: "Point | tuple[int, int]") -> "Area":
        """
        Shrinks the area by padding X Y
        Note that you may get an invalid area after inset
        """
        x1, y1, x2, y2 = self
        px, py = point
        return Area((x1 + px, y1 + py, x2 - px, y2 - py))

    def outset_xy(self, point: "Point | tuple[int, int]") -> "Area":
        """
        Expands the area by padding X Y
        """
        x1, y1, x2, y2 = self
        px, py = point
        return Area((x1 - px, y1 - py, x2 + px, y2 + py))

    def size(self) -> "Point":
        x1, y1, x2, y2 = self
        return Point((x2 - x1, y2 - y1))

    def center(self) -> "Point":
        x1, y1, x2, y2 = self
        return Point(((x1 + x2) // 2, (y1 + y2) // 2))

    def distance_to(self, target: "Point | Area") -> float:
        """
        Euclidean distance to target
        For Point target, calculates distance to the closest point on this area
        For Area target, calculates distance between closest points (0 if intersecting)
        """
        x1, y1, x2, y2 = self
        if isinstance(target, Point):
            tx, ty = target
            # Calculate closest point on area
            if tx < x1:
                closest_x = x1
            elif tx > x2:
                closest_x = x2
            else:
                closest_x = tx
            if ty < y1:
                closest_y = y1
            elif ty > y2:
                closest_y = y2
            else:
                closest_y = ty
            dx = tx - closest_x
            dy = ty - closest_y
            return (dx * dx + dy * dy) ** 0.5
        else:
            # target is Area - using similar algorithm to is_intersect_area
            ax1, ay1, ax2, ay2 = target

            # Calculate center distance difference
            diff_x = ax2 + ax1 - x2 - x1
            if diff_x < 0:
                diff_x = -diff_x
            diff_y = ay2 + ay1 - y2 - y1
            if diff_y < 0:
                diff_y = -diff_y

            # Calculate size sums
            sum_width = x2 - x1 + ax2 - ax1
            sum_height = y2 - y1 + ay2 - ay1

            # Check if intersecting
            if diff_x <= sum_width and diff_y <= sum_height:
                return 0.0

            # Calculate edge distances
            # X direction distance
            if ax2 < x1:
                dx = x1 - ax2
            elif ax1 > x2:
                dx = ax1 - x2
            else:
                dx = 0

            # Y direction distance
            if ay2 < y1:
                dy = y1 - ay2
            elif ay1 > y2:
                dy = ay1 - y2
            else:
                dy = 0

            return (dx * dx + dy * dy) ** 0.5

    def distance_x_to(self, target: "Point | Area") -> int:
        """
        X-axis distance to target
        For Point target, calculates X distance to the closest edge
        For Area target, calculates X distance between closest edges (0 if overlapping on X)
        """
        x1, y1, x2, y2 = self
        if isinstance(target, Point):
            tx, ty = target
            if tx < x1:
                return x1 - tx
            elif tx > x2:
                return tx - x2
            else:
                return 0
        else:
            # target is Area
            ax1, ay1, ax2, ay2 = target
            if ax2 < x1:
                return x1 - ax2
            elif ax1 > x2:
                return ax1 - x2
            else:
                return 0

    def distance_y_to(self, target: "Point | Area") -> int:
        """
        Y-axis distance to target
        For Point target, calculates Y distance to the closest edge
        For Area target, calculates Y distance between closest edges (0 if overlapping on Y)
        """
        x1, y1, x2, y2 = self
        if isinstance(target, Point):
            tx, ty = target
            if ty < y1:
                return y1 - ty
            elif ty > y2:
                return ty - y2
            else:
                return 0
        else:
            # target is Area
            ax1, ay1, ax2, ay2 = target
            if ay2 < y1:
                return y1 - ay2
            elif ay1 > y2:
                return ay1 - y2
            else:
                return 0

    def manhattan_to(self, target: "Point | Area") -> int:
        """
        Manhattan distance to target
        For Point target, calculates Manhattan distance to the closest point on this area
        For Area target, calculates Manhattan distance between closest points (0 if intersecting)
        """
        x1, y1, x2, y2 = self
        if isinstance(target, Point):
            tx, ty = target
            # Calculate closest point on area
            if tx < x1:
                closest_x = x1
            elif tx > x2:
                closest_x = x2
            else:
                closest_x = tx
            if ty < y1:
                closest_y = y1
            elif ty > y2:
                closest_y = y2
            else:
                closest_y = ty
            # Calculate distances
            dx = tx - closest_x
            if dx < 0:
                dx = -dx
            dy = ty - closest_y
            if dy < 0:
                dy = -dy
            return dx + dy
        else:
            # target is Area - using similar algorithm to is_intersect_area
            ax1, ay1, ax2, ay2 = target

            # Calculate center distance difference
            diff_x = ax2 + ax1 - x2 - x1
            if diff_x < 0:
                diff_x = -diff_x
            diff_y = ay2 + ay1 - y2 - y1
            if diff_y < 0:
                diff_y = -diff_y

            # Calculate size sums
            sum_width = x2 - x1 + ax2 - ax1
            sum_height = y2 - y1 + ay2 - ay1

            # Check if intersecting
            if diff_x <= sum_width and diff_y <= sum_height:
                return 0

            # Calculate edge distances
            # X direction distance
            if ax2 < x1:
                dx = x1 - ax2
            elif ax1 > x2:
                dx = ax1 - x2
            else:
                dx = 0

            # Y direction distance
            if ay2 < y1:
                dy = y1 - ay2
            elif ay1 > y2:
                dy = ay1 - y2
            else:
                dy = 0

            return dx + dy

    def align_left(self, x: int) -> "Area":
        """
        Align the left edge (x1) to the specified x coordinate, maintaining size
        """
        x1, y1, x2, y2 = self
        width = x2 - x1
        return Area((x, y1, x + width, y2))

    def align_right(self, x: int) -> "Area":
        """
        Align the right edge (x2) to the specified x coordinate, maintaining size
        """
        x1, y1, x2, y2 = self
        width = x2 - x1
        return Area((x - width, y1, x, y2))

    def align_top(self, y: int) -> "Area":
        """
        Align the top edge (y1) to the specified y coordinate, maintaining size
        """
        x1, y1, x2, y2 = self
        height = y2 - y1
        return Area((x1, y, x2, y + height))

    def align_bottom(self, y: int) -> "Area":
        """
        Align the bottom edge (y2) to the specified y coordinate, maintaining size
        """
        x1, y1, x2, y2 = self
        height = y2 - y1
        return Area((x1, y - height, x2, y))

    def align_center_x(self, x: int) -> "Area":
        """
        Align the horizontal center to the specified x coordinate, maintaining size
        """
        x1, y1, x2, y2 = self
        half_width = (x2 - x1) // 2
        return Area((x - half_width, y1, x - half_width + (x2 - x1), y2))

    def align_center_y(self, y: int) -> "Area":
        """
        Align the vertical center to the specified y coordinate, maintaining size
        """
        x1, y1, x2, y2 = self
        half_height = (y2 - y1) // 2
        return Area((x1, y - half_height, x2, y - half_height + (y2 - y1)))

    def align_center(self, x: int, y: int) -> "Area":
        """
        Align the center to the specified (x, y) coordinate, maintaining size
        Equivalent to with_center(Point((x, y)))
        """
        x1, y1, x2, y2 = self
        half_width = (x2 - x1) // 2
        half_height = (y2 - y1) // 2
        return Area((x - half_width, y - half_height, x + half_width, y + half_height))

    def to_positive(self, res: "tuple[int, int]") -> "Area":
        """
        Convert negative indices to positive indices based on resolution
        Similar to Python's negative indexing for arrays

        For a resolution (width, height):
        - Negative x values are converted: x -> width + x
        - Negative y values are converted: y -> height + y
        - Positive values remain unchanged

        Example:
            res = (100, 100)
            Area((-10, -20, 50, 60)).to_positive(res) -> Area((90, 80, 50, 60))
            Area((-1, -1, -1, -1)).to_positive(res) -> Area((99, 99, 99, 99))
        """
        x1, y1, x2, y2 = self
        if x1 >= 0 and y1 >= 0 and x2 >= 0 and y2 >= 0:
            return self
        rx, ry = res
        if x1 < 0:
            x1 = rx + x1
        if x2 < 0:
            x2 = rx + x2
        if y1 < 0:
            y1 = ry + y1
        if y2 < 0:
            y2 = ry + y2
        return Area((x1, y1, x2, y2))

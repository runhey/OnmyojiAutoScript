import random


def random_normal_distribution_int(a, b, n=3):
    """
    Generate a normal distribution int within the interval.
    Use the average value of several random numbers to simulate normal distribution.

    Args:
        a (int): The minimum of the interval.
        b (int): The maximum of the interval.
        n (int): The amount of numbers in simulation. Default to 3.

    Returns:
        int
    """
    a = round(a)
    b = round(b)
    if a < b:
        total = 0
        for _ in range(n):
            total += random.randint(a, b)
        return round(total / n)
    else:
        return b


def random_rectangle_point(area, n=3):
    """Choose a random point in an area.

    Args:
        area: (upper_left_x, upper_left_y, bottom_right_x, bottom_right_y).
        n (int): The amount of numbers in simulation. Default to 3.

    Returns:
        tuple[int, int]: (x, y)
    """
    x = random_normal_distribution_int(area[0], area[2], n=n)
    y = random_normal_distribution_int(area[1], area[3], n=n)
    return x, y


def random_id(length=6):
    """
    Generate a base62 random id

    Args:
        length:

    Returns:
        str:
    """
    char = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return ''.join(random.choices(char, k=length))


def random_friendly_id(length=10):
    """
    Generate a random ID that is human friendly and OCR friendly
    Output won't contain 0/o/O, 1/i/I/l, 5/S/s, 2/Z/z, 0/D, 8/B, u/U, v/V, w/W, x/X

    Args:
        length:

    Returns:
        str:
    """
    char = 'abcdefghjkmnpqrtyACEFGHJKLMNPQRTY34679'
    return ''.join(random.choices(char, k=length))

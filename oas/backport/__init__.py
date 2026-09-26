def str_center(text, width, char=' '):
    """
    Center *text* in a string of *width* for better visual display.

    Unlike ``str.center()``, the extra padding character is placed on the right when the total padding is odd.

    Args:
        text (str): String to center.
        width (int): Target width.
        char (str): Padding character. Defaults to space.

    Returns:
        str: Centered string.
    """
    length = len(text)
    if width <= length:
        return text
    pad = width - length
    left = pad // 2       # floor
    right = pad - left
    return ''.join([char * left, text, char * right])
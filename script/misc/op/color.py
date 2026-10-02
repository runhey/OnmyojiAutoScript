class RGB(tuple):
    def as_int(self, round_value=True) -> "RGB":
        """
        Ensure value are integer
        """
        r, g, b = self
        if round_value:
            return RGB((int(round(r)), int(round(g)), int(round(b))))
        else:
            return RGB((int(r), int(g), int(b)))

    def as_uint8(self, round_value=True) -> "RGB":
        r, g, b = self
        if r < 0:
            r = 0
        if g < 0:
            g = 0
        if b < 0:
            b = 0
        if r > 255:
            r = 255
        if g > 255:
            g = 255
        if b > 255:
            b = 255
        if round_value:
            return RGB((int(round(r)), int(round(g)), int(round(b))))
        else:
            return RGB((int(r), int(g), int(b)))

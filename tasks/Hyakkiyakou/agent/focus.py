import numpy as np

from rich.table import Table
from rich.text import Text
from cached_property import cached_property

from module.logger import logger

from oashya.labels import id2label, id2name
from oashya.labels import CLASSINDEX as CI


class Focus:
    def __init__(self, inputs: list[tuple]):
        self._id: int = inputs[0]
        self._class: int = inputs[1]
        self._conf: int = inputs[2]
        self._cx: int = inputs[3]
        self._cy: int = inputs[4]
        self._w: int = inputs[5]
        self._h: int = inputs[6]
        self._v: float = inputs[7]
        # -----------------------
        self._omega: float = 0.
        self._omega_buff: float = 0.

    def __eq__(self, o):
        return self._id == o._id or o._class == self._class

    def __str__(self):
        return f"""
id: {self._id}
class: {self._class}
label: {id2label(self._class)}
name: {id2name(self._class)}
conf: {self._conf}
xywh: ({self._cx}, {self._cy}, {self._w}, {self._h})
velocity: {self._v}"""

    def omega(self, z):
        __omega = z[self._cy, self._cx]
        self._omega = __omega
        return __omega

    def set_omega(self, value):
        self._omega = value

    def show(self):
        table = Table(show_lines=True)
        table.add_column('Property', header_style="bright_cyan", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")
        table.add_column('Property', header_style="bright_cyan", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")
        table.add_row('id', str(self._id), 'conf', str(self._conf))
        table.add_row('class', str(self._class), 'xywh', f'({self._cx}, {self._cy}, {self._w}, {self._h})')
        table.add_row('label', id2label(self._class), 'velocity', str(self._v))
        table.add_row('name', f'{id2name(self._class)}', 'omega', str(self._omega))
        logger.print(table, justify='center')

    def update(self, focus):
        self._id = focus._id
        self._class = focus._class
        self._conf = focus._conf
        self._cx = focus._cx
        self._cy = focus._cy
        self._w = focus._w
        self._h = focus._h
        self._v = focus._v

    def decision(self, tracks, strategy, state) -> list:

        buff_omega, buff_cx, buff_cy, buff_v, buff_class = self.omega_buff(tracks, strategy['invite_friend'])
        if self._omega > buff_omega:
            buffed = False
            target_x = self._cx + self._v * 100 - (self._w // 2)
            target_y = self._cy - 40
        else:
            buffed = True
            target_x = buff_cx + buff_v * 100
            target_y = buff_cy - 40  # top left corner

        _r = self.r(vector=state, omega=self._omega, omega_buff=self._omega_buff)
        throw = True if _r > 0 else False
        # x, y, throw, number
        return [target_x, target_y, throw, 10]

    def omega_buff(self, tracks, invite_friend: bool) -> float:
        max_omega = 0.
        max_cx = 0
        max_cy = 0
        max_v = 0
        max_class = 0

        for _id, _class, _conf, _cx, _cy, _w, _h, _v in tracks:
            _current_omega = 0.
            match _class:
                case CI.BUFF_004: _current_omega = 2.2
                case CI.BUFF_006: _current_omega = 2.0
                case CI.BUFF_007: _current_omega = 2.0 if invite_friend and _cx <= 1000 else 0
                case CI.BUFF_002: _current_omega = 2.0 if self._omega >= 1.5 else 0
                case CI.BUFF_003: _current_omega = 2.0 if self._omega >= 1.5 else 0
                case CI.BUFF_003: _current_omega = 2.0 if self._omega >= 1.5 and _cx <= 640 else 0
                case _: pass
            if _current_omega > max_omega:
                max_omega = _current_omega
                max_cx = _cx
                max_cy = _cy
                max_v = _v
                max_class = _class
        return max_omega, max_cx, max_cy, max_v, max_class
            
    @classmethod
    def r(cls, vector: list, omega: float, omega_buff: float) -> float:
        _omega = max(omega, omega_buff)
        tau = - 140 / (max(101, vector[0]) - 100)
        upsilon = (vector[1] / 250 - vector[2] / 35)
        upsilon = 100 * (upsilon**2 if upsilon > 0 else - upsilon**2)
        result = _omega + tau + upsilon - 0.6
        # print(f"total: {result:.4f} | {_omega:.4f} | {tau:.4f} | {upsilon:.4f}")
        return result


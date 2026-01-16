import numpy as np

from rich.table import Table
from rich.text import Text
from cached_property import cached_property

from module.logger import logger

from oashya.labels import id2label, id2name
from oashya.labels import CLASSINDEX as CI

# get buff status
from tasks.Hyakkiyakou.slave.hya_slave import HyaBuff


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

    def decision(self, tracks, strategy, state, freeze: bool = False) -> list:

        buff_states = state[4:] if len(state) > 4 else []  # get buff status：state[4:] = buff_0 ~ buff_3，对应 HyaBuff
        has_prob_up = any(b == HyaBuff.BUFF_STATE6 for b in buff_states) # 是否存在“概率UP”buff（HyaBuff.BUFF_STATE6）
        buff_omega, buff_cx, buff_cy, buff_v, buff_class = self.omega_buff(tracks, strategy['invite_friend'], has_prob_up)
        if self._omega > buff_omega:
            buffed = False
            target_x = self._cx + self._v * 100 - (self._w // 2)
            target_y = self._cy - 40
            target_class = self._class # new : for class
        else:
            buffed = True
            target_x = buff_cx + buff_v * 100
            target_y = buff_cy - 40  # top left corner
            target_class = buff_class # new : for class

        # ========= 新增：利用和 gamma() 一样的区间判断当前“打的对象”是不是 SSR/SP =========
        is_rare_ssr_sp = False
        if CI.MIN_SSR <= target_class <= CI.MAX_SSR and self._omega > buff_omega:
            is_rare_ssr_sp = True
        elif CI.MIN_SP <= target_class <= CI.MAX_SP and self._omega > buff_omega:
            is_rare_ssr_sp = True
        _r = self.r(vector=state, omega=self._omega, omega_buff=self._omega_buff, is_rare_ssr_sp=is_rare_ssr_sp, freeze=freeze, is_buff=buffed)
        throw = True if _r > 0 else False
        # x, y, throw, number
        return [target_x, target_y, throw, 10]

    def omega_buff(self, tracks, invite_friend: bool, has_prob_up: bool) -> float:
        max_omega = 0.
        max_cx = 0
        max_cy = 0
        max_v = 0
        max_class = 0

        focus_is_ssr_sp = (CI.MIN_SSR <= self._class <= CI.MAX_SSR or CI.MIN_SP <= self._class <= CI.MAX_SP)

        for _id, _class, _conf, _cx, _cy, _w, _h, _v in tracks:
            _current_omega = 0.
            match _class:
                case CI.BUFF_004: _current_omega = 2.2
                case CI.BUFF_006: _current_omega = 2.0
                case CI.BUFF_007: _current_omega = 2.0 if invite_friend and _cx <= 1000 else 0
                case CI.BUFF_002: _current_omega = 2.0 if self._omega >= 1.5 else 0
                case CI.BUFF_003: _current_omega = 2.0 if self._omega >= 1.5 and _cx <= 640 else 0
                # case CI.BUFF_005: _current_omega = max(self._omega + 0.1, 3.0) if focus_is_ssr_sp and has_prob_up else 0 # 冻住，不许跑
                case _: pass
            if _current_omega > max_omega:
                max_omega = _current_omega
                max_cx = _cx
                max_cy = _cy
                max_v = _v
                max_class = _class
        return max_omega, max_cx, max_cy, max_v, max_class
            
    @classmethod
    def r(cls, vector: list, omega: float, omega_buff: float, is_rare_ssr_sp: bool, freeze: bool = False, is_buff: bool = False) -> float:
        _omega = max(omega, omega_buff)
        tau = - 140 / (max(101, vector[0]) - 100) # 时间冷却项：避免过密投豆
        upsilon = (vector[1] / 250 - vector[2] / 35) # 豆子数量 vs 进度：豆多进度低 -> 倾向多砸；豆少进度高 -> 惩罚多砸
        upsilon = 100 * (upsilon**2 if upsilon > 0 else - upsilon**2)
        result = _omega + tau + upsilon - 0.6
        # print(f"total: {result:.4f} | {_omega:.4f} | {tau:.4f} | {upsilon:.4f}")
       
        buff_states = vector[4:] if len(vector) > 4 else []  # get buff status：vector[4:] = buff_0 ~ buff_3，对应 HyaBuff
        has_prob_up = any(b == HyaBuff.BUFF_STATE6 for b in buff_states) # 是否存在“概率UP”buff（HyaBuff.BUFF_STATE6）

        # punishment：
        #    no throwing when ssr/sp with no enhanced probability
        if is_rare_ssr_sp and not has_prob_up:
            result = -999.0 # stop throwing nonsense
        
        # punishment:
        #   only throw ssr/sp with enhanced probability or buff when freezed
        if freeze:
            # if not (is_rare_ssr_sp and has_prob_up):
            #     result = -999.0 # stop throwing nonsense
            # if is_buff:
            #     result = 5.0
            result = -999.0
            
        return result


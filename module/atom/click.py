# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import random
import numpy as np

from module.base.decorator import cached_property
from module.base.utils.utils import random_normal_distribution_int
from module.logger import logger

class RuleClick:

    def __init__(self, roi_front: tuple, roi_back: tuple, name: str = None) -> None:
        """
        初始化
        :param roi_front:
        :param roi_back:
        """
        self.roi_front = roi_front
        self.roi_back = roi_back
        if name:
            self.name = name
        else:
            self.name = 'click'

    def coord(self) -> tuple:
        """
        获取坐标, 从roi_front随机获取坐标
        :return:
        """
        x, y, w, h = self.roi_front
        x = random_normal_distribution_int(x, x + w)
        y = random_normal_distribution_int(y, y + h)
        return x, y

    def coord_more(self) -> tuple:
        """
        从roi_back随机获取坐标
        :return:
        """
        x, y, w, h = self.roi_back
        x = random_normal_distribution_int(x, x + w)
        y = random_normal_distribution_int(y, y + h)
        return x, y

    @property
    def center(self) -> tuple:
        """
        返回roi_front的中心坐标
        :return:
        """
        x, y, w, h = self.roi_front
        return x + w // 2, y + h // 2

    def move(self, x: int, y: int) -> None:
        """
        移动roi_front, 需要限幅x是0-1280, y是0-720
        :param x:
        :param y:
        :return:
        """
        x, y, w, h = self.roi_front
        x += x
        y += y
        if x <= 0 :
            x = 0
        elif x >= 1280:
            x = 1280

        if y <= 0 :
            y = 0
        elif y >= 720:
            y = 720

        self.roi_front = x, y, w, h


class RuleClickExclude(RuleClick):
    """Randomly click within the screen while excluding other click regions."""

    SCREEN_WIDTH = 1280
    SCREEN_HEIGHT = 720

    def __init__(self, clicks, strategy: str | None = None, distribution: str | None = None,
                 max_attempts: int = 100, name: str = 'exclude_random_click') -> None:
        """
        初始化排除区域随机点击规则。

        :param clicks: 需要排除的 RuleClick，或 RuleClick 序列；使用其 roi_back 作为排除区域
        :param strategy: 取点策略，None 时在初始化时随机选择 rejection 或 complement
        :param distribution: 坐标分布，None 时在初始化时随机选择 uniform 或 normal
        :param max_attempts: 拒绝采样的最大尝试次数，耗尽后自动使用补集矩形采样
        :param name: 点击规则名称，用于 BaseTask.click 的间隔计时器
        :raises TypeError: clicks 不是 RuleClick 或 RuleClick 序列
        :raises ValueError: strategy、distribution 或 max_attempts 参数无效，或排除区域覆盖整个屏幕
        """
        super().__init__((0, 0, self.SCREEN_WIDTH, self.SCREEN_HEIGHT),
                         (0, 0, self.SCREEN_WIDTH, self.SCREEN_HEIGHT), name=name)
        if strategy is None:
            strategy = random.choice(('rejection', 'complement'))
        if distribution is None:
            distribution = random.choice(('uniform', 'normal'))
        if strategy not in ('rejection', 'complement'):
            raise ValueError("strategy must be 'rejection' or 'complement'")
        if distribution not in ('uniform', 'normal'):
            raise ValueError("distribution must be 'uniform' or 'normal'")
        if max_attempts < 1:
            raise ValueError('max_attempts must be positive')

        if isinstance(clicks, RuleClick):
            clicks = (clicks,)
        self.clicks = tuple(clicks)
        if not all(isinstance(click, RuleClick) for click in self.clicks):
            raise TypeError('clicks must contain RuleClick instances')
        self.strategy = strategy
        self.distribution = distribution
        self.max_attempts = max_attempts
        self._excluded = tuple(
            rect for click in self.clicks
            for rect in (self._clip_roi(click.roi_back),)
            if rect is not None
        )
        self._allowed = self._build_complement()
        if not self._allowed:
            raise ValueError('Excluded regions cover the whole screen')

    def __str__(self):
        click_names = ', '.join(click.name for click in self.clicks) or 'none'
        return (
            f'{self.name}(strategy={self.strategy}, '
            f'distribution={self.distribution}, clicks=[{click_names}])'
        )

    __repr__ = __str__

    @classmethod
    def _clip_roi(cls, roi):
        x, y, w, h = roi
        left, top = max(0, x), max(0, y)
        right, bottom = min(cls.SCREEN_WIDTH, x + w), min(cls.SCREEN_HEIGHT, y + h)
        if left >= right or top >= bottom:
            return None
        return left, top, right - left, bottom - top

    def _is_excluded(self, x, y):
        return any(left <= x < left + width and top <= y < top + height
                   for left, top, width, height in self._excluded)

    def _build_complement(self):
        x_edges = {0, self.SCREEN_WIDTH}
        y_edges = {0, self.SCREEN_HEIGHT}
        for x, y, width, height in self._excluded:
            x_edges.update((x, x + width))
            y_edges.update((y, y + height))

        x_edges, y_edges = sorted(x_edges), sorted(y_edges)
        allowed = []
        for x1, x2 in zip(x_edges, x_edges[1:]):
            for y1, y2 in zip(y_edges, y_edges[1:]):
                if not self._is_excluded(x1, y1):
                    allowed.append((x1, y1, x2 - x1, y2 - y1))
        return allowed

    def _sample_axis(self, start, size, distribution):
        if size == 1:
            return start
        if distribution == 'uniform':
            return random.randrange(start, start + size)
        return max(start, min(start + size - 1,
                              random_normal_distribution_int(start, start + size)))

    def _sample_point(self, rect, distribution):
        x, y, width, height = rect
        return self._sample_axis(x, width, distribution), self._sample_axis(y, height, distribution)

    def _coord_rejection(self, distribution):
        for _ in range(self.max_attempts):
            point = self._sample_point((0, 0, self.SCREEN_WIDTH, self.SCREEN_HEIGHT), distribution)
            if not self._is_excluded(*point):
                return point
        return self._coord_complement(distribution)

    def _coord_complement(self, distribution):
        total = sum(width * height for _, _, width, height in self._allowed)
        offset = random.randrange(total)
        for rect in self._allowed:
            area = rect[2] * rect[3]
            if offset < area:
                return self._sample_point(rect, distribution)
            offset -= area
        raise RuntimeError('Unable to select a click region')

    def coord(self) -> tuple:
        if self.strategy == 'rejection':
            return self._coord_rejection(self.distribution)
        return self._coord_complement(self.distribution)

    def coord_in_excluded(self, areas: list[str] | None = None) -> tuple:
        """Return a random coordinate inside one of the named excluded areas."""
        if not areas:
            areas = ['C_END_1_1', 'C_END_1_2', 'C_END_1_3', 'C_END_1_4', 'C_END_1_5', 'C_END_1_6',
                     'C_END_2_1', 'C_END_2_2', 'C_END_2_3', 'C_END_2_4', 'C_END_2_5', 'C_END_2_6']
        area_names = {area.casefold() for area in areas}
        matched = []
        for click in self.clicks:
            names = {str(click), click.name, click.name.upper(), f'C_{click.name.upper()}'}
            if area_names.intersection(name.casefold() for name in names):
                matched.append(click)
        if not matched:
            raise ValueError(f'No excluded click matches areas: {areas!r}')
        return random.choice(matched).coord()

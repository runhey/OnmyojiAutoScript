# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import numpy as np
import random

from math import dist

from module.base.decorator import cached_property
from module.atom.cBezier import BezierTrajectory
from module.logger import logger


class RuleSwipe:

    def __init__(self, roi_front: tuple, roi_back: tuple, mode: str, name: str =None) -> None:
        """
        初始化
        :param roi_front:
        :param roi_back:
        :param mode:
        """
        self.roi_front = roi_front
        self.roi_back = roi_back
        self.mode = mode
        if name:
            self.name = name
        else:
            self.name = 'swipe'

        self.interval: int = 8  # 每次移动的间隔时间

    @cached_property
    def is_default_mode(self) -> bool:
        """
        是否是默认模式
        :return:
        """
        return self.mode == 'default'

    @cached_property
    def is_vector_mode(self) -> bool:
        """
        是否是向量模式
        :return:
        """
        return self.mode == 'vector'

    def coord(self) -> tuple:
        """
        获取坐标, 从roi_front随机获取坐标 和从roi_back随机获取的坐标
        :return: 两个坐标的tuple
        """
        x, y, w, h = self.roi_front
        x = np.random.randint(x, x + w)
        y = np.random.randint(y, y + h)
        x2, y2, w2, h2 = self.roi_back
        x2 = np.random.randint(x2, x2 + w2)
        y2 = np.random.randint(y2, y2 + h2)
        return x, y, x2, y2

    def trace(self) -> list:
        """
        获取滑动的路径,list的每一项都是tuple
        :return:
        """
        if self.is_default_mode:
            start_pos, end_pos = self.coord()
            # 表示每秒移动1.5个像素点， 总的时间除以每个点10ms就得到总的点的个数
            number_list: int = int(dist(start_pos, end_pos) / (1.5 * self.interval))
            le = random.randint(2, 4)  #
            deviation = random.randint(20, 40)  # 幅度
            b_type = 3
            obbs_type = random.random()  # 0.8的概率是先快中间慢后面快， 0.1概率是先快后慢， 0.1概率先慢后快
            if 0 < obbs_type <= 0.8:
                b_type = 3
            elif obbs_type < 0.9:
                b_type = 2
            else:
                b_type = 1

            return BezierTrajectory.trackArray(start=start_pos, end=end_pos, numberList=number_list, le=le,
                     deviation=30, bias=0.5, type=b_type, cbb=0, yhh=20)

        elif self.is_vector_mode:
            # 获取两个点的直线的规矩
            start_pos, end_pos = self.coord()
            # 表示每秒移动1.5个像素点， 总的时间除以每个点10ms就得到总的点的个数
            number_list: int = int(dist(start_pos, end_pos) / (1.5 * self.interval))

            def generate_linear_trajectory(start_pos: tuple, end_pos: tuple, num_points: int) -> list:
                """
                生成线性轨迹
                :param start_pos:
                :param end_pos:
                :param num_points:
                :return:
                """
                trajectory = []
                delta_x = (end_pos[0] - start_pos[0]) / (num_points - 1)
                delta_y = (end_pos[1] - start_pos[1]) / (num_points - 1)
                for i in range(num_points):
                    x = start_pos[0] + delta_x * i
                    y = start_pos[1] + delta_y * i
                    trajectory.append((x, y))
                return trajectory

            return generate_linear_trajectory(start_pos, end_pos, number_list)

        else:
            raise ValueError(f'Invalid mode: {self.mode}')





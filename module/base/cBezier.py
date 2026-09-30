'''
author: cbb
这个库基于贝塞尔曲线实现模拟人手动滑动的轨迹
可以用于selenium轨迹的模拟，或者生成轨迹数组用于js加密通过网站服务器后端分控检测
QQ群 134064772
里面的人说话好听，个个都是人才
copy from https://github.com/2833844911/gurs
'''

import numpy as np
import math
import random

class BezierTrajectory:

    @classmethod
    def _bztsg(cls, dataTrajectory):
        lengthOfdata = len(dataTrajectory)

        def staer(x):
            t = ((x - dataTrajectory[0][0]) / (dataTrajectory[-1][0] - dataTrajectory[0][0]))
            y = np.array([0, 0], dtype=np.float64)
            for s in range(len(dataTrajectory)):
                y += dataTrajectory[s] * ((math.factorial(lengthOfdata - 1) / (
                            math.factorial(s) * math.factorial(lengthOfdata - 1 - s))) * math.pow(t, s) * math.pow(
                    (1 - t), lengthOfdata - 1 - s))
            return y[1]

        return staer

    @classmethod
    def _type(cls, type, x, numberList):
        numberListre = []
        pin = (x[1] - x[0]) / numberList
        if type == 0:
            for i in range(numberList):
                numberListre.append(i * pin)
            if pin >= 0:
                numberListre = numberListre[::-1]
        elif type == 1:
            for i in range(numberList):
                numberListre.append(1 * ((i * pin) ** 2))
            numberListre = numberListre[::-1]
        elif type == 2:
            for i in range(numberList):
                numberListre.append(1 * ((i * pin - x[1]) ** 2))

        elif type == 3:
            dataTrajectory = [np.array([0,0]), np.array([(x[1]-x[0])*0.8, (x[1]-x[0])*0.6]), np.array([x[1]-x[0], 0])]
            fun = cls._bztsg(dataTrajectory)
            numberListre = [0]
            for i in range(1,numberList):
                numberListre.append(fun(i * pin) + numberListre[-1])
            if pin >= 0:
                numberListre = numberListre[::-1]
        numberListre = np.abs(np.array(numberListre) - max(numberListre))
        biaoNumberList = ((numberListre - numberListre[numberListre.argmin()]) / (
                    numberListre[numberListre.argmax()] - numberListre[numberListre.argmin()])) * (x[1] - x[0]) + x[0]
        biaoNumberList[0] = x[0]
        biaoNumberList[-1] = x[1]
        return biaoNumberList

    @classmethod
    def getFun(cls, s):
        '''

        :param s: 传入P点
        :return: 返回公式
        '''
        dataTrajectory = []
        for i in s:
            dataTrajectory.append(np.array(i))
        return cls._bztsg(dataTrajectory)

    @classmethod
    def simulation(cls, start, end, le=1, deviation=0, bias=0.5):
        '''

        :param start:开始点的坐标 如 start = [0, 0]
        :param end:结束点的坐标 如 end = [100, 100]
        :param le:几阶贝塞尔曲线，越大越复杂 如 le = 4
        :param deviation:轨迹上下波动的范围 如 deviation = 10
        :param bias:波动范围的分布位置 如 bias = 0.5
        :return:返回一个字典equation对应该曲线的方程，P对应贝塞尔曲线的影响点
        '''
        start = np.array(start)
        end = np.array(end)
        cbb = []
        if le != 1:
            e = (1 - bias) / (le - 1)
            cbb = [[bias + e * i, bias + e * (i + 1)] for i in range(le - 1)]

        dataTrajectoryList = [start]

        t = random.choice([-1, 1])
        w = 0
        for i in cbb:
            px1 = start[0] + (end[0] - start[0]) * (random.random() * (i[1] - i[0]) + (i[0]))
            p = np.array([px1, cls._bztsg([start, end])(px1) + t * deviation])
            dataTrajectoryList.append(p)
            w += 1
            if w >= 2:
                w = 0
                t = -1 * t

        dataTrajectoryList.append(end)
        return {"equation": cls._bztsg(dataTrajectoryList), "P": np.array(dataTrajectoryList)}

    @classmethod
    def trackArray(cls, start, end, numberList, le=1, deviation=0, bias=0.5, type=0, cbb=0, yhh=10):
        '''

        :param start:开始点的坐标 如 start = [0, 0]
        :param end:结束点的坐标 如 end = [100, 100]
        :param numberList:返回的数组的轨迹点的数量 numberList = 150
        :param le:几阶贝塞尔曲线，越大越复杂 如 le = 4
        :param deviation:轨迹上下波动的范围 如 deviation = 10
        :param bias:波动范围的分布位置 如 bias = 0.5
        :param type:0表示均速滑动，1表示先慢后快，2表示先快后慢，3表示先慢中间快后慢 如 type = 1
        :param cbb:在终点来回摆动的次数
        :param yhh:在终点来回摆动的范围
        :return:返回一个字典trackArray对应轨迹数组，P对应贝塞尔曲线的影响点
        '''
        s = []
        fun = cls.simulation(start, end, le, deviation, bias)
        w = fun['P']
        fun = fun["equation"]
        if cbb != 0:
            numberListOfcbb = round(numberList*0.2/(cbb+1))
            numberList -= (numberListOfcbb*(cbb+1))

            xTrackArray = cls._type(type, [start[0], end[0]], numberList)
            for i in xTrackArray:
                s.append([i, fun(i)])
            dq = yhh/cbb
            kg = 0
            ends = np.copy(end)
            for i in range(cbb):
                if kg == 0:
                    d = np.array([end[0] + (yhh-dq*i), ((end[1]-start[1])/(end[0]-start[0]))*(end[0]+(yhh-dq*i)) +(end[1]-((end[1]-start[1])/(end[0]-start[0]))*end[0])   ])
                    kg = 1
                else:
                    d = np.array([end[0] - (yhh - dq * i), ((end[1]-start[1])/(end[0]-start[0]))*(end[0]-(yhh-dq*i)) +(end[1]-((end[1]-start[1])/(end[0]-start[0]))*end[0])  ])
                    kg = 0
                print(d)
                y = cls.trackArray(ends, d, numberListOfcbb, le=2, deviation=0, bias=0.5, type=0, cbb=0, yhh=10)
                s += list(y['trackArray'])
                ends = d
            y = cls.trackArray(ends, end, numberListOfcbb, le=2, deviation=0, bias=0.5, type=0, cbb=0, yhh=10)
            s += list(y['trackArray'])

        else:
            xTrackArray = cls._type(type, [start[0], end[0]], numberList)
            for i in xTrackArray:
                s.append([i, fun(i)])
        # return {"trackArray": np.array(s), "P": w}
        return [[int(s[0]), int(s[1])] for s in s]


def human_track(start, end, interval=10):
    """
    生成 start → end 的拟人贝塞尔轨迹点，相邻两点间隔约 interval 像素。
    轨迹阶数、波动幅度、速度分布随机，供模拟器滑动与桌面客户端滑动共用。

    两种退化输入单独处理：起点终点 x 相同时贝塞尔以 x 做参数化会除零，
    纯垂直移动退化为直线插值；距离不足以生成一个点时直接返回终点，
    避免调用方拿到空轨迹再去取 [0]。
    """
    number_list = int(math.dist(start, end) / (1 * interval))
    if number_list < 1:
        return [tuple(end)]
    if start[0] == end[0]:
        dy = end[1] - start[1]
        return [[int(start[0]), int(start[1] + dy * i / number_list)]
                for i in range(1, number_list + 1)]
    le = random.randint(2, 4)
    deviation = random.randint(20, 40)
    obbs_type = random.random()
    # 0.8 概率先快中间慢后面快，0.1 先快后慢，0.1 先慢后快
    if 0 < obbs_type <= 0.8:
        b_type = 3
    elif obbs_type < 0.9:
        b_type = 2
    else:
        b_type = 1
    return BezierTrajectory.trackArray(start=list(start), end=list(end), numberList=number_list,
                                       le=le, deviation=deviation, bias=0.5, type=b_type,
                                       cbb=0, yhh=20)

# print(BezierTrajectory.trackArray(start=[0, 0], end=[100, 100], numberList=50, le=2,
#                     deviation=0, bias=0.5, type=0, cbb=0, yhh=10))
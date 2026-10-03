import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Self, Tuple, Union


def timer(function):
    """
    Decorator to time a function, for debug only
    """

    @wraps(function)
    def function_timer(*args, **kwargs):
        start = time.perf_counter()
        result = function(*args, **kwargs)
        cost = time.perf_counter() - start
        print(f'{function.__name__}: {cost:.10f} s')
        return result

    return function_timer


def getnow(tz=True, ms=False):
    """
    Get datatime now, with or without timezone

    Args:
        tz (tzinfo | bool):
        ms (bool): True to have microsecond
    """
    now = datetime.now()
    if tz is True:
        now = now.astimezone()
    elif tz is False:
        pass
    else:
        now = now.astimezone(tz)
    if not ms:
        now = now.replace(microsecond=0)
    return now


def future_time(string):
    """
    Args:
        string (str): Such as 14:59.

    Returns:
        datetime.datetime: Time with given hour, minute in the future.
    """
    hour, minute = [int(x) for x in string.split(':')]
    future = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    future = future + timedelta(days=1) if future < datetime.now() else future
    return future


def past_time(string):
    """
    Args:
        string (str): Such as 14:59.

    Returns:
        datetime.datetime: Time with given hour, minute in the past.
    """
    hour, minute = [int(x) for x in string.split(':')]
    past = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    past = past - timedelta(days=1) if past > datetime.now() else past
    return past


def future_time_range(string):
    """
    Args:
        string (str): Such as 23:30-06:30.

    Returns:
        tuple(datetime.datetime): (time start, time end).
    """
    start, end = [future_time(s) for s in string.split('-')]
    if start > end:
        start = start - timedelta(days=1)
    return start, end


def time_range_active(time_range):
    """
    Args:
        time_range(tuple(datetime.datetime)): (time start, time end).

    Returns:
        bool:
    """
    return time_range[0] < datetime.now() < time_range[1]


# timeout `limit` in seconds or (limit, count), limit can be int or float
T_TIMER_LIMIT = Union[int, float, Tuple[int, int], Tuple[float, int], 'Timer']


class Timer:
    def __init__(self, limit, count=0):
        """
        Dual timer for time count and access count.
        Access count can provide robustness on slow devices where screenshot time cost > timer.limit

        Args:
            limit (int | float): Timer limit
            count (int): Timer access count. Default to 0.
        """
        if limit < 0:
            limit = 0
        if count < 0:
            count = 0
        self.limit = limit
        self.count = count
        self._start = 0.
        self._access = 0

    @classmethod
    def from_seconds(cls, limit: T_TIMER_LIMIT, speed=0.5) -> Self:
        """
        Create timer from given seconds

        Args:
            limit:
                - timeout `limit` in seconds, limit can be int or float
                - (limit, count), limit can be int or float
                - Timer object
            speed (int | float): Approximate screenshot time cost
                if time cost > 0.5s, device is considered slow
        """
        if isinstance(limit, Timer):
            return limit
        if isinstance(limit, tuple):
            limit, count = limit
            return cls(limit, count=count)
        count = int(limit / speed)
        return cls(limit, count=count)

    def start(self) -> Self:
        """
        Start current timer.
        If timer not started, reached() always return True. So we can have fast first try on:

        interval = Timer(2)
        while 1:
            if interval.reached():
                pass
        """
        if self._start <= 0:
            self._start = time.monotonic()
            self._access = 0

        return self

    def started(self):
        """
        Returns:
            bool:
        """
        return self._start > 0

    def current_time(self):
        """
        Returns:
            float:
        """
        if self._start > 0:
            diff = time.monotonic() - self._start
            if diff < 0:
                diff = 0.
            return diff
        else:
            return 0.

    def current(self):
        """
        Returns:
            float
        """
        return self.current_time()

    def current_count(self):
        """
        Returns:
            int:
        """
        return self._access

    def set(self, current=None, count=None, speed=0.5) -> Self:
        """
        Set internal state directly

        Args:
            current (int, float):
            count (int):
            speed (int, float):
        """
        if current is not None:
            if count is not None:
                # set both
                self._start = time.monotonic() - current
                self._access = count
            else:
                # set current only, calculate count
                count = int(current / speed)
                self._start = time.monotonic() - current
                self._access = count
        else:
            if count is not None:
                # set count only
                self._access = count
            else:
                # nothing to set
                pass
        return self

    def add_count(self) -> Self:
        self._access += 1
        return self

    def reached(self):
        """
        Returns:
            bool:
        """
        # each reached() call is consider as an access
        self._access += 1
        if self._start > 0:
            return self._access > self.count and time.monotonic() - self._start > self.limit
        else:
            # not started, return True for fast first try
            return True

    def reset(self) -> Self:
        """
        Reset the timer as if it just started
        """
        self._start = time.monotonic()
        self._access = 0
        return self

    def clear(self) -> Self:
        """
        Reset the timer as if it never started
        """
        self._start = 0.
        self._access = self.count
        return self

    def reached_and_reset(self):
        """
        Returns:
            bool:
        """
        if self.reached():
            self.reset()
            return True
        else:
            return False

    def wait(self) -> Self:
        """
        Wait until timer reached.
        """
        diff = self._start + self.limit - time.monotonic()
        if diff > 0:
            time.sleep(diff)
        return self

    def remain(self):
        """
        remain time
        :return:
        """
        return self._start + self.limit - time.monotonic()

    def show(self):
        from oas.logger import logger
        logger.info(str(self))

    def __str__(self):
        # Timer(limit=2.351/3, count=4/6)
        return f'Timer(limit={round(self.current_time(), 3)}/{self.limit}, count={self._access}/{self.count})'

    __repr__ = __str__

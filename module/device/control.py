# from module.base.button import Button
from module.base.decorator import cached_property
from module.base.timer import Timer
from module.base.utils import *
# from module.device.method.hermit import Hermit
# from module.device.method.maatouch import MaaTouch
from module.device.method.minitouch import Minitouch
from module.device.method.adb import Adb
from module.device.method.scrcpy import Scrcpy
from module.device.method.windows import Window
from module.logger import logger


class Control(Minitouch, Adb, Scrcpy, Window):
    def handle_control_check(self, button):
        # Will be overridden in Device
        pass

    @cached_property
    def click_methods(self):
        return {
            'ADB': self.click_adb,
            'uiautomator2': self.click_uiautomator2,
            'minitouch': self.click_minitouch,
            'window_message': self.click_window_message
            # 'Hermit': self.click_hermit,
            # 'MaaTouch': self.click_maatouch,
        }

    @cached_property
    def long_click_methods(self):
        return {
            'ADB': self.long_click_adb,
            'uiautomator2': self.long_click_uiautomator2,
            'minitouch': self.long_click_minitouch,
            'window_message': self.long_click_window_message,
            'scrcpy': self.long_click_scrcpy
            # 'Hermit': self.click_hermit,
            # 'MaaTouch': self.click_maatouch,
        }

    # def click(self, button, control_check=True):
    #     """
    #     后面改一改  不用用button的逻辑
    #     :param button:
    #     :param control_check:
    #     :return:
    #     """
    #     if control_check:
    #         self.handle_control_check(button)
    #     x, y = random_rectangle_point(button.button)
    #     x, y = ensure_int(x, y)
    #     logger.info(
    #         'Click %s @ %s' % (point2str(x, y), button)
    #     )
    #     method = self.click_methods.get(
    #         self.config.script.emulator.control_method,
    #         self.click_adb
    #     )
    #     method(x, y)

    def click(self, x: int, y: int, control_check=True, control_name='Click') -> None:
        """

        :param control_name:
        :param x:
        :param y:
        :param control_check:
        :return:
        """
        if control_check:
            self.handle_control_check(control_name)
        x, y = ensure_int(x, y)
        logger.info(
            'Click %s @ %s' % (point2str(x, y), control_name)
        )
        method = self.click_methods.get(
            self.config.script.device.control_method,
            self.click_adb
        )
        method(x, y)


    def multi_click(self, button, n, interval=(0.1, 0.2)):
        """
        也是不能用button的逻辑
        :param button:
        :param n:
        :param interval:
        :return:
        """
        self.handle_control_check(button)
        click_timer = Timer(0.1)
        for _ in range(n):
            remain = ensure_time(interval) - click_timer.current()
            if remain > 0:
                self.sleep(remain)
            click_timer.reset()

            self.click(button, control_check=False)

    # def long_click(self, button, duration=(1, 1.2)):
    #     """
    #
    #     :param button:
    #     :param duration:
    #     :return:
    #     """
    #     self.handle_control_check(button)
    #     x, y = random_rectangle_point(button.button)
    #     x, y = ensure_int(x, y)
    #     duration = ensure_time(duration)
    #     logger.info(
    #         'Click %s @ %s, %s' % (point2str(x, y), button, duration)
    #     )
    #     method = self.config.script.emulator.control_method
    #     if method == 'minitouch':
    #         self.long_click_minitouch(x, y, duration)
    #     elif method == 'window_message':
    #         self.long_click_window_message(x, y, duration)
    #     elif method == 'uiautomator2':
    #         self.long_click_uiautomator2(x, y, duration)
    #     elif method == 'scrcpy':
    #         self.long_click_scrcpy(x, y, duration)
    #     # elif method == 'MaaTouch':
    #     #     self.long_click_maatouch(x, y, duration)
    #     else:
    #         self.swipe_adb((x, y), (x, y), duration)

    def long_click(self, x: int, y: int, duration=(0.5, 2), control_name='LongClick') -> None:
        """

        :param control_name:
        :param x:
        :param y:
        :param duration: 单位是s
        :return:
        """
        self.handle_control_check(control_name)
        x, y = ensure_int(x, y)
        if duration is None:
            duration = 0.8
        duration = ensure_time(duration)
        logger.info(
            'Click %s @ %s %s' % (point2str(x, y), control_name, duration)
        )
        method = self.long_click_methods.get(
            self.config.script.device.control_method,
            self.long_click_adb)
        method(x, y, duration)

    def swipe(self, p1, p2, duration=(0.1, 0.2), control_name='SWIPE', distance_check=True):
        self.handle_control_check(control_name)
        p1, p2 = ensure_int(p1, p2)
        duration = ensure_time(duration)
        method = self.config.script.device.control_method
        if method == 'minitouch':
            logger.info('Swipe %s -> %s' % (point2str(*p1), point2str(*p2)))
        elif method == 'window_message':
            logger.info('Swipe %s -> %s' % (point2str(*p1), point2str(*p2)))
        elif method == 'uiautomator2':
            logger.info('Swipe %s -> %s, %s' % (point2str(*p1), point2str(*p2), duration))
        elif method == 'scrcpy':
            logger.info('Swipe %s -> %s' % (point2str(*p1), point2str(*p2)))
        # elif method == 'MaaTouch':
        #     logger.info('Swipe %s -> %s' % (point2str(*p1), point2str(*p2)))
        else:
            # ADB needs to be slow, or swipe doesn't work
            duration *= 2.5
            logger.info('Swipe %s -> %s, %s ' % (point2str(*p1), point2str(*p2), duration))

        if distance_check:
            if p1[0] == p2[0]:
                logger.info('Swipe x distance is 0')
                p1[0] += 1
            if p1[1] == p2[1]:
                logger.info('Swipe y distance is 0')
                p1[1] += 1

            if np.linalg.norm(np.subtract(p1, p2)) < 10:
                # Should swipe a certain distance, otherwise AL will treat it as click.
                # uiautomator2 should >= 6px, minitouch should >= 5px
                logger.info('Swipe distance < 10px, dropped')
                return

        if method == 'minitouch':
            self.swipe_minitouch(p1, p2)
        elif method == 'window_message':
            self.swipe_window_message(p1, p2)
        elif method == 'uiautomator2':
            self.swipe_uiautomator2(p1, p2, duration=duration)
        elif method == 'scrcpy':
            self.swipe_scrcpy(p1, p2)
        # elif method == 'MaaTouch':
        #     self.swipe_maatouch(p1, p2)
        else:
            self.swipe_adb(p1, p2, duration=duration)

    def swipe_vector(self, vector, box=(123, 159, 1175, 628), random_range=(0, 0, 0, 0), padding=15,
                     duration=(0.1, 0.2), whitelist_area=None, blacklist_area=None, name='SWIPE', distance_check=True):
        """Method to swipe.

        Args:
            box (tuple): Swipe in box (upper_left_x, upper_left_y, bottom_right_x, bottom_right_y).
            vector (tuple): (x, y).
            random_range (tuple): (x_min, y_min, x_max, y_max).
            padding (int):
            duration (int, float, tuple):
            whitelist_area: (list[tuple[int]]):
                A list of area that safe to click. Swipe path will end there.
            blacklist_area: (list[tuple[int]]):
                If none of the whitelist_area satisfies current vector, blacklist_area will be used.
                Delete random path that ends in any blacklist_area.
            name (str): Swipe name
            distance_check: (bool):
        """
        p1, p2 = random_rectangle_vector_opted(
            vector,
            box=box,
            random_range=random_range,
            padding=padding,
            whitelist_area=whitelist_area,
            blacklist_area=blacklist_area
        )
        self.swipe(p1, p2, duration=duration, name=name, distance_check=distance_check)

    def drag(self, p1, p2, segments=1, shake=(0, 15), point_random=(-10, -10, 10, 10), shake_random=(-5, -5, 5, 5),
             swipe_duration=0.25, shake_duration=0.1, name='DRAG'):
        self.handle_control_check(name)
        p1, p2 = ensure_int(p1, p2)
        logger.info(
            'Drag %s -> %s' % (point2str(*p1), point2str(*p2))
        )
        method = self.config.script.emulator.control_method
        if method == 'minitouch':
            self.drag_minitouch(p1, p2, point_random=point_random)
        elif method == 'uiautomator2':
            self.drag_uiautomator2(
                p1, p2, segments=segments, shake=shake, point_random=point_random, shake_random=shake_random,
                swipe_duration=swipe_duration, shake_duration=shake_duration)
        elif method == 'scrcpy':
            self.drag_scrcpy(p1, p2, point_random=point_random)
        # elif method == 'MaaTouch':
        #     self.drag_maatouch(p1, p2, point_random=point_random)
        else:
            logger.warning(f'Control method {method} does not support drag well, '
                           f'falling back to ADB swipe may cause unexpected behaviour')
            self.swipe_adb(p1, p2, duration=ensure_time(swipe_duration * 2))
            # self.click(Button(area=(), color=(), button=area_offset(point_random, p2), name=name))

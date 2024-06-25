import cv2
import copy
import shutil
import time
import numpy as np

from datetime import datetime
from cached_property import cached_property
from pathlib import Path
from numpy import uint8, fromfile
from rich.table import Table
from threading import Event, Lock, Thread
from oashya.labels import id2label, CLASSIFY, CLASSINDEX, id2name
from oashya.utils import draw_tracks
from oashya.tracker import Tracker

from tasks.base_task import BaseTask
from module.logger import logger
from tasks.Hyakkiyakou.agent.focus import Focus


def test_track(show: bool = False):
    tracker = Tracker()
    # --------------------------------
    #
    folder_save = Path('./tasks/Hyakkiyakou/temp/save')
    shutil.rmtree(folder_save, ignore_errors=True)
    folder_save.mkdir(parents=True, exist_ok=True)
    folder_image = Path('./tasks/Hyakkiyakou/temp/20240621T221325')
    #
    start_time = datetime.now()
    for index, file in enumerate(folder_image.iterdir()):
        print(f'{index}-----------------------------------------------------------------------------------------------')
        if file.suffix != '.png':
            continue
        image = cv2.imdecode(fromfile(str(file), dtype=uint8), -1)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = tracker(image=image, response=[0, 0, False, 10])
        print(results)
        save_file = folder_save / f'{file.stem}.png'
        draw_image = draw_tracks(image, results)
        if show:
            cv2.imshow('OAS Tracker', draw_image)
            cv2.waitKey(500)
            print('Press any key to continue')
        else:
            cv2.imwrite(str(save_file), draw_image)
        # if index >= 14:
        #     raise
    end_time = datetime.now()
    print(f'平均时间: {(end_time - start_time) / len([folder_image.iterdir()])}')


def show_track(sync_image, sync_lock, stop_event):
    # global glob_image
    while True:
        if stop_event.is_set():
            logger.info('OAS Track Debugger stopped')
            cv2.destroyAllWindows()
            break
        sync_lock.acquire()
        if Debugger.sync_image is None:
            logger.info('OAS Track Debugger not started')
            time.sleep(1)
            sync_lock.release()
            continue
        cv2.imshow('OAS Tracker', Debugger.sync_image)
        sync_lock.release()
        cv2.waitKey(100)


class Debugger:
    info_enable: bool = False
    sync_image = None
    sync_lock = Lock()
    stop_event = Event()
    sync_thread = Thread(target=show_track, daemon=True, name='OAS Track Debugger',
                         args=(sync_image, sync_lock, stop_event))
    # sync_event = Event()  # reserved for future use
    # -------------------------------------------------------------------------

    def __init__(self, 
                 info_enable: bool = False, 
                 continuous_learning: bool = False,
                 hya_save_result: bool = False):
        self._reset_thread_env()
        Debugger.info_enable = info_enable
        self.images_cache: dict = {}
        self.continuous_learning = continuous_learning
        self.hya_save_result = hya_save_result
        if continuous_learning:
            logger.info('Continuous Learning Mode Enabled')
            save_time = datetime.now().strftime('%Y%m%dT%H')
            self.hya_save_folder: Path = Path(f'./log/hya/{save_time}')
            self.hya_save_folder.mkdir(parents=True, exist_ok=True)
        if hya_save_result:
            logger.info('Hyakkiyakou Save Result Mode Enabled')
            save_time = datetime.now().strftime('%Y%m%dT%H')
            self.hya_save_result_folder: Path = Path(f'./log/hyakkiyakou/{save_time}')
            self.hya_save_result_folder.mkdir(parents=True, exist_ok=True)

    @cached_property
    def save_class(self) -> list[int]:
        """
        需要保存的类别
        @return:
        """
        sp = [i for i in range(CLASSINDEX.MIN_SP, CLASSINDEX.MAX_SP + 1)]
        ssr = [i for i in range(CLASSINDEX.MIN_SSR, CLASSINDEX.MAX_SSR + 1)]
        g = [i for i in range(CLASSINDEX.MIN_G, CLASSINDEX.MAX_G + 1)]
        return sp + ssr + g

    def _reset_thread_env(self):
        logger.info('Reset Debugger Thread Environment')
        Debugger.sync_image = None
        self.sync_lock = Lock()
        self.stop_event = Event()
        self.sync_thread = Thread(target=show_track, daemon=True, name='OAS Track Debugger',
                                  args=(Debugger.sync_image, self.sync_lock, self.stop_event))

    def show(self, results):
        image = draw_tracks(self.device.image, results)
        cv2.imshow('OAS Tracker', image)

    def show_start(self):
        logger.info('OAS Track Debugger show image start')
        Debugger.sync_image = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.sync_thread.start()

    def show_sync(self, image=None):
        self.sync_lock.acquire()
        if image is not None:
            # deepcopy
            Debugger.sync_image = copy.deepcopy(image)
            # logger.info('OAS Track Debugger synced image')
        self.sync_lock.release()

    def show_stop(self):
        logger.info('OAS Track Debugger show image stop')
        self.stop_event.set()
        self.sync_thread.join()

    def check_class(self, _class: int) -> bool:
        return _class in self.save_class

    def deal_learning(self, image, tracks: list):
        save_flag: bool = False
        for _id, _class, _conf, _cx, _cy, _w, _h, _v in tracks:
            if self.check_class(_class):
                save_flag = True
                break
        if not save_flag:
            return
        time_now_image_name = f'hya_{int(time.time() * 1000)}'
        self.images_cache[time_now_image_name] = image

    def save_images(self):
        if not self.images_cache:
            self.images_cache: dict = {}
            return
        logger.info('OAS Track Debugger save images to train model')
        for image_name, image in self.images_cache.items():
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            cv2.imwrite(str(self.hya_save_folder / f'{image_name}.png'), image)
        self.images_cache.clear()

    def save_result(self, image):
        if not self.hya_save_result:
            return
        _now_name = f'hya_{int(time.time() * 1000)}.png'
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        cv2.imwrite(str(self.hya_save_result_folder / _now_name), image)

    @classmethod
    def show_info(cls, tracker, f: Focus):
        table = Table(show_lines=True)
        table.add_column('Property', header_style="bright_cyan", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")
        table.add_column('Property', header_style="bright_cyan", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")
        if f is not None:
            try:
                table.add_row('id', str(f._id), 'conf', f'{f._conf:.2f}')
                table.add_row('class', str(f._class), 'xywh', f'({f._cx}, {f._cy}, {f._w}, {f._h})')
                table.add_row('label', id2label(f._class), 'velocity', f'{f._v:.2f}')
                table.add_row('name', f'{id2name(f._class)}', 'omega', str(f._omega))
            except Exception as e:
                pass
        table.add_row('detect cost', f'{(tracker.detect_time.total_seconds() * 1000):.2f}ms',
                    'track cost', f'{(tracker.track_time.total_seconds() * 1000):.2f}ms')
        logger.print(table, justify='center')


def test_debugger():
    debugger = Debugger(info_enable=False, continuous_learning=True)
    debugger.show_start()
    folder_image = Path('./tasks/Hyakkiyakou/temp/20240621T221325')
    for index, file in enumerate(folder_image.iterdir()):
        print(f'{index}-----------------------------------------------------------------------------------------------')
        if file.suffix != '.png':
            continue
        image = cv2.imdecode(fromfile(str(file), dtype=uint8), -1)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        debugger.show_sync(image)
        tracks = [[1, 190, 0.9, 0, 0, 0, 0, 0]]
        debugger.deal_learning(image=image, tracks=tracks)
        time.sleep(0.5)
        if index >= 19:
            break
    debugger.show_stop()
    debugger.save_images()


if __name__ == '__main__':
    # test_track()
    test_debugger()
    pass

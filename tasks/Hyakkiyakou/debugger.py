import cv2
import copy
import shutil
import time
import numpy as np

from datetime import datetime
from pathlib import Path
from numpy import uint8, fromfile
from threading import Event, Lock, Thread
from oashya.labels import id2label, CLASSIFY
from oashya.utils import draw_tracks
from oashya.tracker import Tracker

from tasks.base_task import BaseTask
from module.logger import logger


def test_track(show : bool = False):
    tracker = Tracker()
    # --------------------------------
    #
    folder_save = Path('./tasks/Hyakkiyakou/temp/save')
    shutil.rmtree(folder_save, ignore_errors=True)
    folder_save.mkdir(parents=True, exist_ok=True)
    folder_image = Path('./tasks/Hyakkiyakou/temp/20240526T103931')
    #
    start_time = datetime.now()
    for index, file in enumerate(folder_image.iterdir()):
        print(f'{index}-----------------------------------------------------------------------------------------------')
        if file.suffix != '.png':
            continue
        img = cv2.imdecode(fromfile(str(file), dtype=uint8), -1)
        image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = tracker(image=image)
        save_file = folder_save / f'{file.stem}.png'
        draw_image = draw_tracks(image, results)
        if show:
            cv2.imshow('OAS Tracker', draw_image)
            time.sleep(2)
            cv2.waitKey(10000)
            print('Press any key to continue')
        else:
            cv2.imwrite(str(save_file), draw_image)
        if index >= 4:
            raise
    end_time = datetime.now()
    print(f'平均时间: {(end_time - start_time) / len([folder_image.iterdir()])}')


glob_image = np.zeros((720, 1280, 3), dtype=np.uint8)

def show_track(sync_image, sync_lock, stop_event):
    global glob_image
    while True:
        if stop_event.is_set():
            logger.info('OAS Track Debugger stopped')
            break
        sync_lock.acquire()
        cv2.imshow('OAS Tracker', glob_image)
        sync_lock.release()
        cv2.waitKey(100)


class Debugger:
    sync_image = np.zeros((720, 1280, 3), dtype=np.uint8)
    sync_lock = Lock()
    stop_event = Event()
    sync_thread = Thread(target=show_track, daemon=True, name='OAS Track Debugger',
                         args=(sync_image, sync_lock, stop_event))
    # sync_event = Event()  # reserved for future use

    def show(self, results):
        image = draw_tracks(self.device.image, results)
        cv2.imshow('OAS Tracker', image)

    def show_start(self):
        logger.info('OAS Track Debugger started')
        self.sync_thread.start()

    def show_sync(self, image=None):
        self.sync_lock.acquire()
        if image is not None:
            # deepcopy
            global glob_image
            glob_image = copy.deepcopy(image)
            self.sync_image = copy.deepcopy(image)
            logger.info('OAS Track Debugger synced image')
        self.sync_lock.release()

    def show_stop(self):
        self.stop_event.set()
        self.sync_thread.join()


def test_debugger():
    debugger = Debugger()
    debugger.show_start()
    folder_image = Path('./tasks/Hyakkiyakou/temp/20240526T103931')
    for index, file in enumerate(folder_image.iterdir()):
        print(f'{index}-----------------------------------------------------------------------------------------------')
        if file.suffix != '.png':
            continue
        img = cv2.imdecode(fromfile(str(file), dtype=uint8), -1)
        image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        debugger.show_sync(image)
        time.sleep(0.1)
    debugger.show_stop()


if __name__ == '__main__':
    test_debugger()

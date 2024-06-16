import cv2
import shutil
import time
import numpy as np

from datetime import datetime
from pathlib import Path
from numpy import uint8, fromfile
from oashya.labels import id2label, CLASSIFY
from oashya.utils import draw_tracks
from oashya.tracker import Tracker

from tasks.base_task import BaseTask


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






class Debugger(BaseTask):

    def show(self, results):
        image = draw_tracks(self.device.image, results)
        cv2.imshow('OAS Tracker', image)


if __name__ == '__main__':
    pass

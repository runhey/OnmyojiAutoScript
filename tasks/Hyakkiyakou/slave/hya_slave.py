import cv2

from pathlib import Path

from tasks.Hyakkiyakou.slave.hya_device import HyaDevice


class HyaSlave(HyaDevice):
    """
    主要是用来跟游戏进行交互的
    """
    pass

def covert_rgb():
    images_folders: Path = Path(r'E:\Project\OnmyojiAutoScript\tasks\Hyakkiyakou\temp\20240526T103931')
    save_folders = images_folders.parent / 'save'
    save_folders.mkdir(parents=True, exist_ok=True)
    for file in images_folders.iterdir():
        if file.suffix != '.png':
            continue
        img = cv2.imread(str(file))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        cv2.imwrite(str(save_folders / file.name), img)


if __name__ == '__main__':
    pass


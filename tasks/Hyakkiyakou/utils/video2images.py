import cv2

from datetime import datetime
from pathlib import Path

from module.logger import logger

from tasks.base_task import BaseTask
from tasks.Hyakkiyakou.assets import HyakkiyakouAssets


class TransformVideo(HyakkiyakouAssets):
    def __init__(self, change_channel: bool = False, interval: float = 2):
        """

        @param interval: 视频帧间隔，默认2
        @param change_channel: 修改视频通道数，默认False
        """
        self.change_channel = change_channel
        self.interval = interval

    def run(self, video: str | Path, save_path: str | Path):
        """

        @param video: 视频的路径，可以是单个视频也可以是一个文件夹
        @param save_path: 保存的路径
        @return:
        """
        if isinstance(video, str):
            video = Path(video)
        if not isinstance(video, Path):
            logger.error(f'{video} is not a valid path')
            return
        if isinstance(save_path, str):
            save_path = Path(save_path)
        if not isinstance(save_path, Path):
            logger.error(f'{save_path} is not a valid path')
            return
        save_path.mkdir(parents=True, exist_ok=True)
        if video.is_dir():
            for video_file in video.iterdir():
                self.parse_one(video_file, save_path)
        else:
            self.parse_one(video, save_path)

    def parse_one(self, video: Path, save_path: Path):
        """
        单次解析一个视频
        @param video:
        @param save_path:
        @return:
        """
        # 获取时间戳的str形式，用来命名图片
        datetime_now = datetime.now().strftime('%Y%m%dT%H%M%S')
        logger.info(f'Start transform video {video}')

        cap = cv2.VideoCapture(str(video))
        if not cap.isOpened():
            logger.error(f'{video} open failed')
            return
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_skip = int(fps * self.interval)
        count_frame = 0  # 抽帧用的
        index_frame = 0  # 记录
        while 1:
            ret, frame = cap.read()
            if not ret:
                break
            w, h, _ = frame.shape
            if w != 1280 and h != 720:
                frame = cv2.resize(frame, (1280, 720))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # 抽帧
            count_frame += 1
            if count_frame % frame_skip != 0:
                continue

            if not self.I_CHECK_RUN.match(frame, threshold=0.6):
                continue
            if not self.change_channel:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            index_frame += 1
            cv2.imwrite(str(save_path / f'{datetime_now}_{index_frame:05d}.png'), frame)
            cv2.imshow('frame', frame)
            cv2.waitKey(100)
            cv2.destroyAllWindows()

        cap.release()
        logger.info(f'{video} done')


if __name__ == '__main__':
    VIDEO = 'D:/Project/Hyakkiyakou/OnmyojiAutoScript-hyakkiyakou/temp/sources_video/001-砸百鬼靠技术？在绝对的运气面前，所有技术.mp4'
    SAVE_PATH = 'D:/Project/Hyakkiyakou/OnmyojiAutoScript-hyakkiyakou/temp/sources_images'
    t = TransformVideo()
    t.run(VIDEO, SAVE_PATH)

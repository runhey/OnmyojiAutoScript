from typing import Dict

from module.base.decorator import cached_property
from module.ocr.ppocr import TextSystem
from module.ocr.rpc import ModelProxy
from module.server.setting import State


class OcrModel:
    @cached_property
    def ch(self):
        return TextSystem()


OCR_MODEL = OcrModel()

_OCR_PROXY_CACHE: Dict[str, ModelProxy] = {}


def get_ocr_model(lang: str = "ch"):
    deploy_config = State.deploy_config
    if deploy_config.UseOcrServer:
        address = deploy_config.OcrClientAddress or "127.0.0.1:22268"
        if address not in _OCR_PROXY_CACHE:
            _OCR_PROXY_CACHE[address] = ModelProxy(address)
        return _OCR_PROXY_CACHE[address]
    return getattr(OCR_MODEL, lang)


if __name__ == "__main__":
    model = OCR_MODEL.ch
    import cv2
    import time
    from memory_profiler import profile
    image = cv2.imread(r"E:\Project\OnmyojiAutoScript-assets\jade.png")

    # 引入ocr 会导致非常巨大的内存开销
    @profile
    def test_memory():
        for i in range(2):
            start_time = time.time()
            result = model.detect_and_ocr(image)
            print(result)
            end_time = time.time()
            print(f'耗时：{end_time-start_time}')

    test_memory()

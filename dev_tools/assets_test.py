import cv2
import numpy as np

from numpy import float32, int32, uint8, fromfile
from pathlib import Path

from module.logger import logger
from module.atom.image import RuleImage
from module.atom.ocr import RuleOcr


def load_image(file: str, strict_size: bool = True):
    file = Path(file)
    img = cv2.imdecode(fromfile(file, dtype=uint8), -1)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    height, width, channels = img.shape
    if strict_size and (height != 720 or width != 1280):
        logger.error(f'Image size is {height}x{width}, not 720x1280')
        return None
    return img


def detect_image(file: str, targe: RuleImage) -> bool:
    img = load_image(file)
    result = targe.test_match(img)
    logger.info(f'[{targe.name}]: {result}')
    return result


def detect_ocr(file: str, target: RuleOcr):
    img = load_image(file)
    return target.ocr(img)


def _roi_to_text(roi: list | tuple) -> str:
    x, y, w, h = roi
    return f"{int(round(x))},{int(round(y))},{int(round(w))},{int(round(h))}"


def detect_image_detail(file: str, target: RuleImage) -> dict:
    img = load_image(file, strict_size=False)
    if img is None:
        return {
            "matched": False,
            "similarity": 0.0,
            "roiFront": _roi_to_text(target.roi_front),
            "roiBack": _roi_to_text(target.roi_back),
            "message": "image_load_failed",
        }

    similarity = 0.0
    matched = False
    message = "not_match"

    if target.is_template_match:
        source = target.corp(img)
        mat = target.image
        if source.shape[0] < mat.shape[0] or source.shape[1] < mat.shape[1]:
            return {
                "matched": False,
                "similarity": 0.0,
                "roiFront": _roi_to_text(target.roi_front),
                "roiBack": _roi_to_text(target.roi_back),
                "message": "roi_back_too_small",
            }
        res = cv2.matchTemplate(source, mat, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        similarity = float(max_val)
        matched = similarity >= target.threshold
        target.roi_front[0] = int(max_loc[0] + target.roi_back[0])
        target.roi_front[1] = int(max_loc[1] + target.roi_back[1])
        target.roi_front[2] = int(mat.shape[1])
        target.roi_front[3] = int(mat.shape[0])
        message = "match" if matched else "not_match"
    else:
        try:
            matched = bool(target.test_match(img))
            similarity = 1.0 if matched else 0.0
            message = "match" if matched else "not_match"
        except Exception as e:
            message = f"sift_error:{e}"

    return {
        "matched": matched,
        "similarity": round(similarity, 4),
        "roiFront": _roi_to_text(target.roi_front),
        "roiBack": _roi_to_text(target.roi_back),
        "message": message,
    }


def detect_ocr_detail(file: str, target: RuleOcr) -> dict:
    img = load_image(file, strict_size=False)
    if img is None:
        return {
            "matched": False,
            "similarity": 0.0,
            "text": "",
            "roiFront": _roi_to_text(target.roi),
            "roiBack": _roi_to_text(target.area),
            "message": "image_load_failed",
        }

    boxed = target.detect_and_ocr(img, logDisplay=False)
    selected = None

    if boxed:
        if target.keyword:
            for item in boxed:
                text = str(item.ocr_text or "")
                if target.keyword in text or text == target.keyword:
                    selected = item
                    break
        if selected is None:
            selected = max(boxed, key=lambda x: float(x.score))

    if selected is None:
        return {
            "matched": False,
            "similarity": 0.0,
            "text": "",
            "roiFront": _roi_to_text(target.roi),
            "roiBack": _roi_to_text(target.area),
            "message": "not_match",
        }

    box = selected.box
    x0 = int(np.min(box[:, 0])) + int(target.roi[0])
    y0 = int(np.min(box[:, 1])) + int(target.roi[1])
    x1 = int(np.max(box[:, 0])) + int(target.roi[0])
    y1 = int(np.max(box[:, 1])) + int(target.roi[1])
    w = max(1, x1 - x0)
    h = max(1, y1 - y0)

    target.roi = [x0, y0, w, h]
    target.area = [x0, y0, w, h]

    text = str(selected.ocr_text or "")
    matched = target.match(text, included=True) if target.keyword else bool(text)

    return {
        "matched": matched,
        "similarity": round(float(selected.score), 4),
        "text": text,
        "roiFront": _roi_to_text(target.roi),
        "roiBack": _roi_to_text(target.area),
        "message": "match" if matched else "not_match",
    }


# 图片文件路径 可以是相对路径
IMAGE_FILE = r"C:\Users\Ryland\Desktop\ScreenShot_2026-05-30_141821_235.png"
if __name__ == '__main__':
    from tasks.Exploration.script_task import ScriptTask
    targe = ScriptTask.I_TREASURE_BOX_CLICK
    print(detect_image(IMAGE_FILE, targe))

    # ocr demo
    # from tasks.KekkaiActivation.assets import KekkaiActivationAssets
    # target = KekkaiActivationAssets.O_CARD_ALL_TIME
    # print(detect_ocr(IMAGE_FILE, target))

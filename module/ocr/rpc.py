# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import atexit
import multiprocessing
import pickle
import socket
import time
from typing import Any, Dict, List, Optional

import numpy as np
import zerorpc

from module.exception import ScriptError
from module.logger import logger
from module.ocr.ppocr import TextSystem

_OCR_SERVER_PROCESS: Optional[multiprocessing.Process] = None


def _normalize_address(address: str) -> str:
    if address.startswith("tcp://"):
        return address
    return f"tcp://{address}"


def _split_host_port(address: str) -> tuple[str, int]:
    addr = address.replace("tcp://", "")
    if ":" not in addr:
        return addr, 22268
    host, port = addr.rsplit(":", 1)
    return host, int(port)


def _is_port_in_use(host: str, port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(0.5)
        s.connect((host, port))
        s.shutdown(2)
        return True
    except Exception:
        return False
    finally:
        s.close()


def ensure_ocr_server_started() -> bool:
    from module.server.setting import State

    deploy_config = State.deploy_config
    if not deploy_config.StartOcrServer:
        return False

    if deploy_config.OcrServerPort:
        port = int(deploy_config.OcrServerPort)
    else:
        _, port = _split_host_port(str(deploy_config.OcrClientAddress))
    host = "0.0.0.0"

    if _is_port_in_use("127.0.0.1", port):
        logger.info(f"OCR server already running on port {port}")
        return True

    global _OCR_SERVER_PROCESS
    if _OCR_SERVER_PROCESS is not None and _OCR_SERVER_PROCESS.is_alive():
        logger.info("OCR server process already started")
        return True

    _OCR_SERVER_PROCESS = multiprocessing.Process(
        target=run_ocr_server,
        args=(host, port),
        name="ocr_server",
        daemon=True,
    )
    _OCR_SERVER_PROCESS.start()
    logger.info(f"Start OCR server on {host}:{port}")
    for _ in range(50):
        if _is_port_in_use("127.0.0.1", port):
            return True
        time.sleep(0.1)
    logger.error(f"OCR server is not ready on port {port}")
    return False


def shutdown_ocr_server(timeout: float = 2.0) -> bool:
    global _OCR_SERVER_PROCESS

    process = _OCR_SERVER_PROCESS
    if process is None:
        return False

    if not process.is_alive():
        _OCR_SERVER_PROCESS = None
        return False

    logger.info("Stopping OCR server process")
    try:
        process.terminate()
        process.join(timeout=timeout)
        if process.is_alive():
            logger.warning("OCR server process did not exit in time, force killing")
            process.kill()
            process.join(timeout=1.0)
        logger.info("OCR server process stopped")
        return True
    except Exception as e:
        logger.exception(e)
        return False
    finally:
        _OCR_SERVER_PROCESS = None


def run_ocr_server(host: str, port: int) -> None:
    server = zerorpc.Server(OcrServer())
    server.bind(f"tcp://{host}:{port}")
    server.run()


class OcrServer:
    def __init__(self) -> None:
        self.model = TextSystem()

    def ping(self) -> bool:
        return True

    @staticmethod
    def _rotate_vertical(image: np.ndarray) -> np.ndarray:
        height, width = image.shape[0:2]
        if height * 1.0 / width >= 1.5:
            return np.rot90(image)
        return image

    def ocr_single_line(self, image_bytes: bytes):
        image = pickle.loads(image_bytes)
        result, score = self.model.ocr_single_line(image)
        return result, float(score)

    def detect_and_ocr(
        self,
        image_bytes: bytes,
        drop_score: float = 0.5,
        unclip_ratio: Optional[float] = None,
        box_thresh: Optional[float] = None,
        vertical: bool = False,
    ) -> List[Dict[str, Any]]:
        image = pickle.loads(image_bytes)
        if not vertical:
            results = self.model.detect_and_ocr(image, drop_score=drop_score,
                                                unclip_ratio=unclip_ratio,
                                                box_thresh=box_thresh)
            return [
                {"box": r.box.tolist(), "ocr_text": r.ocr_text, "score": float(r.score)}
                for r in results
            ]

        text_recognizer = self.model.text_recognizer

        def vertical_text_recognizer(img_crop_list):
            img_crop_list = [self._rotate_vertical(i) for i in img_crop_list]
            return text_recognizer(img_crop_list)

        self.model.text_recognizer = vertical_text_recognizer
        try:
            results = self.model.detect_and_ocr(image, drop_score=drop_score,
                                                unclip_ratio=unclip_ratio,
                                                box_thresh=box_thresh)
        finally:
            self.model.text_recognizer = text_recognizer

        return [
            {"box": r.box.tolist(), "ocr_text": r.ocr_text, "score": float(r.score)}
            for r in results
        ]


class ModelProxy:
    is_proxy = True

    def __init__(self, address: str) -> None:
        self.address = _normalize_address(address)
        self.client = zerorpc.Client()
        try:
            self.client.connect(self.address)
            self.client.ping()
        except Exception as e:
            raise ScriptError(f"OCR server connection failed: {self.address}") from e

    def ocr_single_line(self, image: np.ndarray):
        payload = pickle.dumps(image, protocol=4)
        return self.client.ocr_single_line(payload)

    def detect_and_ocr(
        self,
        image: np.ndarray,
        drop_score: float = 0.5,
        unclip_ratio: Optional[float] = None,
        box_thresh: Optional[float] = None,
        vertical: bool = False,
    ):
        payload = pickle.dumps(image, protocol=4)
        results = self.client.detect_and_ocr(payload, drop_score, unclip_ratio, box_thresh, vertical)
        from ppocronnx.predict_system import BoxedResult
        return [
            BoxedResult(np.array(item["box"]), None, item["ocr_text"], item["score"])
            for item in results
        ]


atexit.register(shutdown_ocr_server)

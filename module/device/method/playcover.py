import socket
import struct
import time

import cv2
import numpy as np


class PlayCoverError(RuntimeError):
    pass


class PlayCoverProtocolError(PlayCoverError):
    pass


class PlayCoverClient:
    HANDSHAKE = b'MAA\x00'
    HANDSHAKE_OK = b'OKAY'
    DEFAULT_TIMEOUT = 10.0
    MAX_FRAME_BYTES = 256 * 1024 * 1024
    TOUCH_BEGAN = 0
    TOUCH_MOVED = 1
    TOUCH_ENDED = 3

    def __init__(self, address, *, screenshot_mode='MacBGR',
                 timeout=DEFAULT_TIMEOUT, socket_factory=socket.create_connection):
        self.host, self.port = self._parse_address(address)
        self.screenshot_mode = getattr(screenshot_mode, 'value', screenshot_mode)
        self.timeout = float(timeout)
        self.socket_factory = socket_factory
        self._socket = None
        self.version = None
        self.width = None
        self.height = None

    @staticmethod
    def _parse_address(address):
        text = str(address).strip()
        if not text or '://' in text:
            raise PlayCoverError(f'Invalid PlayCover address: {address!r}')
        if text.isdigit():
            host, port_text = '127.0.0.1', text
        else:
            try:
                host, port_text = text.rsplit(':', 1)
            except ValueError as exc:
                raise PlayCoverError(f'Invalid PlayCover address: {address!r}') from exc
        try:
            port = int(port_text)
        except ValueError as exc:
            raise PlayCoverError(f'Invalid PlayCover port: {port_text!r}') from exc
        if not host or not 1 <= port <= 65535:
            raise PlayCoverError(f'Invalid PlayCover address: {address!r}')
        return host, port

    @property
    def connected(self):
        return self._socket is not None

    @property
    def screen_size(self):
        if self.width is None or self.height is None:
            return None
        return self.width, self.height

    def connect(self):
        if self._socket is not None:
            return self
        sock = None
        try:
            sock = self.socket_factory((self.host, self.port), self.timeout)
            sock.settimeout(self.timeout)
            sock.sendall(self.HANDSHAKE)
            if self.recv_exact(sock, 4) != self.HANDSHAKE_OK:
                raise PlayCoverProtocolError('Invalid MaaTools handshake')
            self._socket = sock
            self._send(b'VERN')
            self.version = self._read('>I')[0]
            self.width, self.height = self._read_size()
            return self
        except PlayCoverError:
            self._socket = None
            self._close(sock)
            raise
        except OSError as exc:
            self._socket = None
            self._close(sock)
            raise PlayCoverError('PlayCover connection failed') from exc

    def close(self):
        sock, self._socket = self._socket, None
        self.version = None
        self.width = None
        self.height = None
        self._close(sock)

    def screenshot(self):
        self._ensure_connected()
        if self.screenshot_mode == 'MacBGR':
            return self._screenshot_bgr()
        if self.screenshot_mode in ('RGBA', 'MacSCK'):
            return self._screenshot_rgba()
        raise PlayCoverProtocolError(
            f'Unsupported PlayCover screenshot mode: {self.screenshot_mode}'
        )

    def refresh_size(self):
        if self._socket is None:
            self.connect()
        if self.screen_size is None:
            self.width, self.height = self._read_size()
        return self.width, self.height

    def click(self, x, y):
        self.touch(self.TOUCH_BEGAN, x, y)
        time.sleep(0.05)
        self.touch(self.TOUCH_ENDED, x, y)

    def long_click(self, x, y, duration=0.8):
        self.touch(self.TOUCH_BEGAN, x, y)
        time.sleep(max(0, float(duration)))
        self.touch(self.TOUCH_ENDED, x, y)

    def swipe(self, p1, p2, duration=0.2):
        self.touch(self.TOUCH_BEGAN, p1[0], p1[1])
        self.touch(self.TOUCH_MOVED, p2[0], p2[1])
        time.sleep(max(0, float(duration)))
        self.touch(self.TOUCH_ENDED, p2[0], p2[1])

    def touch(self, phase, x, y):
        self._ensure_connected()
        width, height = self.screen_size
        x = max(0, min(width - 1, int(x)))
        y = max(0, min(height - 1, int(y)))
        self._send(b'TUCH', bytes((int(phase),)) + struct.pack('>HH', x, y))

    def _screenshot_bgr(self):
        self._send(b'BGR\x01')
        width, height, length = self._read('>III')
        data = self._frame(width, height, length, 3)
        self.width, self.height = width, height
        image = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 3))
        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    def _screenshot_rgba(self):
        width, height = self.screen_size
        self._send(b'SCRN')
        length = self._read('>I')[0]
        data = self._frame(width, height, length, 4)
        image = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 4))
        return cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)

    def _read_size(self):
        self._send(b'SIZE')
        width, height = self._read('>HH')
        if width <= 0 or height <= 0 or width * height * 4 > self.MAX_FRAME_BYTES:
            raise PlayCoverProtocolError(f'Invalid MaaTools size: {width}x{height}')
        return width, height

    def _frame(self, width, height, length, channels):
        expected = width * height * channels
        if width <= 0 or height <= 0 or length != expected or length > self.MAX_FRAME_BYTES:
            raise PlayCoverProtocolError(
                f'Invalid MaaTools frame length: {length}, expected {expected}'
            )
        return self.recv_exact(self._socket, length)

    def _read(self, fmt):
        return struct.unpack(fmt, self.recv_exact(self._socket, struct.calcsize(fmt)))

    def _send(self, command, payload=b''):
        size = len(command) + len(payload)
        if len(command) != 4 or size > 0xffff:
            raise PlayCoverProtocolError('Invalid MaaTools command')
        if self._socket is None:
            raise PlayCoverError('PlayCover socket is not connected')
        self._socket.sendall(struct.pack('>H', size) + command + payload)

    def _ensure_connected(self):
        if self._socket is None:
            self.connect()

    @staticmethod
    def recv_exact(sock, size):
        data = bytearray()
        while len(data) < size:
            try:
                chunk = sock.recv(size - len(data))
            except OSError as exc:
                raise PlayCoverError('PlayCover socket read failed') from exc
            if not chunk:
                raise PlayCoverError('PlayCover socket closed')
            data.extend(chunk)
        return bytes(data)

    @staticmethod
    def _close(sock):
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

import struct
import unittest
from unittest.mock import patch

try:
    import numpy as np
    from module.device.method.playcover import (
        PlayCoverClient,
        PlayCoverProtocolError,
    )
except ImportError as exc:
    np = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class FakeSocket:
    def __init__(self, incoming=b"", chunk_size=3):
        self.incoming = bytearray(incoming)
        self.chunk_size = chunk_size
        self.sent = bytearray()
        self.timeout = None
        self.closed = False

    def settimeout(self, timeout):
        self.timeout = timeout

    def sendall(self, data):
        if self.closed:
            raise OSError("closed")
        self.sent.extend(data)

    def recv(self, size):
        if self.closed or not self.incoming:
            return b""
        take = min(size, self.chunk_size, len(self.incoming))
        result = bytes(self.incoming[:take])
        del self.incoming[:take]
        return result

    def close(self):
        self.closed = True


def handshake_stream(width=1280, height=720, version=3):
    return b"OKAY" + struct.pack(">I", version) + struct.pack(">HH", width, height)


def command_frames(data):
    frames = []
    offset = 4
    while offset < len(data):
        length = struct.unpack(">H", data[offset:offset + 2])[0]
        offset += 2
        frames.append(bytes(data[offset:offset + length]))
        offset += length
    return frames


@unittest.skipIf(_IMPORT_ERROR is not None, f"optional image dependency unavailable: {_IMPORT_ERROR}")
class PlayCoverProtocolTests(unittest.TestCase):
    def make_client(self, incoming, **kwargs):
        sock = FakeSocket(incoming, chunk_size=kwargs.pop("chunk_size", 3))
        client = PlayCoverClient(
            "localhost:1718",
            socket_factory=lambda _address, _timeout: sock,
            **kwargs,
        )
        return client, sock

    def test_handshake_and_partial_recv(self):
        client, sock = self.make_client(handshake_stream(), chunk_size=1)
        client.connect()
        self.assertEqual(bytes(sock.sent[:4]), b"MAA\x00")
        self.assertEqual(command_frames(sock.sent), [b"VERN", b"SIZE"])
        self.assertEqual(client.screen_size, (1280, 720))
        self.assertEqual(sock.timeout, client.timeout)

    def test_bgr_is_decoded_to_rgb(self):
        bgr = bytes((1, 2, 3, 10, 20, 30))
        incoming = handshake_stream(2, 1) + struct.pack(">III", 2, 1, len(bgr)) + bgr
        client, sock = self.make_client(incoming)
        image = client.screenshot()
        self.assertEqual(image.shape, (1, 2, 3))
        self.assertEqual(image.tolist(), [[[3, 2, 1], [30, 20, 10]]])
        self.assertEqual(command_frames(sock.sent)[-1], b"BGR\x01")

    def test_scrn_decodes_rgba(self):
        rgba = bytes((1, 2, 3, 255, 10, 20, 30, 255))
        incoming = handshake_stream(2, 1) + struct.pack(">I", len(rgba)) + rgba
        client, sock = self.make_client(incoming, screenshot_mode="RGBA")
        image = client.screenshot()
        self.assertEqual(image.shape, (1, 2, 3))
        self.assertEqual(image.tolist(), [[[1, 2, 3], [10, 20, 30]]])
        self.assertEqual(command_frames(sock.sent)[-1], b"SCRN")

    def test_macsck_uses_scrn(self):
        rgba = bytes((1, 2, 3, 255))
        incoming = handshake_stream(1, 1) + struct.pack(">I", len(rgba)) + rgba
        client, sock = self.make_client(incoming, screenshot_mode="MacSCK")
        client.screenshot()
        self.assertEqual(command_frames(sock.sent)[-1], b"SCRN")

    def test_touch_phases_are_clamped(self):
        client, sock = self.make_client(handshake_stream(10, 5))
        with patch("module.device.method.playcover.time.sleep", return_value=None):
            client.click(-10, 99)
            client.swipe((-1, -2), (99, 88), duration=0)
        touch_frames = [frame for frame in command_frames(sock.sent) if frame[:4] == b"TUCH"]
        self.assertEqual([frame[4] for frame in touch_frames], [0, 3, 0, 1, 3])
        for frame in touch_frames:
            x, y = struct.unpack(">HH", frame[5:9])
            self.assertLessEqual(x, 9)
            self.assertLessEqual(y, 4)

    def test_invalid_frame_length_raises(self):
        incoming = handshake_stream(2, 1) + struct.pack(">III", 2, 1, 5) + b"12345"
        client, _sock = self.make_client(incoming)
        with self.assertRaises(PlayCoverProtocolError):
            client.screenshot()

    def test_bare_port_uses_localhost(self):
        sock = FakeSocket(handshake_stream())
        client = PlayCoverClient(
            "1718",
            socket_factory=lambda _address, _timeout: sock,
        )
        self.assertEqual((client.host, client.port), ("127.0.0.1", 1718))

if __name__ == "__main__":
    unittest.main()

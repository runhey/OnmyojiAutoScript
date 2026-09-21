import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock, patch


ROOT = Path(__file__).resolve().parents[1]


class PlayCoverIntegrationTests(unittest.TestCase):
    def test_template_defaults(self):
        template = json.loads((ROOT / "config" / "template.json").read_text(encoding="utf-8"))
        device = template["script"]["device"]
        self.assertEqual(device["serial"], "auto")
        self.assertEqual(device["screenshot_method"], "auto")
        self.assertEqual(device["control_method"], "minitouch")

    def test_playcover_screenshot_passes_through_1280x720(self):
        try:
            import numpy as np
            from module.device.screenshot import Screenshot
        except ImportError as exc:
            self.skipTest(f"optional OAS image dependencies unavailable: {exc}")

        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        fake = SimpleNamespace(
            playcover_client=SimpleNamespace(
                screenshot=lambda: image
            )
        )
        self.assertIs(Screenshot.screenshot_playcover(fake), image)

    def test_macplaytools_passes_oas_coordinates_to_playcover(self):
        try:
            from module.device.control import Control
        except ImportError as exc:
            self.skipTest(f"optional OAS control dependencies unavailable: {exc}")

        client = SimpleNamespace(
            click=Mock(),
            long_click=Mock(),
            swipe=Mock(),
        )
        control = SimpleNamespace(playcover_client=client)

        Control.click_playcover(control, 640, 360)
        Control.long_click_playcover(control, 640, 360, duration=1.2)
        Control.swipe_playcover(control, (10, 20), (1279, 719), duration=0.3)

        client.click.assert_called_once_with(640, 360)
        client.long_click.assert_called_once_with(640, 360, duration=1.2)
        client.swipe.assert_called_once_with((10, 20), (1279, 719), duration=0.3)

    def test_macplaytools_selects_playcover(self):
        try:
            from module.device.connection import Connection
            from module.device.connection_attr import ConnectionAttr
        except ImportError as exc:
            self.skipTest(f"optional OAS runtime dependencies unavailable: {exc}")

        device = SimpleNamespace(
            serial="localhost:1718",
            screenshot_method="MacBGR",
            control_method="MacPlayTools",
        )
        config = SimpleNamespace(script=SimpleNamespace(device=device))
        with patch("module.device.connection.PlayCoverClient") as playcover_client, \
                patch.object(Connection, "detect_device", side_effect=AssertionError("ADB detect called")), \
                patch.object(Connection, "adb_connect", side_effect=AssertionError("ADB connect called")), \
                patch.object(ConnectionAttr, "adb_client", new_callable=PropertyMock) as adb_client:
            connection = Connection(config)
        playcover_client.assert_called_once_with(
            "localhost:1718", screenshot_mode="MacBGR"
        )
        playcover_client.return_value.connect.assert_called_once_with()
        adb_client.assert_not_called()
        self.assertTrue(connection.is_playcover)
        self.assertEqual(connection.package, "com.netease.onmyoji")

    def test_minitouch_connection_uses_adb_path(self):
        try:
            from tasks.Script.config_device import PackageName
            from module.device.connection import Connection
            from module.device.connection_attr import ConnectionAttr
        except ImportError as exc:
            self.skipTest(f"optional OAS runtime dependencies unavailable: {exc}")

        device = SimpleNamespace(
            serial="localhost:1718",
            screenshot_method="MacBGR",
            control_method="minitouch",
            package_name=PackageName.AUTO,
        )
        config = SimpleNamespace(script=SimpleNamespace(device=device))
        with patch("module.device.connection.PlayCoverClient") as playcover_client, \
                patch.object(Connection, "detect_device", return_value=None) as detect_device, \
                patch.object(Connection, "adb_connect", return_value=None) as adb_connect, \
                patch.object(Connection, "detect_package", return_value=None), \
                patch.object(Connection, "adb", new_callable=PropertyMock) as adb, \
                patch.object(ConnectionAttr, "adb_client", new_callable=PropertyMock) as adb_client, \
                patch(
                    "module.device.connection_attr.deep_iter",
                    side_effect=[
                        [([], {"type": "oc", "value": True})] * 3,
                        [],
                    ],
                ):
            connection = Connection(config)

        playcover_client.assert_not_called()
        self.assertFalse(connection.is_playcover)
        detect_device.assert_called_once_with()
        adb_connect.assert_called_once_with("localhost:1718")
        adb_client.assert_called_once_with()
        adb.assert_called_once_with()

    def test_enum_values_exist_when_pydantic_is_available(self):
        try:
            from tasks.Script.config_device import ControlMethod, Device, ScreenshotMethod
        except ImportError as exc:
            self.skipTest(f"pydantic unavailable: {exc}")
        config = Device()
        self.assertEqual(config.serial, "auto")
        self.assertEqual(config.screenshot_method, ScreenshotMethod.AUTO)
        self.assertEqual(config.control_method, ControlMethod.MINITOUCH)
        self.assertIn("MacBGR", [item.value for item in ScreenshotMethod])
        self.assertIn("RGBA", [item.value for item in ScreenshotMethod])
        self.assertIn("MacSCK", [item.value for item in ScreenshotMethod])
        self.assertIn("MacPlayTools", [item.value for item in ControlMethod])


if __name__ == "__main__":
    unittest.main()

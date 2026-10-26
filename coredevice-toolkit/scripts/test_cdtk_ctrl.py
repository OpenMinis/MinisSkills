#!/usr/bin/env python3
"""cdtk-ctrl 坐标换算单元测试，无需设备与 pymobiledevice3：python3 test_cdtk_ctrl.py"""

import asyncio
import sys
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

STUBS = [
    "coredevice_session",
    "pymobiledevice3",
    "pymobiledevice3.remote",
    "pymobiledevice3.remote.core_device",
    "pymobiledevice3.remote.core_device.app_service",
    "pymobiledevice3.remote.core_device.device_info",
    "pymobiledevice3.remote.core_device.hid_service",
]

def load_cdtk_ctrl():
    path = Path(__file__).with_name("cdtk-ctrl")
    spec = spec_from_loader("cdtk_ctrl", SourceFileLoader("cdtk_ctrl", str(path)))
    module = module_from_spec(spec)
    with mock.patch.dict(sys.modules, {name: mock.MagicMock() for name in STUBS}):
        spec.loader.exec_module(module)
    return module

ctrl = load_cdtk_ctrl()

# 取自 iPhone (iOS 27.2) get_display_info() 的真实返回，已删去无关字段
DISPLAY_INFO = {
    "displays": [
        {"primary": True, "deviceName": "primary", "nativeSize": [1179.0, 2556.0], "pointScale": 3},
        {"primary": False, "deviceName": "external-0", "nativeSize": [0.0, 0.0], "pointScale": 1},
        {"primary": False, "deviceName": "wireless0", "nativeSize": [1184.0, 2560.0], "pointScale": 1},
    ]
}

class ScreenSizeTest(unittest.TestCase):
    def test_picks_primary_display(self):
        self.assertEqual(ctrl.screen_size(DISPLAY_INFO), (1179, 2556))

    def test_primary_not_first(self):
        info = {"displays": list(reversed(DISPLAY_INFO["displays"]))}
        self.assertEqual(ctrl.screen_size(info), (1179, 2556))

class ToHidTest(unittest.TestCase):
    SIZE = (1179, 2556)

    def test_corners_stay_in_range(self):
        self.assertEqual(ctrl.to_hid(0, 0, self.SIZE), (28, 13))
        self.assertEqual(ctrl.to_hid(1178, 2555, self.SIZE), (65507, 65522))

    def test_center(self):
        x, y = ctrl.to_hid(589, 1278, self.SIZE)
        self.assertAlmostEqual(x, 32768, delta=1)
        self.assertAlmostEqual(y, 32768, delta=13)

    def test_out_of_range(self):
        for x, y in [(-1, 0), (0, -1), (1179, 0), (0, 2556)]:
            with self.assertRaises(ValueError):
                ctrl.to_hid(x, y, self.SIZE)

    def test_monotonic(self):
        xs = [ctrl.to_hid(x, 0, self.SIZE)[0] for x in range(1179)]
        self.assertEqual(xs, sorted(set(xs)))

class RawHidTest(unittest.TestCase):
    ARGS = SimpleNamespace(hid=True)

    def test_passthrough(self):
        points = [(0, 0), (65535, 65535)]
        self.assertEqual(asyncio.run(ctrl.resolve_points(None, self.ARGS, points)), points)

    def test_out_of_range_exits(self):
        with self.assertRaises(SystemExit):
            asyncio.run(ctrl.resolve_points(None, self.ARGS, [(65536, 0)]))

if __name__ == "__main__":
    unittest.main()

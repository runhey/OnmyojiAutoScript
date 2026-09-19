from __future__ import annotations

"""GameUi 运行时公共导出层。"""

from tasks.GameUi.navigator import GameUi
from tasks.GameUi.page_definition import Page
from tasks.GameUi.session import NavigatorSession

__all__ = ["GameUi", "NavigatorSession", "Page"]


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device
    from tasks.GameUi.page import page_main

    c = Config("oas2")
    d = Device(c)
    game = GameUi(config=c, device=d)
    game.get_current_page()
    game.goto_page(page_main)

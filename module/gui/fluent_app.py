# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import sys
import os

from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import Qt, QObject
from pathlib import Path

from module.gui.utils import get_work_path
from module.gui.Bridge import bridge

class FluentApp():
    app = None
    engine = None

    def __init__(self):
        super().__init__()
        # 适配高分辨率、声明、设置Logo、设置软件名字
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.Round)
        FluentApp.app = QGuiApplication(sys.argv)
        QGuiApplication.setWindowIcon(QIcon(os.fspath(Path(__file__).resolve().parent / "res/logo.ico")))
        QGuiApplication.setApplicationName("oas")
        QGuiApplication.setOrganizationName("oas")


    def run(self):
        FluentApp.engine = QQmlApplicationEngine()
        # FluentApp.engine.rootContext().setContextProperty("bridge", bridge)
        FluentApp.engine.load(os.fspath(Path(get_work_path() / 'module' / 'gui' / 'qml' / 'app.qml')))
        if not FluentApp.engine.rootObjects():
            sys.exit(-1)
        sys.exit(FluentApp.app.exec())
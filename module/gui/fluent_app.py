# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import sys
import os

from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType
from PySide6.QtCore import Qt, QObject, QTranslator, QLocale, Slot
from pathlib import Path

from module.gui.utils import get_work_path
from module.gui.Bridge import bridge
from module.logger import logger

# import module.gui.qml_rcc
import module.gui.res_rcc

class FluentApp():
    app = None
    engine = None
    translator = None
    dpi = None

    def __init__(self):
        super().__init__()
        # 适配高分辨率、声明、设置Logo、设置软件名字
        # 后面的这三条失效了 使用 QGuiApplication.setHighDpiScaleFactorRoundingPolicy
        # https://blog.weimo.info/archives/602/
        # QGuiApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        # QGuiApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
        # QGuiApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
        os.putenv("QT_QUICK_CONTROLS_STYLE", "Basic")

        FluentApp.app = QGuiApplication(sys.argv)
        QGuiApplication.setWindowIcon(QIcon(os.fspath(Path(__file__).resolve().parent / "res/icon.ico")))
        QGuiApplication.setApplicationName("oas")
        QGuiApplication.setOrganizationName("oas")

        FluentApp.engine = QQmlApplicationEngine()
        FluentApp.engine.addImportPath(os.fspath(Path(__file__).resolve().parent))

        FluentApp.translator = Translator(engine=FluentApp.engine, app=FluentApp.app)
        FluentApp.dpi = DpiScale()
        self.set_context_property(context=FluentApp.translator, name='translator')
        self.set_context_property(context=FluentApp.dpi, name='dpi')

    @classmethod
    def run(cls):
        FluentApp.engine.load(os.fspath(Path(get_work_path() / 'module' / 'gui' / 'qml' / 'app.qml')))
        if not FluentApp.engine.rootObjects():
            sys.exit(-1)
        sys.exit(FluentApp.app.exec())

    @classmethod
    def set_context_property(cls, context, name: str) -> None:
        """
        设置上下文
        :param name:
        :param context:
        :return:
        """
        FluentApp.engine.rootContext().setContextProperty(name, context)



    def qml_register_type(self, Class, qml_class: str) -> None:
        """
        注册qml类型
        :param Class:
        :param qml_class:
        :return:
        """
        qmlRegisterType(Class, "Oas", 1, 0, qml_class)


class Translator(QObject):

    def __init__(self, engine, app) -> None:
        super(Translator, self).__init__()
        self._engine = engine
        self._app = app
        self.path_en_US = str((Path.cwd() / "module" / "config" / "i18n" / "en_US.qm").resolve())
        self.path_zh_CN = str((Path.cwd() / "module" / "config" / "i18n" / "zh_CN.qm").resolve())

        self.translator = QTranslator()

    @Slot(str)
    def set_language(self, language: str) -> None:
        """
        设置语言
        :param language:
        :return:
        """
        if language == "简体中文":
            if not self.translator.load(self.path_zh_CN):
                logger.error("load language 简体中文 failed!")
            QGuiApplication.installTranslator(self.translator)
            self._engine.retranslate()
            return

        if language == "English":
            if not self.translator.load(self.path_en_US):
                logger.error("load language English failed!")
            QGuiApplication.installTranslator(self.translator)
            self._engine.retranslate()
            return

class DpiScale(QObject):
    def __init__(self) -> None:
        super().__init__()

    @Slot(str)
    def set_dpi_scale(self, strategy: str) -> None:
        """
        设置dpi缩放
        :param strategy:
        :return:
        """
        match strategy:
            case "default": QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)  # 不缩放
            case "round": QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.Round)  # 设备像素比0.5及以上的，进行缩放
            case "floor": QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.Floor)  # 始终不缩放
            case "ceil": QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.Ceil)  # 始终缩放
            case "round_prefer_floor": QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.RoundPreferFloor)  # 设备像素比0.75及以上的，进行缩放
            case _: QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)




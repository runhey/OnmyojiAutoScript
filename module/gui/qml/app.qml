import QtQuick 2.12
import QtQuick.Controls 2.12
import QtQuick.Window 2.12
import FluentUI

Window {
    id:app
    Component.onCompleted: {
        FluApp.init(app)
        FluTheme.frameless = ("windows" === Qt.platform.os)
        FluTheme.darkMode = FluDarkMode.System
        FluApp.routes = {
            "/":"./module/gui/qml/MainWindow.qml",
        }
        FluApp.initialRoute = "/"
        FluApp.run()
    }
}

pragma Singleton

import QtQuick
import QtQuick.Controls
import FluentUI

QtObject {
    enum RunStatus {
        Error,
        Run,
        Free, //空闲
        Empty //不显示
    }

    property int displayMode : FluNavigationView.Compact
    property int runStatus: MainEvent.RunStatus.Empty
    property string menuTitle: "主页"
    property bool addOpen: false
}

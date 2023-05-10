import QtQuick
import QtQuick.Controls
import FluentUI

ToolTip {

    id:tool_tip

//    property var font: FluTextStyle.Body

    contentItem: FluText {
        text: tool_tip.text
//        font: tool_tip.font
        padding: 4
        wrapMode: Text.WrapAnywhere
    }

    background: Rectangle{
        anchors.fill: parent
        color: FluTheme.dark ? Qt.rgba(50/255,49/255,48/255,1) : Qt.rgba(1,1,1,1)
        radius: 5
        FluShadow{}
    }
}

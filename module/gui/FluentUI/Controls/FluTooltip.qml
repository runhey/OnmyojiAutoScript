import QtQuick
import QtQuick.Controls
import FluentUI

ToolTip {

    id:tool_tip

    contentItem: FluText {
        text: tool_tip.text
        font: tool_tip.font
        fontStyle: FluText.Body
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

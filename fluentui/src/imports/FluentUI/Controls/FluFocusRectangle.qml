import QtQuick
import QtQuick.Controls
import FluentUI

Item {

    property int radius: 4

    id:root
    anchors.fill: parent
    anchors.margins: -3
    Rectangle{
        width: root.width
        height: root.height
        anchors.centerIn: parent
        color: "#00000000"
        border.width: 3
        radius: root.radius
        border.color: FluTheme.dark ? Qt.rgba(1,1,1,1) : Qt.rgba(0,0,0,1)
        z: 65535
    }

}

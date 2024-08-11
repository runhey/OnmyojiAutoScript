import QtQuick
import QtQuick.Controls
import QtQuick.Window
import FluentUI

Rectangle {

    default property alias content: container.data
    property int paddings : 0
    property int leftPadding : 0
    property int rightPadding : 0
    property int topPadding : 0
    property int bottomPadding : 0

    radius: 4
    color: FluTheme.dark ? Window.active ?  Qt.rgba(38/255,44/255,54/255,1) : Qt.rgba(39/255,39/255,39/255,1) : Qt.rgba(251/255,251/255,253/255,1)
    border.color: FluTheme.dark ? Window.active ? Qt.rgba(55/255,55/255,55/255,1):Qt.rgba(45/255,45/255,45/255,1) : Qt.rgba(226/255,229/255,234/255,1)
    border.width: 1
    implicitHeight: height
    implicitWidth: width

    Behavior on color{
        ColorAnimation {
            duration: 300
        }
    }

    Behavior on border.color{
        ColorAnimation {
            duration: 300
        }
    }

    Item {
        id: container
        anchors.fill: parent
        anchors.leftMargin: Math.max(paddings,leftPadding)
        anchors.rightMargin: Math.max(paddings,rightPadding)
        anchors.topMargin: Math.max(paddings,topPadding)
        anchors.bottomMargin: Math.max(paddings,bottomPadding)
    }

}

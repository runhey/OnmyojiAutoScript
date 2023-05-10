import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import FluentUI

FluWindow {

    id:window
    title:"Standard"
    width: 500
    height: 600
    minimumWidth: 500
    minimumHeight: 600
    maximumWidth: 500
    maximumHeight: 600
    launchMode: FluWindow.Standard

    FluAppBar{
        id:appbar
        title:"Standard"
        width:parent.width
    }

    FluText{
        anchors.centerIn: parent
        text:"我是一个Standard模式的窗口，每次我都会创建一个新的窗口"
    }

}

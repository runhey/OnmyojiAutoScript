import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import FluentUI

FluWindow {

    id:window
    title:"SingleInstance"
    width: 500
    height: 600
    minimumWidth: 500
    minimumHeight: 600
    maximumWidth: 500
    maximumHeight: 600
    launchMode: FluWindow.SingleInstance

    FluAppBar{
        id:appbar
        title:"SingleInstance"
        width:parent.width
    }

    FluTextBox{
        anchors{
            top:parent.top
            topMargin:60
            horizontalCenter: parent.horizontalCenter
        }
    }

    FluText{
        wrapMode: Text.WrapAnywhere
        anchors{
            left: parent.left
            right: parent.right
            leftMargin: 20
            rightMargin: 20
            verticalCenter: parent.verticalCenter
        }
        text:"我是一个SingleInstance模式的窗口，如果我存在，我会销毁之前的窗口，并创建一个新窗口"
    }

}

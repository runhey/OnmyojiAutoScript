import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls
import FluentUI
import "../component"

FluScrollablePage{

    title:"InfoBar"
    leftPadding:10
    rightPadding:10
    bottomPadding:20
    spacing: 0

    FluArea{
        Layout.fillWidth: true
        Layout.topMargin: 20
        height: 200
        paddings: 10
        ColumnLayout{
            spacing: 14
            anchors{
                verticalCenter: parent.verticalCenter
                left: parent.left
            }
            FluButton{
                text:"Info"
                onClicked: {
                    showInfo("这是一个Info样式的InfoBar")
                }
            }
            FluButton{
                text:"Warning"
                onClicked: {
                    showWarning("这是一个Warning样式的InfoBar")
                }
            }
            FluButton{
                text:"Error"
                onClicked: {
                    showError("这是一个Error样式的InfoBar")
                }
            }
            FluButton{
                text:"Success"
                onClicked: {
                    showSuccess("这是一个Success样式的InfoBar这是一个Success样式的InfoBar")
                }
            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'showInfo("这是一个Info样式的InfoBar")

showWarning("这是一个Warning样式的InfoBar")

showError("这是一个Error样式的InfoBar")

showSuccess("这是一个Success样式的InfoBar这是一个Success样式的InfoBar")'
    }
}

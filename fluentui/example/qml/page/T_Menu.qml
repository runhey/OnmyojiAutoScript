import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls
import FluentUI
import "../component"

FluScrollablePage{

    title:"Menu"
    leftPadding:10
    rightPadding:10
    bottomPadding:20
    spacing: 0

    FluArea{
        Layout.fillWidth: true
        height: 100
        paddings: 10
        Layout.topMargin: 20
        Column{
            id:layout_column
            spacing: 15
            anchors{
                verticalCenter: parent.verticalCenter
                left:parent.left
            }

            FluButton{
                text:"左击菜单"
                Layout.topMargin: 20
                onClicked:{
                    menu.popup()
                }
            }

            FluButton{
                text:"右击菜单"
                Layout.topMargin: 20
                onClicked: {
                    showSuccess("请按鼠标右击")
                }
                MouseArea{
                    anchors.fill: parent
                    acceptedButtons: Qt.RightButton
                    onClicked: {
                        menu.popup()
                    }
                }
            }
        }
    }

    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluMenu{
    id:menu
    FluMenuItem:{
        text:"删除"
        onClicked: {
            showError("删除")
        }
    }
    FluMenuItem:{
        text:"修改"
        onClicked: {
            showInfo"修改")
        }
    }
}
menu.popup()
'
    }

    FluMenu{
        id:menu
        FluMenuItem{
            text:"删除"
            onClicked: {
                showError("删除")
            }
        }
        FluMenuItem{
            text:"修改"
            onClicked: {
                showInfo("修改")
            }
        }
    }

}

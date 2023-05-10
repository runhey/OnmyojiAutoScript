import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import FluentUI
import "../component"

FluScrollablePage{

    title:"Tooltip"
    leftPadding:10
    rightPadding:10
    bottomPadding:20
    spacing: 0

    FluText{
        Layout.topMargin: 20
        text:"鼠标悬停不动，弹出Tooltip"
    }

    FluArea{
        Layout.fillWidth: true
        Layout.topMargin: 20
        height: 68
        paddings: 10

        Column{
            spacing: 5
            anchors{
                verticalCenter: parent.verticalCenter
                left: parent.left
            }
            FluText{
                text:"FluIconButton的text属性自带Tooltip效果"
            }
            FluIconButton{
                iconSource:FluentIcons.ChromeCloseContrast
                iconSize: 15
                text:"删除"
                onClicked:{
                    showSuccess("点击IconButton")
                }
            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluIconButton{
    iconSource:FluentIcons.ChromeCloseContrast
    iconSize: 15
    text:"删除"
    onClicked:{
        showSuccess("点击IconButton")
    }
}
'
    }

    FluArea{
        Layout.fillWidth: true
        Layout.topMargin: 20
        height: 68
        paddings: 10

        Column{
            spacing: 5
            anchors{
                verticalCenter: parent.verticalCenter
                left: parent.left
            }
            FluText{
                text:"给一个Button添加Tooltip效果"
            }
            FluButton{
                id:button_1
                text:"删除"
                onClicked:{
                    showSuccess("点击一个Button")
                }
                FluTooltip{
                    visible: button_1.hovered
                    text:button_1.text
                    delay: 1000
                }
            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluButton{
    id:button_1
    text:"删除"
    FluTooltip{
        visible: button_1.hovered
        text:button_1.text
        delay: 1000
    }
    onClicked:{
        showSuccess("点击一个Button")
    }
}'
    }


}

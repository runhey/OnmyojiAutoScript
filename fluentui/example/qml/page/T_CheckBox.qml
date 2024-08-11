import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls
import FluentUI
import "../component"

FluScrollablePage{

    title:"CheckBox"
    leftPadding:10
    rightPadding:10
    bottomPadding:20
    spacing: 0

    FluArea{
        Layout.fillWidth: true
        height: 68
        paddings: 10
        Layout.topMargin: 20
        Row{
            spacing: 30
            anchors.verticalCenter: parent.verticalCenter
            FluCheckBox{
            }
            FluCheckBox{
                text:"Text"
            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluCheckBox{
    text:"Text"
}'
    }

}

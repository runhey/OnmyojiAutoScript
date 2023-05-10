import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import FluentUI
import "../component"

FluScrollablePage{

    title:"TimePicker"
    leftPadding:10
    rightPadding:10
    bottomPadding:20
    spacing: 0

    FluArea{
        Layout.fillWidth: true
        Layout.topMargin: 20
        height: 80
        paddings: 10
        ColumnLayout{
            anchors{
                verticalCenter: parent.verticalCenter
                left: parent.left
            }
            FluText{
                text:"showYear=true"
            }
            FluDatePicker{
            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluDatePicker{

}'
    }

    FluArea{
        Layout.fillWidth: true
        Layout.topMargin: 20
        height: 80
        paddings: 10
        ColumnLayout{
            anchors{
                verticalCenter: parent.verticalCenter
                left: parent.left
            }
            FluText{
                text:"showYear=false"
            }

            FluDatePicker{
                showYear:false

            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluDatePicker{
    showYear:false
}'
    }

}

import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls
import "../component"
import FluentUI

FluScrollablePage{

    title:"Slider"
    leftPadding:10
    rightPadding:10
    bottomPadding:20
    spacing: 0

    FluArea{
        Layout.fillWidth: true
        height: 100
        paddings: 10
        Layout.topMargin: 20
        FluSlider{
            value: 50
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluSlider{
    value:50
}'
    }


    FluArea{
        Layout.fillWidth: true
        height: 200
        paddings: 10
        Layout.topMargin: 20
        FluSlider{
            value: 50
            vertical:true
            anchors.left: parent.left
            anchors.leftMargin: 20
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluSlider{
    vertical:true
    value:50
}'
    }


}

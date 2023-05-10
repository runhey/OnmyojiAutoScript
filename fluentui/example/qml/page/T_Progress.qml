import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls
import FluentUI
import "../component"

FluScrollablePage{

    title:"Progress"
    leftPadding:10
    rightPadding:10
    bottomPadding:20
    spacing: 0

    FluArea{
        Layout.fillWidth: true
        Layout.topMargin: 20
        height: 260
        paddings: 10
        ColumnLayout{
            spacing: 20
            anchors{
                verticalCenter: parent.verticalCenter
                left: parent.left
            }
            FluProgressBar{
            }
            FluProgressRing{
            }
            FluProgressBar{
                id:progress_bar
                indeterminate: false
            }
            FluProgressRing{
                id:progress_ring
                indeterminate: false
            }
            FluSlider{
                value:50
                onValueChanged:{
                    progress_bar.progress = value/100
                    progress_ring.progress = value/100
                }
            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluProgressBar{

}

FluProgressRing{

}

FluProgressBar{
    indeterminate: false
}

FluProgressRing{
    indeterminate: false
}'
    }



}

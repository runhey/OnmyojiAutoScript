import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls
import FluentUI
import "../component"

FluScrollablePage{

    title:"RatingControl"
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
            spacing: 10
            anchors.verticalCenter: parent.verticalCenter
            FluRatingControl{

            }
            FluRatingControl{
                number:10
            }
        }

    }

    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluRatingControl{

}'
    }


}

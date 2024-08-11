import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls
import FluentUI

Item {

    property alias title: text_title.text
    default property alias content: container.data
    property int leftPadding: 0
    property int topPadding: 0
    property int rightPadding: 0
    property int bottomPadding: 0

    id:control

    FluText{
        id:text_title
        font: FluTextStyle.TitleLarge
        anchors{
            top: parent.top
            topMargin: control.topPadding
            left: parent.left
            right: parent.right
            leftMargin: control.leftPadding
            rightMargin: control.rightPadding
        }
    }

    Item{
        clip: true
        id:container
        anchors{
            left: parent.left
            right: parent.right
            top: text_title.bottom
            bottom: parent.bottom
            leftMargin: control.leftPadding
            rightMargin: control.rightPadding
            bottomMargin: control.bottomPadding
        }
    }

}

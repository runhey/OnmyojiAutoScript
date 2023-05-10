import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic
import FluentUI

Item{

    property bool vertical: false
    default property alias content : swipe.contentData
    property alias currentIndex: swipe.currentIndex

    id:control
    width: 400
    height: 300
    implicitWidth: width
    implicitHeight: height

    QtObject{
        id:d
        property bool flag: true
    }

    MouseArea{
        anchors.fill: parent
        preventStealing: true
        onWheel:
            (wheel)=>{
                if(!d.flag)
                return
                if (wheel.angleDelta.y > 0){
                    btn_start.clicked()
                }else{
                    btn_end.clicked()
                }
                d.flag = false
                timer.restart()
            }
    }

    Timer{
        id:timer
        interval: 250
        onTriggered: {
            d.flag = true
        }
    }

    SwipeView {
        id:swipe
        clip: true
        interactive: false
        orientation:control.vertical ? Qt.Vertical : Qt.Horizontal
        anchors.fill: parent
    }

    Button{
        id:btn_start
        height: vertical ? 20 : 40
        width: vertical ? 40 : 20
        anchors{
            left: vertical ? undefined : parent.left
            leftMargin: vertical ? undefined : 2
            verticalCenter: vertical ? undefined : parent.verticalCenter
            horizontalCenter: !vertical ? undefined : parent.horizontalCenter
            top: !vertical ? undefined :parent.top
            topMargin: !vertical ? undefined :2
        }
        background: Rectangle{
            radius: 4
            color:FluTheme.dark ? Qt.rgba(45/255,45/255,45/255,0.97) : Qt.rgba(237/255,237/255,237/255,0.97)
        }
        contentItem:FluIcon{
            iconSource: vertical ? FluentIcons.CaretUpSolid8 : FluentIcons.CaretLeftSolid8
            width: 10
            height: 10
            iconSize: 10
            iconColor: btn_start.hovered ? FluColors.Grey220  :  FluColors.Grey120
            anchors.centerIn: parent
        }
        visible: swipe.currentIndex !==0
        onClicked: {
            swipe.currentIndex = Math.max(swipe.currentIndex - 1, 0)
        }
    }

    Button{
        id:btn_end
        height: vertical ? 20 : 40
        width: vertical ? 40 : 20
        anchors{
            right: vertical ? undefined : parent.right
            rightMargin: vertical ? undefined : 2
            verticalCenter: vertical ? undefined : parent.verticalCenter
            horizontalCenter: !vertical ? undefined : parent.horizontalCenter
            bottom: !vertical ? undefined :parent.bottom
            bottomMargin: !vertical ? undefined :2
        }
        background: Rectangle{
            radius: 4
            color:FluTheme.dark ? Qt.rgba(45/255,45/255,45/255,0.97) : Qt.rgba(237/255,237/255,237/255,0.97)
        }
        visible: swipe.currentIndex !== swipe.count - 1
        contentItem:FluIcon{
            iconSource: vertical ? FluentIcons.CaretDownSolid8 : FluentIcons.CaretRightSolid8
            width: 10
            height: 10
            iconSize: 10
            iconColor: btn_end.hovered ? FluColors.Grey220  :  FluColors.Grey120
            anchors.centerIn: parent
        }
        onClicked: {
            swipe.currentIndex = Math.min(swipe.currentIndex + 1,swipe.count-1)
        }
    }

}


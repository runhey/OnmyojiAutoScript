import QtQuick
import QtQuick.Controls
import FluentUI

ScrollBar {

    property color handleNormalColor: Qt.rgba(134/255,134/255,134/255,1)
    property color handleHoverColor: Qt.lighter(handleNormalColor)
    property color handlePressColor: Qt.darker(handleNormalColor)
    property bool expand: false

    id: control
    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding)

    visible: control.policy !== ScrollBar.AlwaysOff
    minimumSize: 0.3
    topPadding:{
        if(vertical){
            if(expand)
                return 15
            return 2
        }else{
            if(expand){
                return 2
            }
            return 4
        }
    }
    bottomPadding:{
        if(vertical){
            if(expand)
                return 15
            return 2
        }else{
            if(expand){
                return 2
            }
            return 4
        }
    }
    leftPadding:{
        if(vertical){
            if(expand){
                return 2
            }
            return 4
        }else{
            if(expand)
                return 15
            return 2
        }
    }
    rightPadding:{
        if(vertical){
            if(expand){
                return 2
            }
            return 4
        }else{
            if(expand)
                return 15
            return 2
        }
    }
    Behavior on topPadding {
        NumberAnimation{
            duration: 150
        }
    }
    Behavior on bottomPadding {
        NumberAnimation{
            duration: 150
        }
    }
    Behavior on leftPadding {
        NumberAnimation{
            duration: 150
        }
    }
    Behavior on rightPadding {
        NumberAnimation{
            duration: 150
        }
    }
    contentItem: Rectangle {
        id:item_react
        implicitWidth: expand ? 8 : 2
        implicitHeight:  expand ? 8 : 2
        radius: width / 2
        color: control.pressed?handlePressColor:control.hovered?handleHoverColor:handleNormalColor
        opacity:(control.policy === ScrollBar.AlwaysOn || control.size < 1.0)?1.0:0.0
    }
    background:  Rectangle{
        radius: 5
        color: {
            if(expand && item_react.opacity){
                if(FluTheme.dark){
                    return Qt.rgba(0,0,0,1)
                }
                return Qt.rgba(1,1,1,1)
            }
            return Qt.rgba(0,0,0,0)
        }
        MouseArea{
            id:mouse_item
            hoverEnabled: true
            anchors.fill: parent
            onEntered: {
                timer.restart()
            }
            onExited: {
                timer.restart()
            }
        }
    }
    Timer{
        id:timer
        interval: 800
        onTriggered: {
            expand = mouse_item.containsMouse || btn_top.hovered || btn_bottom.hovered || btn_left.hovered || btn_right.hovered
        }
    }
    Behavior on implicitWidth {
        NumberAnimation{
            duration: 150
        }
    }

    FluIconButton{
        id:btn_top
        iconSource: FluentIcons.CaretSolidUp
        anchors.horizontalCenter: parent.horizontalCenter
        width:10
        height:10
        z:100
        iconColor: hovered ? FluColors.Black : FluColors.Grey120
        iconSize: 8
        anchors.top: parent.top
        anchors.topMargin: 4
        visible:vertical && expand && item_react.opacity
        onClicked:{
            decrease()
        }
    }
    FluIconButton{
        id:btn_bottom
        iconSource: FluentIcons.CaretSolidDown
        visible:vertical && expand && item_react.opacity
        width:10
        height:10
        iconSize: 8
        iconColor: hovered ? FluColors.Black : FluColors.Grey120
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 4
        onClicked:{
            increase()
        }
    }
    FluIconButton{
        id:btn_left
        iconSource: FluentIcons.CaretSolidLeft
        visible:!vertical && expand && item_react.opacity
        width:10
        height:10
        iconSize: 8
        iconColor: hovered ? FluColors.Black : FluColors.Grey120
        anchors.leftMargin: 4
        anchors.verticalCenter: parent.verticalCenter
        anchors.left: parent.left
        onClicked:{
            decrease()
        }
    }
    FluIconButton{
        id:btn_right
        iconSource: FluentIcons.CaretSolidRight
        visible:!vertical && expand && item_react.opacity
        width:10
        height:10
        iconSize: 8
        iconColor: hovered ? FluColors.Black : FluColors.Grey120
        anchors.rightMargin: 4
        anchors.verticalCenter: parent.verticalCenter
        anchors.right: parent.right
        onClicked:{
            increase()
        }
    }

}

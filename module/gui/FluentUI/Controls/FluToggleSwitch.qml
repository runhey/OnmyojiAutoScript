import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic
import QtQuick.Layouts
import FluentUI

Button {

    property bool selected: false
    property var clickFunc

    id: control
    height: 20
    implicitHeight: height
    focusPolicy:Qt.TabFocus
    Keys.onSpacePressed: control.visualFocus&&clicked()
    onClicked: {
        if(clickFunc){
            clickFunc()
            return
        }
        selected = !selected
    }

    contentItem: Item{}

    background : RowLayout{
        spacing: 0
        Rectangle {
            id:control_backgound
            width: 40
            height: control.height
            radius: height / 2
            FluFocusRectangle{
                visible: control.visualFocus
                radius: 20
            }
            color: {
                if(FluTheme.dark){
                    if(selected){
                        return FluTheme.primaryColor.dark
                    }
                    if(hovered){
                        return "#3E3E3C"
                    }
                    return "#323232"
                }else{
                    if(selected){
                        return FluTheme.primaryColor.dark
                    }
                    if(hovered){
                        return "#F4F4F4"
                    }
                    return  "#FFFFFF"
                }
            }
            border.width: 1
            border.color: selected ? Qt.lighter(FluTheme.primaryColor.dark,1.2) : "#666666"
            Rectangle {
                width: pressed ? 28 : 20
                anchors{
                    left: selected ? undefined : parent.left
                    leftMargin: selected ? 20 : 0
                    right: selected ? parent.right : undefined
                    rightMargin: selected ? 0: 20
                }
                height: 20
                radius: 10
                scale: hovered ? 7/10 : 6/10
                anchors.verticalCenter: parent.verticalCenter
                color: selected ? "#FFFFFF" : "#666666"
                Behavior on anchors.leftMargin  {
                    NumberAnimation {
                        duration: 167
                        easing.type: Easing.BezierSpline
                        easing.bezierCurve: [ 1, 0, 0, 0 ]
                    }
                }
                Behavior on anchors.rightMargin  {
                    NumberAnimation {
                        duration: 167
                        easing.type: Easing.BezierSpline
                        easing.bezierCurve: [ 1, 0, 0, 0 ]
                    }
                }
                Behavior on width {
                    NumberAnimation {
                        duration: 167
                        easing.type: Easing.BezierSpline
                        easing.bezierCurve: [ 1, 0, 0, 0 ]
                    }
                }
                Behavior on scale {
                    NumberAnimation {
                        duration: 167
                        easing.type: Easing.BezierSpline
                        easing.bezierCurve: [ 1, 0, 0, 0 ]
                    }
                }
            }
        }
        FluText{
            text: control.text
            Layout.leftMargin: 5
            visible: text !== ""
        }
    }
}

import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic
import QtQuick.Layouts
import FluentUI

Button {

    property bool selected: false
    property bool disabled: false

    id:control
    enabled: !disabled
    focusPolicy:Qt.TabFocus
    padding:0
    background: Item{
        FluFocusRectangle{
            visible: control.visualFocus
        }
    }
    Keys.onSpacePressed: control.visualFocus&&clicked()
    contentItem: RowLayout{
        Rectangle{
            id:rect_check
            width: 20
            height: 20
            radius: 10
            border.width: {
                if(selected&&disabled){
                    return 3
                }
                if(pressed){
                    if(selected){
                        return 5
                    }
                    return 1
                }
                if(hovered){
                    if(selected){
                        return 3
                    }
                    return 1
                }
                return selected ? 5 : 1
            }
            Behavior on border.width {
                NumberAnimation{
                    duration: 167
                    easing.type: Easing.BezierSpline
                    easing.bezierCurve: [ 0, 0, 0, 1 ]
                }
            }
            border.color: {
                if(disabled){
                    if(FluTheme.dark){
                        return Qt.rgba(82/255,82/255,82/255,1)
                    }else{
                        return Qt.rgba(198/255,198/255,198/255,1)
                    }
                }
                if(selected){
                    if(FluTheme.dark){
                        return FluTheme.primaryColor.lighter
                    }else{

                        return FluTheme.primaryColor.dark
                    }
                }else{
                    if(FluTheme.dark){
                        return Qt.rgba(161/255,161/255,161/255,1)
                    }else{

                        return Qt.rgba(141/255,141/255,141/255,1)
                    }
                }
            }
            color:{
                if(disabled&&selected){
                    return Qt.rgba(159/255,159/255,159/255,1)
                }
                if(FluTheme.dark){
                    if(hovered){
                        return Qt.rgba(43/255,43/255,43/255,1)
                    }
                    return Qt.rgba(50/255,50/255,50/255,1)
                }else{
                    if(hovered){
                        if(selected){
                            return Qt.rgba(1,1,1,1)
                        }
                        return Qt.rgba(222/255,222/255,222/255,1)
                    }
                    return Qt.rgba(1,1,1,1)
                }
            }
        }
        FluText{
            text: control.text
            Layout.alignment: Qt.AlignVCenter
        }
    }
}


import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic
import QtQuick.Window
import FluentUI

Button {

    property bool disabled: false
    property color normalColor: FluTheme.dark ? Qt.rgba(62/255,62/255,62/255,1) : Qt.rgba(254/255,254/255,254/255,1)
    property color hoverColor: FluTheme.dark ? Qt.rgba(68/255,68/255,68/255,1) : Qt.rgba(251/255,251/255,251/255,1)
    property color disableColor: FluTheme.dark ? Qt.rgba(59/255,59/255,59/255,1) : Qt.rgba(252/255,252/255,252/255,1)
    property var window : Window.window
    property alias items: menu.content

    id: control
    topPadding:5
    bottomPadding:5
    leftPadding:15
    rightPadding:35
    enabled: !disabled
    focusPolicy:Qt.TabFocus

    Keys.onSpacePressed: control.visualFocus&&clicked()

    background: Rectangle{
        border.color: FluTheme.dark ? "#505050" : "#DFDFDF"
        border.width: 1
        radius: 4
        FluFocusRectangle{
            visible: control.visualFocus
            radius:8
        }
        color:{
            if(disabled){
                return disableColor
            }
            return hovered ? hoverColor :normalColor
        }
        FluIcon{
            iconSource:FluentIcons.ChevronDown
            iconSize: 15
            anchors{
                right: parent.right
                rightMargin: 10
                verticalCenter: parent.verticalCenter
            }
            iconColor:title.color
        }

    }
    contentItem: FluText {
        id:title
        text: control.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        color: {
            if(FluTheme.dark){
                if(disabled){
                    return Qt.rgba(131/255,131/255,131/255,1)
                }
                if(pressed){
                    return Qt.rgba(162/255,162/255,162/255,1)
                }
                return Qt.rgba(1,1,1,1)
            }else{
                if(disabled){
                    return Qt.rgba(160/255,160/255,160/255,1)
                }
                if(pressed){
                    return Qt.rgba(96/255,96/255,96/255,1)
                }
                return Qt.rgba(0,0,0,1)
            }
        }
    }

    onClicked: {
        var pos = control.mapToItem(null, 0, 0)
        var containerHeight = menu.getContainerHeight()
        if(window.height>pos.y+control.height+containerHeight){
            menu.y = control.height
        }else if(pos.y>containerHeight){
            menu.y = -containerHeight
        }else{
            menu.y = window.height-(pos.y+containerHeight)
        }
        menu.open()
    }

    FluMenu{
        id:menu
        width: control.width
    }

}

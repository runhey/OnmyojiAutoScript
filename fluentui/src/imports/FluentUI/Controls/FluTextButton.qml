import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic
import FluentUI

Button {

    property bool disabled: false
    property color normalColor: FluTheme.dark ? FluTheme.primaryColor.lighter : FluTheme.primaryColor.dark
    property color hoverColor: FluTheme.dark ? Qt.darker(normalColor,1.15) : Qt.lighter(normalColor,1.15)
    property color pressedColor: FluTheme.dark ? Qt.darker(normalColor,1.3) : Qt.lighter(normalColor,1.3)
    property color disableColor: FluTheme.dark ? Qt.rgba(82/255,82/255,82/255,1) : Qt.rgba(199/255,199/255,199/255,1)
    property bool textBold: true

    id: control
    topPadding:0
    bottomPadding:0
    leftPadding:0
    rightPadding:0
    enabled: !disabled
    focusPolicy:Qt.TabFocus

    Keys.onSpacePressed: control.visualFocus&&clicked()

    background: Item{
        FluFocusRectangle{
            visible: control.visualFocus
            radius:8
        }
    }
    contentItem: FluText {
        text: control.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        font.bold: control.textBold
        color: {
            color:{
                if(disabled){
                    return disableColor
                }
                if(pressed){
                    return pressedColor
                }
                return hovered ? hoverColor :normalColor
            }
        }
    }
}

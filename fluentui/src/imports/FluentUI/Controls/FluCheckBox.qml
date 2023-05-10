import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic
import QtQuick.Layouts
import FluentUI

Button {

    property bool selected: false
    property var clickFunc
    property bool disabled: false
    property color borderNormalColor: FluTheme.dark ? Qt.rgba(160/255,160/255,160/255,1) : Qt.rgba(136/255,136/255,136/255,1)
    property color borderSelectedColor: FluTheme.dark ? FluTheme.primaryColor.lighter : FluTheme.primaryColor.dark
    property color borderHoverColor: FluTheme.dark ? Qt.rgba(167/255,167/255,167/255,1) : Qt.rgba(135/255,135/255,135/255,1)
    property color borderDisableColor: FluTheme.dark ? Qt.rgba(82/255,82/255,82/255,1) : Qt.rgba(199/255,199/255,199/255,1)
    property color borderPressedColor: FluTheme.dark ? Qt.rgba(90/255,90/255,90/255,1) : Qt.rgba(191/255,191/255,191/255,1)

    property color normalColor: FluTheme.dark ? Qt.rgba(45/255,45/255,45/255,1) : Qt.rgba(247/255,247/255,247/255,1)
    property color selectedColor: FluTheme.dark ? FluTheme.primaryColor.lighter : FluTheme.primaryColor.dark
    property color hoverColor: FluTheme.dark ? Qt.rgba(72/255,72/255,72/255,1) : Qt.rgba(236/255,236/255,236/255,1)
    property color selectedHoverColor: FluTheme.dark ? Qt.darker(selectedColor,1.15) : Qt.lighter(selectedColor,1.15)
    property color selectedPreesedColor: FluTheme.dark ? Qt.darker(selectedColor,1.3) : Qt.lighter(selectedColor,1.3)
    property color selectedDisableColor: FluTheme.dark ? Qt.rgba(82/255,82/255,82/255,1) : Qt.rgba(199/255,199/255,199/255,1)
    property color disableColor: FluTheme.dark ? Qt.rgba(50/255,50/255,50/255,1) : Qt.rgba(253/255,253/255,253/255,1)

    id:control
    enabled: !disabled
    focusPolicy:Qt.TabFocus
    Keys.onSpacePressed: control.visualFocus&&clicked()
    padding:0
    onClicked: {
        if(disabled){
            return
        }
        if(clickFunc){
            clickFunc()
            return
        }
        selected = !selected
    }
    background: Item{
        FluFocusRectangle{
            visible: control.visualFocus
        }
    }
    contentItem: RowLayout{
        spacing: 4
        Rectangle{
            width: 20
            height: 20
            radius: 4
            border.color: {
                if(disabled){
                    return borderDisableColor
                }
                if(selected){
                    return borderSelectedColor
                }
                if(pressed){
                    return borderPressedColor
                }
                if(hovered){
                    return borderHoverColor
                }
                return borderNormalColor
            }
            border.width: 1
            color: {
                if(selected){
                    if(disabled){
                        return selectedDisableColor
                    }
                    if(pressed){
                        return selectedPreesedColor
                    }
                    if(hovered){
                        return selectedHoverColor
                    }
                    return selectedColor
                }
                if(hovered){
                    return hoverColor
                }
                return normalColor
            }
            Behavior on color {
                ColorAnimation{
                    duration: 150
                }
            }
            FluIcon {
                anchors.centerIn: parent
                iconSource: FluentIcons.AcceptMedium
                iconSize: 15
                visible: selected
                iconColor: FluTheme.dark ? Qt.rgba(0,0,0,1) : Qt.rgba(1,1,1,1)
                Behavior on visible {
                    NumberAnimation{
                        duration: 150
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

import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic
import FluentUI

TextField{

    property bool disabled: false
    property int iconSource: 0
    property color normalColor: FluTheme.dark ?  Qt.rgba(255/255,255/255,255/255,1) : Qt.rgba(27/255,27/255,27/255,1)
    property color disableColor: FluTheme.dark ? Qt.rgba(131/255,131/255,131/255,1) : Qt.rgba(160/255,160/255,160/255,1)
    property color placeholderNormalColor: FluTheme.dark ? Qt.rgba(210/255,210/255,210/255,1) : Qt.rgba(96/255,96/255,96/255,1)
    property color placeholderFocusColor: FluTheme.dark ? Qt.rgba(152/255,152/255,152/255,1) : Qt.rgba(141/255,141/255,141/255,1)
    property color placeholderDisableColor: FluTheme.dark ? Qt.rgba(131/255,131/255,131/255,1) : Qt.rgba(160/255,160/255,160/255,1)

    id:control
    width: 300
    enabled: !disabled
    color: {
        if(disabled){
            return disableColor
        }
        return normalColor
    }
    font:FluTextStyle.Body
    echoMode:btn_reveal.pressed ? TextField.Normal : TextField.Password
    renderType: FluTheme.nativeText ? Text.NativeRendering : Text.QtRendering
    selectionColor: FluTheme.primaryColor.lightest
    placeholderTextColor: {
        if(disabled){
            return placeholderDisableColor
        }
        if(focus){
            return placeholderFocusColor
        }
        return placeholderNormalColor
    }
    selectByMouse: true
    rightPadding: icon_end.visible ? 50 : 30
    background: FluTextBoxBackground{
        inputItem: control
        FluIcon{
            id:icon_end
            iconSource: control.iconSource
            iconSize: 15
            opacity: 0.5
            visible: control.iconSource != 0
            anchors{
                verticalCenter: parent.verticalCenter
                right: parent.right
                rightMargin: 5
            }
        }
    }
    FluIconButton{
        id:btn_reveal
        iconSource:FluentIcons.RevealPasswordMedium
        iconSize: 10
        width: 20
        height: 20
        opacity: 0.5
        visible: control.text !== ""
        anchors{
            verticalCenter: parent.verticalCenter
            right: parent.right
            rightMargin: icon_end.visible ? 25 : 5
        }
    }
    TapHandler {
        acceptedButtons: Qt.RightButton
        onTapped: control.echoMode !== TextInput.Password && menu.popup()
    }
    FluTextBoxMenu{
        id:menu
        inputItem: control
    }

}


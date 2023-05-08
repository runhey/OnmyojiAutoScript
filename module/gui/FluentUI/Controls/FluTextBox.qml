import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic
import FluentUI

TextField{

    property int fontStyle: FluText.Body
    property int pixelSize : FluTheme.textSize
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
    font.bold: {
        switch (fontStyle) {
        case FluText.Display:
            return true
        case FluText.TitleLarge:
            return true
        case FluText.Title:
            return true
        case FluText.SubTitle:
            return true
        case FluText.BodyStrong:
            return true
        case FluText.Body:
            return false
        case FluText.Caption:
            return false
        default:
            return false
        }
    }
    font.pixelSize: {
        switch (fontStyle) {
        case FluText.Display:
            return text.pixelSize * 4.857
        case FluText.TitleLarge:
            return text.pixelSize * 2.857
        case FluText.Title:
            return text.pixelSize * 2
        case FluText.SubTitle:
            return text.pixelSize * 1.428
        case FluText.Body:
            return text.pixelSize * 1.0
        case FluText.BodyStrong:
            return text.pixelSize * 1.0
        case FluText.Caption:
            return text.pixelSize * 0.857
        default:
            return text.pixelSize * 1.0
        }
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
        iconSource:FluentIcons.ChromeClose
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
        onClicked:{
            control.text = ""
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


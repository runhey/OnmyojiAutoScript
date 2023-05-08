import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic
import FluentUI

TextArea{

    property int fontStyle: FluText.Body
    property int pixelSize : FluTheme.textSize
    property bool disabled: false
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
    wrapMode: Text.WrapAnywhere
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
    background: FluTextBoxBackground{ inputItem: control }
    TapHandler {
        acceptedButtons: Qt.RightButton
        onTapped: control.echoMode !== TextInput.Password && menu.popup()
    }
    FluTextBoxMenu{
        id:menu
        inputItem: control
    }

}

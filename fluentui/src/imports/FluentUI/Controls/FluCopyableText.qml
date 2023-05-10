import QtQuick
import QtQuick.Controls
import FluentUI

TextField {

    property color textColor: FluTheme.dark ? FluColors.White : FluColors.Grey220

    id:control
    color: textColor
    readOnly: true
    renderType: FluTheme.nativeText ? Text.NativeRendering : Text.QtRendering
    padding: 0
    leftPadding: 0
    rightPadding: 0
    topPadding: 0
    bottomPadding: 0
    selectionColor: FluTheme.primaryColor.lightest
    TextMetrics {
        id: text_metrics
        font:control.font
        text: control.text
    }
    background: Item{
        implicitWidth: text_metrics.width+10
        implicitHeight: text_metrics.height
    }
    font:FluTextStyle.Body
    TapHandler {
        acceptedButtons: Qt.RightButton
        onTapped: control.echoMode !== TextInput.Password && menu.popup()
    }
    FluTextBoxMenu{
        id:menu
        inputItem: control
    }

}

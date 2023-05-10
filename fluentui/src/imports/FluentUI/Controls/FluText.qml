import QtQuick
import QtQuick.Controls
import FluentUI

Text {

    property color textColor: FluTheme.dark ? FluColors.White : FluColors.Grey220

    id:text
    color: textColor
    renderType: FluTheme.nativeText ? Text.NativeRendering : Text.QtRendering
    font: FluTextStyle.Body

}

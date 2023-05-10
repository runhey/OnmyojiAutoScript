import QtQuick
import QtQuick.Controls
import FluentUI

Text {

    property int iconSource
    property int iconSize: 20
    property color iconColor: FluTheme.dark ? "#FFFFFF" : "#000000"

    id:text_icon
    font.family: "Segoe Fluent Icons"
    font.pixelSize: iconSize
    horizontalAlignment: Text.AlignHCenter
    verticalAlignment: Text.AlignVCenter
    color: iconColor
    text: (String.fromCharCode(iconSource).toString(16));
}

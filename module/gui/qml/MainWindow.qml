import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import FluentUI

FluWindow {
    id:app
    width: 1440
    height: 810

    FluAppBar{
        id:appbar
        width: parent.width
        title: "Hello world"
    }


    FluText {
        text: "Hello There!"
        font.pixelSize: 32
        fontStyle: FluText.Body
        anchors.centerIn: parent
    }



}

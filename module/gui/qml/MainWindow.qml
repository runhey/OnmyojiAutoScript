import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import FluentUI

FluWindow {
    id:app
    width: 640
    height: 480

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

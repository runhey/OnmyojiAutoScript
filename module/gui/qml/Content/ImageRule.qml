import QtQuick
import QtQuick.Controls
import FluentUI
import "../Component"

Item {
    MirrorImage{
        id: mirrorImage
        anchors{
            left: parent.left
            top: parent.top
        }
        width: 1280
        height: 720 + 50
        imageWidth: 1280
        imageHeight: 720
    }
}

import QtQuick

Item {
    id: root
    property color hueColor : "blue"
    property real saturation : pickerCursor.x/(width-2*r)
    property real brightness : 1 - pickerCursor.y/(height-2*r)
    property int r : colorHandleRadius

    Rectangle {
        x : r
        y : r + parent.height - 2 * r
        rotation: -90
        transformOrigin: Item.TopLeft
        width: parent.height - 2 * r
        height: parent.width - 2 * r
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#FFFFFF" }
            GradientStop { position: 1.0; color: root.hueColor }
        }
    }
    Rectangle {
        x: r
        y: r
        width: parent.width - 2 * r
        height: parent.height - 2 *  r
        gradient: Gradient {
            GradientStop { position: 1.0; color: "#FF000000" }
            GradientStop { position: 0.0; color: "#00000000" }
        }
    }
    Item {
        id: pickerCursor
        Rectangle {
            width: r*2; height: r*2
            radius: r
            border.color: "black"; border.width: 2
            color: "transparent"
            Rectangle {
                anchors.fill: parent; anchors.margins: 2;
                border.color: "white"; border.width: 2
                radius: width/2
                color: "transparent"
            }
        }
    }
    MouseArea {
        anchors.fill: parent
        x: r
        y: r
        preventStealing: true
        function handleMouse(mouse) {
            if (mouse.buttons & Qt.LeftButton) {
                pickerCursor.x = Math.max(0,Math.min(mouse.x - r,width-2*r));
                pickerCursor.y = Math.max(0,Math.min(mouse.y - r,height-2*r));
            }
        }
        onPositionChanged:(mouse)=> handleMouse(mouse)
        onPressed:(mouse)=> handleMouse(mouse)
    }
}


import QtQuick

Item {
    property int cursorHeight: 7
    property real value: (1 - pickerCursor.y/height)
    width: 15
    height: 300
    Item {
        id: pickerCursor
        width: parent.width
        Rectangle {
            x: -3; y: -height*0.5
            width: parent.width + 4; height: cursorHeight
            border.color: "black"; border.width: 1
            color: "transparent"
            Rectangle {
                anchors.fill: parent; anchors.margins: 2
                border.color: "white"; border.width: 1
                color: "transparent"
            }
        }
    }
    MouseArea {
        y: -Math.round(cursorHeight/2)
        height: parent.height+cursorHeight
        anchors.left: parent.left
        preventStealing: true
        anchors.right: parent.right
        function handleMouse(mouse) {
            if (mouse.buttons & Qt.LeftButton) {
                pickerCursor.y = Math.max(0, Math.min(height, mouse.y)-cursorHeight)
            }
        }
        onPositionChanged:(mouse)=> {
            handleMouse(mouse)
        }
        onPressed:(mouse)=> handleMouse(mouse)
    }

    function setValue(val) {
        pickerCursor.y = height * (1 - val)
    }
}


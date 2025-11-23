import QtQuick 2.0
import QtQuick.Window 2.15

Item {
    id:rect
    property int minimumWidth: 5
    property int minimumHeight: 5
    property int mouseRegion: 5
    property var resizeTarget: rect
    anchors.fill: resizeTarget

    MouseArea{
        id: move
        anchors.fill: parent
        anchors.margins: mouseRegion
        cursorShape: Qt.ClosedHandCursor
        property int xPosition: 0
        property int yPosition: 0
        onPressed: function(mouse){
            xPosition = mouse.x
            yPosition = mouse.y
        }
        onPositionChanged: function(mouse){
            var xOffset = mouse.x-xPosition
            var yOffset = mouse.y-yPosition

            if(rect.resizeTarget.x+xOffset>0 && rect.resizeTarget.width+xOffset+rect.resizeTarget.x < rect.resizeTarget.parent.width){
                rect.resizeTarget.x = rect.resizeTarget.x+xOffset
            }

            if(rect.resizeTarget.y+yOffset>0 && rect.resizeTarget.height+yOffset+rect.resizeTarget.y < rect.resizeTarget.parent.height){
                rect.resizeTarget.y = rect.resizeTarget.y+yOffset
            }
        }
    }

    MouseArea {
        id:leftX
        width: mouseRegion
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.leftMargin: 0
        anchors.bottomMargin: 0
        anchors.topMargin: 0
        cursorShape: Qt.SizeHorCursor
        property int xPosition: 0
        onPressed: function(mouse){
            xPosition = mouse.x
        }

        onPositionChanged: function(mouse){
            var xOffset = mouse.x-xPosition
            if(rect.resizeTarget.x+xOffset>0 && rect.resizeTarget.width-xOffset>minimumWidth){
                rect.resizeTarget.x = rect.resizeTarget.x+xOffset
                rect.resizeTarget.width = rect.resizeTarget.width-xOffset
            }
        }
    }

    MouseArea{
        id:rightX
        width: mouseRegion
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 0
        anchors.topMargin: 0
        anchors.rightMargin: 0
        cursorShape: Qt.SizeHorCursor
        property int xPosition: 0
        onPressed: function(mouse){
            xPosition = mouse.x
        }

        onPositionChanged: function(mouse){
            var xOffset = mouse.x-xPosition
            var xWidth = rect.resizeTarget.width+xOffset
            var availableWidth = rect.resizeTarget.parent ? rect.resizeTarget.parent.width:Screen.desktopAvailableWidth
            if(xWidth+rect.resizeTarget.x<availableWidth && xWidth>minimumWidth){
                rect.resizeTarget.width = xWidth
            }
        }
    }

    MouseArea{
        id:topY
        height: mouseRegion
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.rightMargin: 0
        anchors.leftMargin: 0
        anchors.topMargin: 0
        cursorShape: Qt.SizeVerCursor
        property int yPosition: 0
        onPressed: function(mouse){
            yPosition = mouse.y
        }

        onPositionChanged: function(mouse){
            var yOffset = mouse.y-yPosition
            if(rect.resizeTarget.y+yOffset>0 && rect.resizeTarget.height-yOffset>minimumHeight){
                rect.resizeTarget.y = rect.resizeTarget.y+yOffset
                rect.resizeTarget.height = rect.resizeTarget.height-yOffset
            }
        }
    }

    MouseArea{
        id:bottomY
        height: mouseRegion
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: 0
        anchors.leftMargin: 0
        anchors.bottomMargin: 0
        cursorShape: Qt.SizeVerCursor
        property int yPosition: 0
        onPressed: function(mouse){
            yPosition = mouse.y
        }

        onPositionChanged: function(mouse){
            var yOffset = mouse.y-yPosition
            var yHeight = rect.resizeTarget.height+yOffset
            var availableHeight = rect.resizeTarget.parent ? rect.resizeTarget.parent.height : Screen.desktopAvailableHeight
            if(yHeight+rect.resizeTarget.y<availableHeight && yHeight>minimumHeight){
                rect.resizeTarget.height = yHeight
            }
        }
    }

    MouseArea{
        width: mouseRegion
        height: mouseRegion
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.topMargin: 0
        anchors.leftMargin: 0
        cursorShape: Qt.SizeFDiagCursor
        property int xPosition: 0
        property int yPosition: 0
        onPressed: function(mouse){
            xPosition = mouse.x
            yPosition = mouse.y
        }

        onPositionChanged: function(mouse){
            var xOffset = mouse.x-xPosition
            if(rect.resizeTarget.x+xOffset>0 && rect.resizeTarget.width-xOffset>minimumWidth){
                rect.resizeTarget.x = rect.resizeTarget.x+xOffset
                rect.resizeTarget.width = rect.resizeTarget.width-xOffset
            }
            var yOffset = mouse.y-yPosition
            if(rect.resizeTarget.y+yOffset>0 && rect.resizeTarget.height-yOffset>minimumHeight){
                rect.resizeTarget.y = rect.resizeTarget.y+yOffset
                rect.resizeTarget.height = rect.resizeTarget.height-yOffset
            }
        }
    }

    MouseArea{
        width: mouseRegion
        height: mouseRegion
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: 0
        anchors.rightMargin: 0
        cursorShape: Qt.SizeBDiagCursor
        property int xPosition: 0
        property int yPosition: 0
        onPressed: function(mouse){
            xPosition = mouse.x
            yPosition = mouse.y
        }

        onPositionChanged: function(mouse){
            var xOffset = mouse.x-xPosition
            var xWidth = rect.resizeTarget.width+xOffset
            var availableWidth = rect.resizeTarget.parent ? rect.resizeTarget.parent.width:Screen.desktopAvailableWidth
            var availableHeight = rect.resizeTarget.parent ? rect.resizeTarget.parent.height : Screen.desktopAvailableHeight

            if(xWidth+rect.resizeTarget.x<availableWidth && xWidth>minimumWidth){
                rect.resizeTarget.width = xWidth
            }
            var yOffset = mouse.y-yPosition
            if(rect.resizeTarget.y+yOffset>0 && rect.resizeTarget.height-yOffset>minimumHeight){
                rect.resizeTarget.y = rect.resizeTarget.y+yOffset
                rect.resizeTarget.height = rect.resizeTarget.height-yOffset
            }
        }
    }

    MouseArea{
        width: mouseRegion
        height: mouseRegion
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.leftMargin: 0
        anchors.bottomMargin: 0
        cursorShape: Qt.SizeBDiagCursor
        property int xPosition: 0
        property int yPosition: 0
        onPressed: function(mouse){
            xPosition = mouse.x
            yPosition = mouse.y
        }
        onPositionChanged: function(mouse){
            var xOffset = mouse.x-xPosition
            var availableWidth = rect.resizeTarget.parent ? rect.resizeTarget.parent.width:Screen.desktopAvailableWidth
            var availableHeight = rect.resizeTarget.parent ? rect.resizeTarget.parent.height : Screen.desktopAvailableHeight
            if(rect.resizeTarget.x+xOffset>0 && availableWidth-xOffset>minimumWidth){
                rect.resizeTarget.x = rect.resizeTarget.x+xOffset
                rect.resizeTarget.width = rect.resizeTarget.width-xOffset
            }
            var yOffset = mouse.y-yPosition
            var yHeight = rect.resizeTarget.height+yOffset
            if(yHeight+rect.resizeTarget.y<availableHeight && yHeight>minimumHeight){
                rect.resizeTarget.height = yHeight
            }
        }
    }


    MouseArea{
        width: mouseRegion
        height: mouseRegion
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: 0
        anchors.bottomMargin: 0
        cursorShape: Qt.SizeFDiagCursor
        property int xPosition: 0
        property int yPosition: 0
        onPressed: function(mouse){
            xPosition = mouse.x
            yPosition = mouse.y
        }
        onPositionChanged: function(mouse){
            var xOffset = mouse.x-xPosition
            var xWidth = rect.resizeTarget.width+xOffset
            var availableWidth = rect.resizeTarget.parent ? rect.resizeTarget.parent.width:Screen.desktopAvailableWidth
            var availableHeight = rect.resizeTarget.parent ? rect.resizeTarget.parent.height : Screen.desktopAvailableHeight

            if(xWidth+rect.resizeTarget.x<availableWidth && xWidth>minimumWidth){
                rect.resizeTarget.width = xWidth
            }
            var yOffset = mouse.y-yPosition
            var yHeight = rect.resizeTarget.height+yOffset
            if(yHeight+rect.resizeTarget.y<availableHeight && yHeight>minimumHeight){
                rect.resizeTarget.height = yHeight
            }
        }
    }
}

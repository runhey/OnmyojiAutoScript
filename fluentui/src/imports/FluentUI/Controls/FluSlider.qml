import QtQuick
import QtQuick.Controls
import Qt5Compat.GraphicalEffects
import FluentUI

Item{

    property int size: 180
    property int dotSize: 24
    property int value: 50
    property int maxValue: 100
    property bool vertical: false
    property bool tipEnabled : true
    property var onLineClickFunc
    signal pressed
    signal released

    id:root
    height: control.height
    width: control.width
    rotation: vertical ? 180 : 0

    Component.onCompleted: {
        seek(value)
    }

    MouseArea{
        id:mouse_line
        anchors.centerIn: control
        width: vertical ? 10 : control.width
        height: vertical ? control.height : 10
        hoverEnabled: true
        onClicked:
            (mouse) => {
                var val;
                if(vertical){
                    val = mouse.y*maxValue/control.height
                }else{
                    val = mouse.x*maxValue/control.width
                }
                if(onLineClickFunc){
                    onLineClickFunc(val)
                }else{
                    seek(val)
                }
            }
    }

    Rectangle {
        id: control
        width: vertical ? 4 :size
        height:  vertical ? size : 4
        radius: 2
        anchors.verticalCenter: parent.verticalCenter
        color:FluTheme.dark ? Qt.rgba(162/255,162/255,162/255,1) : Qt.rgba(138/255,138/255,138/255,1)
        Rectangle{
            id:rect
            radius: 2.5
            width: vertical ? 5 : control.width*(value/maxValue)
            height: vertical ? control.height*(value/maxValue) :  5
            color:FluTheme.dark ? FluTheme.primaryColor.lighter :FluTheme.primaryColor.dark
        }
    }

    Rectangle{
        id:dot
        width: dotSize
        height: dotSize
        FluShadow{
            radius: dotSize/2
        }
        radius: dotSize/2
        anchors.verticalCenter: vertical ? undefined : parent.verticalCenter
        anchors.horizontalCenter: vertical ? parent.horizontalCenter : undefined
        color:FluTheme.dark ? Qt.rgba(69/255,69/255,69/255,1) :Qt.rgba(1,1,1,1)
        Rectangle{
            width: dotSize
            height: dotSize
            radius: dotSize/2
            color:FluTheme.dark ? FluTheme.primaryColor.lighter :FluTheme.primaryColor.dark
            anchors.centerIn: parent
            scale: {
                if(control_mouse.pressed){
                    return 4/10
                }
                return control_mouse.containsMouse || mouse_line.containsMouse  ? 6/10 : 5/10
            }
            Behavior on scale {
                NumberAnimation{
                    duration: 150
                }
            }
        }
        MouseArea{
            id:control_mouse
            anchors.fill: parent
            hoverEnabled: true
            drag {
                target: dot
                axis: vertical ? Drag.YAxis : Drag.XAxis
                minimumX: vertical ? 0 : -dotSize/2
                maximumX: vertical ? 0 : (control.width - dotSize/2)
                minimumY: vertical ? -dotSize/2 : 0
                maximumY: vertical ? (control.height - dotSize/2) : 0
            }
            onPressed: {
                if(tipEnabled){
                    tool_tip.visible  =  true
                }
                root.pressed()
            }

            onReleased: {
                tool_tip.visible  =  false
                root.released()
            }
        }

        FluTooltip{
            id:tool_tip
            text:String(root.value)
            y: vertical ? 32 : -40
        }
    }

    function seek(val){
        if(vertical){
            dot.y =val/maxValue*control.height - dotSize/2
            root.value = Qt.binding(function(){
                return (dot.y+dotSize/2)/control.height*maxValue
            })
        }else{
            dot.x =val/maxValue*control.width - dotSize/2
            root.value = Qt.binding(function(){
                return (dot.x+dotSize/2)/control.width*maxValue
            })
        }
    }
}


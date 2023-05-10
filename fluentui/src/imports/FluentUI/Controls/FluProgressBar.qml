import QtQuick
import QtQuick.Controls
import FluentUI

FluRectangle {

    property real progress: 0.5
    property bool indeterminate: true

    id: control
    width: 150
    height: 5
    radius: [3,3,3,3]
    clip: true
    color:  FluTheme.dark ? Qt.rgba(99/255,99/255,99/255,1) : Qt.rgba(214/255,214/255,214/255,1)

    Component.onCompleted: {
        if(indeterminate){
            bar.x = -control.width*0.5
            behavior.enabled = true
            bar.x = control.width
        }else{
            bar.x = 0
        }
    }

    Rectangle{
        id:bar
        radius: 3
        width: control.width*progress
        height:  control.height
        color:FluTheme.dark ? FluTheme.primaryColor.lighter : FluTheme.primaryColor.dark

        Behavior on x{
            id:behavior
            enabled: false
            NumberAnimation{
                duration: 1000
                onRunningChanged: {
                    if(!running){
                        behavior.enabled = false
                        bar.x = -control.width*0.5
                        behavior.enabled = true
                        bar.x = control.width
                    }
                }
            }
        }
    }
}

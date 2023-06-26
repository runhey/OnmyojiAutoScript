import QtQuick
import QtQuick.Controls
import FluentUI
import "../Global"

Item {
    id: root
    width: 40
    height: 40
    clip: true
    property int runStatus: MainEvent.runStatus
    property real radius: width / 2
    property color color: FluTheme.dark ? FluTheme.primaryColor.lighter : FluTheme.primaryColor.dark
    property real animationDuration: 600 // in ms
    property real maxRadius: width / 4


    Rectangle {
        id: runError
        anchors.centerIn: parent
        width: radius * 2
        height: radius * 2
        visible: runStatus
        color: root.color
        radius: radius

//        Behavior on radius {
//            enabled: false
//            NumberAnimation {
//                duration: root.animationDuration
//                easing.type: Easing.OutQuad
//            }
//        }

//        SequentialAnimation on radius {
//            enabled: false
//            loops: Animation.Infinite
//            PropertyAnimation { to: root.maxRadius; duration: root.animationDuration }
//        }
    }

    FluProgressRing{
        id: runProgress
        anchors.centerIn: parent
        indeterminate: false
        width: parent.width/2
        height: parent.height/2
    }

    onRunStatusChanged: {
        if(runStatus === MainEvent.RunStatus.Empty){
            runError.visible = false
            runProgress.visible = false
        }else if(runStatus === MainEvent.RunStatus.Free){
            runError.visible = false
            runProgress.visible = true
            runProgress.progress = 0
        }else if(runStatus === MainEvent.RunStatus.Run){
            runError.visible = false
            runProgress.visible = true
            runProgress.progress = 0.25
        }else if(runStatus === MainEvent.RunStatus.Error){
            runError.visible = true
            runProgress.visible = false
            runProgress.progress = 0
        }else if(runStatus === MainEvent.RunStatus.Init){
            runError.visible = false
            runProgress.visible = true
            runProgress.progress = 0.25
        }
    }



}

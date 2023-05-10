import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import FluentUI
import "../component"

FluScrollablePage{

    title:"MediaPlayer"
    leftPadding:10
    rightPadding:10
    bottomPadding:20
    spacing: 0

    onVisibleChanged: {
        if(visible){
            player.play()
        }else{
            player.pause()
        }
    }
    FluArea{
        Layout.fillWidth: true
        height: 320
        Layout.topMargin: 20
        paddings: 10
        ColumnLayout{
            anchors{
                verticalCenter: parent.verticalCenter
                left:parent.left
            }
            FluMediaPlayer{
                id:player
                source:"http://clips.vorwaerts-gmbh.de/big_buck_bunny.mp4"
            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluMediaPlayer{
    id:player
    source:"http://clips.vorwaerts-gmbh.de/big_buck_bunny.mp4"
}
'
    }
    FluArea{
        Layout.fillWidth: true
        height: 68
        Layout.topMargin: 20
        paddings: 10
        FluButton{
            text:"跳转到视频播放器窗口"
            anchors.verticalCenter: parent.verticalCenter
            onClicked:{
                FluApp.navigate("/media",{source:"http://clips.vorwaerts-gmbh.de/big_buck_bunny.mp4"})
            }
        }
    }




}


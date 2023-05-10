import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import FluentUI

FluWindow {

    title:"视频播放器"
    width: 640
    height: 480
    minimumWidth: 640
    minimumHeight: 480

    onInitArgument:
        (argument)=>{
            player.source = argument.source
        }

    FluAppBar{
        id:appbar
        title:"视频播放器"
        width:parent.width
    }

    FluMediaPlayer{
        id:player
        anchors{
            left: parent.left
            right: parent.right
            top: appbar.bottom
            bottom: parent.bottom
        }
    }

}

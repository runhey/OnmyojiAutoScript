import QtQuick
import QtQuick.Controls
import QtQuick.Window
import QtQuick.Layouts
import FluentUI

Rectangle{

    property string title: ""
    property string darkText : "夜间模式"
    property string minimizeText : "最小化"
    property string restoreText : "向下还原"
    property string maximizeText : "最大化"
    property string closeText : "关闭"
    property color textColor: FluTheme.dark ? "#FFFFFF" : "#000000"
    property color minimizeNormalColor: Qt.rgba(0,0,0,0)
    property color minimizeHoverColor: FluTheme.dark ? Qt.rgba(1,1,1,0.1) : Qt.rgba(0,0,0,0.06)
    property color maximizeNormalColor: Qt.rgba(0,0,0,0)
    property color maximizeHoverColor: FluTheme.dark ? Qt.rgba(1,1,1,0.1) : Qt.rgba(0,0,0,0.06)
    property color closeNormalColor: Qt.rgba(0,0,0,0)
    property color closeHoverColor:  Qt.rgba(251/255,115/255,115/255,1)
    property bool showDark: false
    property color borerlessColor : FluTheme.dark ? FluTheme.primaryColor.lighter : FluTheme.primaryColor.dark

    Item{
        id:d
        property var win: Window.window
        property bool isRestore: win && Window.Maximized === win.visibility
        property bool resizable: win && !(win.minimumHeight === win.maximumHeight && win.maximumWidth === win.minimumWidth)
    }

    id:root
    color: Qt.rgba(0,0,0,0)
    visible: FluTheme.frameless
    height: visible ? 30 : 0
    opacity: visible
    z: 65535

    TapHandler {
        onTapped: if (tapCount === 2) toggleMaximized()
        gesturePolicy: TapHandler.DragThreshold
    }

    DragHandler {
        target: null
        grabPermissions: TapHandler.CanTakeOverFromAnything
        onActiveChanged: if (active) { d.win.startSystemMove(); }
    }

    FluText {
        text: title
        anchors{
            verticalCenter: parent.verticalCenter
            left: parent.left
            leftMargin: 10
        }
        color:root.textColor
    }

    RowLayout{
        anchors.right: parent.right
        height: root.height
        spacing: 0

        RowLayout{
            Layout.alignment: Qt.AlignVCenter
            Layout.rightMargin: 5
            visible: showDark
            spacing: 5
            FluText{
                text:darkText
                color:root.textColor
            }
            FluToggleSwitch{
                selected: FluTheme.dark
                clickFunc:function(){
                    if(FluTheme.dark){
                        FluTheme.darkMode = FluDarkMode.Light
                    }else{
                        FluTheme.darkMode = FluDarkMode.Dark
                    }
                }
            }
        }

        // FluIconButton{
        //     width: 40
        //     height: 30
        //     iconSource : FluentIcons.Down
        //     Layout.alignment: Qt.AlignVCenter
        //     iconSize: 11
        //     text: "隐藏到系统托盘"
        //     radius: 0
        //     iconColor: root.textColor
        //     color: hovered ? minimizeHoverColor : minimizeNormalColor
        //     onClicked: {
        //         d.win.hide()
        //     }
        // }
        FluIconButton{
            width: 40
            height: 30
            iconSource : FluentIcons.ChromeMinimize
            Layout.alignment: Qt.AlignVCenter
            iconSize: 11
            text:minimizeText
            radius: 0
            iconColor: root.textColor
            color: hovered ? minimizeHoverColor : minimizeNormalColor
            onClicked: {
                d.win.showMinimized()
            }
        }
        FluIconButton{
            width: 40
            height: 30
            iconSource : d.isRestore  ? FluentIcons.ChromeRestore : FluentIcons.ChromeMaximize
            color: hovered ? maximizeHoverColor : maximizeNormalColor
            Layout.alignment: Qt.AlignVCenter
            visible: d.resizable
            radius: 0
            iconColor: root.textColor
            text:d.isRestore?restoreText:maximizeText
            iconSize: 11
            onClicked: {
                toggleMaximized()
            }
        }
        FluIconButton{
            iconSource : FluentIcons.ChromeClose
            Layout.alignment: Qt.AlignVCenter
            text:closeText
            width: 40
            height: 30
            radius: 0
            iconSize: 10
            iconColor: hovered ? Qt.rgba(1,1,1,1) : root.textColor
            color:hovered ? closeHoverColor : closeNormalColor
            onClicked: {
                d.win.close()
            }
        }
    }

    function toggleMaximized() {
        if(!d.resizable)
            return
        if (d.win.visibility === Window.Maximized) {
            d.win.showNormal();
        } else {
            d.win.showMaximized();
        }
    }

}

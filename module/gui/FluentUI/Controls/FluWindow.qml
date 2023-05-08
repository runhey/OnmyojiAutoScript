import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import FluentUI

ApplicationWindow {

    enum LaunchMode {
        Standard,
        SingleTask,
        SingleInstance
    }

    default property alias content: container.data
    property bool closeDestory: true
    property int launchMode: FluWindow.Standard
    property string route
    property var argument:({})
    property var pageRegister
    property var closeFunc: function(event){
        if(closeDestory){
            destoryWindow()
        }else{
            visible = false
            event.accepted = false
        }
    }
    signal initArgument(var argument)

    QtObject{
        id:d
        property bool firstFlag: true
    }

    id:window
    background: Rectangle{
        color: {
            if(active){
                return FluTheme.dark ? Qt.rgba(26/255,34/255,40/255,1) : Qt.rgba(238/255,244/255,249/255,1)
            }
            return FluTheme.dark ? Qt.rgba(32/255,32/255,32/255,1) : Qt.rgba(243/255,243/255,243/255,1)
        }
        Behavior on color{
            ColorAnimation {
                duration: 300
            }
        }
    }

    Item{
        id:container
        anchors.fill: parent
        anchors.margins: window.visibility === Window.Maximized && FluTheme.frameless ? 8/Screen.devicePixelRatio : 0
        clip: true
    }

    onActiveChanged: {
        if(d.firstFlag){
            helper.firstUpdate()
            d.firstFlag = false
        }
    }

    onClosing:(event)=>closeFunc(event)

    FluInfoBar{
        id:infoBar
        root: window
    }

    WindowHelper{
        id:helper
    }

    Component.onCompleted: {
        helper.initWindow(window)
        initArgument(argument)
        window.x = (Screen.width - window.width)/2
        window.y = (Screen.desktopAvailableHeight - window.height)/2
    }

    function showSuccess(text,duration,moremsg){
        infoBar.showSuccess(text,duration,moremsg);
    }

    function showInfo(text,duration,moremsg){
        infoBar.showInfo(text,duration,moremsg);
    }

    function showWarning(text,duration,moremsg){
        infoBar.showWarning(text,duration,moremsg);
    }

    function showError(text,duration,moremsg){
        infoBar.showError(text,duration,moremsg);
    }

    function registerForWindowResult(path){
        return helper.createRegister(window,path)
    }

    function destoryWindow(){
        helper.destoryWindow()
    }

    function onResult(data){
        if(pageRegister){
            pageRegister.onResult(data)
        }
    }

}

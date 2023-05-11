import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import Qt.labs.platform

import FluentUI
import "./Global/"

FluWindow {
    id:window
    title: "oas"
    width: 1000
    height: 720
    closeDestory:false
    minimumWidth: 520
    minimumHeight: 460
    launchMode: FluWindow.SingleTask

//    Connections{
//        target: appInfo
//        function onActiveWindow(){
//            window.show()
//            window.raise()
//            window.requestActivate()
//        }
//    }

    FluAppBar{
       id:appbar
       z:9
       width: parent.width
    }

// 任务栏的左边系统图标
    SystemTrayIcon {
        id:system_tray
        visible: true
        icon.source: "qrc:/res/icon.ico"
        tooltip: "oas"
        menu: Menu {
            MenuItem {
                text: "退出"
                onTriggered: {
                    window.destoryWindow()
                    FluApp.closeApp()
                }
            }
        }
        onActivated:
            (reason)=>{
                if(reason === SystemTrayIcon.Trigger){
                    window.show()
                    window.raise()
                    window.requestActivate()
                }
            }
    }


    FluNavigationView{
        id:nav_view
        anchors.fill: parent
        items: ItemsOriginal
        footerItems:ItemsFooter
        z:11
        displayMode:MainEvent.displayMode
        logo: "qrc:/res/icon.ico"
        title:"OAS"
        Component.onCompleted: {
            items.navigationView = nav_view
            footerItems.navigationView = nav_view
            nav_view.setCurrentIndex(0)
        }
    }



}

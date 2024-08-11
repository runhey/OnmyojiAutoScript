import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import Qt.labs.platform

import FluentUI
import "./Global/"
import "./Component/"

FluWindow {
    id:window
    title: "oas"
    width: 1100
    height: 720
    closeDestory:false
    minimumWidth: 520
    minimumHeight: 460
    launchMode: FluWindow.SingleTask

    FluAppBar{
       id:appbar
       z:9
       width: parent.width
    }
//    OverStatus{
//        anchors{
//            top: parent.top
//            horizontalCenter: parent.horizontalCenter
//        }
//    }


// 任务栏的右边边系统图标
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

    //添加一份脚本实例的dialog
    Add{
        id: add
        property bool add_open: MainEvent.addOpen
        onAdd_openChanged: {
            add.open()
        }
        onUpdateScriptItems: {
            nav_view.items.addFluPaneItems()
//            process_manager.create_all()
        }
    }
//    Notity{
//        id: notity
//    }

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
            items.addFluPaneItems()

            notity.open()
        }
    }
    Component.onCompleted:{
//        process_manager.create_all()
    }

}

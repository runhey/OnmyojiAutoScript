pragma Singleton

import QtQuick
import FluentUI
import "../Global/"

FluObject{

    property var navigationView

    id:footer_items

    FluPaneItemSeparator{}

    FluPaneItem{
        title: "add"
        icon: FluentIcons.Add
        onTap:{
            MainEvent.addOpen = !MainEvent.addOpen
        }
    }
    FluPaneItem{
        title: "about"
        icon:FluentIcons.Contact
        tapFunc:function(){
            console.debug("this click about")
            MainEvent.runStatus = MainEvent.RunStatus.Error
        }
    }

    FluPaneItem{
        title: "settings"
        icon:FluentIcons.Settings
        onTap:{
            Qt.Pa
            navigationView.push(Qt.resolvedUrl("../../qml/Page/O_Settings.qml"))
        }
    }

}

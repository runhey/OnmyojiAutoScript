pragma Singleton

import QtQuick
import FluentUI
import "../Global/"

FluObject{

    property var navigationView

    id:footer_items

    FluPaneItemSeparator{}

    FluPaneItem{
        title: qsTr("add")
        icon: FluentIcons.Add
        onTap:{
            MainEvent.addOpen = !MainEvent.addOpen
        }
    }
    FluPaneItem{
        title: qsTr("about")
        icon:FluentIcons.Contact
        tapFunc:function(){
            MainEvent.runStatus = MainEvent.RunStatus.Error
        }
    }

    FluPaneItem{
        title: qsTr("settings")
        icon:FluentIcons.Settings
        onTap:{
            Qt.Pa
//            navigationView.push(Qt.resolvedUrl("../../qml/Page/O_Settings.qml"))
            navigationView.pushScript(Qt.resolvedUrl("../../qml/Page/O_Settings.qml"), "settings")
        }
    }

}

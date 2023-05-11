pragma Singleton

import QtQuick
import FluentUI

FluObject{

    property var navigationView

    id:footer_items

    FluPaneItemSeparator{}

    FluPaneItem{
        title: "关于"
        icon:FluentIcons.Contact
        tapFunc:function(){
            console.debug("this click about")
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

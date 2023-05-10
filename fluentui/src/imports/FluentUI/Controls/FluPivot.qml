import QtQuick
import QtQuick.Controls
import FluentUI

Item {

    default property alias content: d.children
    property alias currentIndex: nav_list.currentIndex
    property color normalColor: FluTheme.dark ? FluColors.Grey120 : FluColors.Grey120
    property color hoverColor: FluTheme.dark ? FluColors.Grey10 : FluColors.Black

    id:control
    width: 400
    height: 300
    implicitHeight: height
    implicitWidth: width

    MouseArea{
        anchors.fill: parent
        preventStealing: true
    }

    FluObject{
        id:d
    }

    ListView{
        id:nav_list
        height: 40
        width: control.width
        model:d.children
        clip: true
        spacing: 20
        interactive: false
        orientation:ListView.Horizontal
        highlight: Item{
            clip: true
            Rectangle{
                height: 3
                radius: 1.5
                color: FluTheme.primaryColor.dark
                width: nav_list.currentItem ? nav_list.currentItem.width : 0
                y:37
                Behavior on width {
                    NumberAnimation{
                        duration: 150
                    }
                }
            }
        }
        delegate: Button{
            id:item_button
            width: item_title.width
            height: nav_list.height
            background:Item{
            }
            contentItem: Item{
                FluText {
                    id:item_title
                    font: FluTextStyle.Title
                    text: modelData.title
                    anchors.centerIn: parent
                    color: {
                        if(item_button.hovered)
                            return hoverColor
                        return normalColor
                    }
                }
                transitions: Transition {
                    NumberAnimation{
                        duration: 400;
                    }
                }
            }
            onClicked: {
                nav_list.currentIndex = index
            }
        }
    }

    Item{
        id:container
        anchors{
            top: nav_list.bottom
            topMargin: 10
            left: parent.left
            right: parent.right
            bottom: parent.bottom
        }

        Repeater{
            model:d.children
            Loader{
                property var argument: modelData.argument
                anchors.fill: parent
                sourceComponent: modelData.contentItem
                visible: nav_list.currentIndex === index
            }
        }
    }


}

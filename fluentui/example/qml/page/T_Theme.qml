import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls
import FluentUI
import "../component"

FluScrollablePage{

    title:"Theme"
    leftPadding:10
    rightPadding:10
    bottomPadding:20
    spacing: 0

    FluArea{
        Layout.fillWidth: true
        Layout.topMargin: 20
        height: 210
        paddings: 10
        ColumnLayout{
            spacing:0
            anchors{
                left: parent.left
            }
            RowLayout{
                Layout.topMargin: 10
                Repeater{
                    model: [FluColors.Yellow,FluColors.Orange,FluColors.Red,FluColors.Magenta,FluColors.Purple,FluColors.Blue,FluColors.Teal,FluColors.Green]
                    delegate:  FluRectangle{
                        width: 42
                        height: 42
                        radius: [4,4,4,4]
                        color: mouse_item.containsMouse ? Qt.lighter(modelData.normal,1.1) : modelData.normal
                        FluIcon {
                            anchors.centerIn: parent
                            iconSource: FluentIcons.AcceptMedium
                            iconSize: 15
                            visible: modelData === FluTheme.primaryColor
                            color: FluTheme.dark ? Qt.rgba(0,0,0,1) : Qt.rgba(1,1,1,1)
                        }
                        MouseArea{
                            id:mouse_item
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: {
                                FluTheme.primaryColor = modelData
                            }
                        }
                    }
                }
            }
            FluText{
                text:"夜间模式"
                Layout.topMargin: 20
            }
            FluToggleSwitch{
                Layout.topMargin: 5
                selected: FluTheme.dark
                clickFunc:function(){
                    if(FluTheme.dark){
                        FluTheme.darkMode = FluDarkMode.Light
                    }else{
                        FluTheme.darkMode = FluDarkMode.Dark
                    }
                }
            }
            FluText{
                text:"native文本渲染"
                Layout.topMargin: 20
            }
            FluToggleSwitch{
                Layout.topMargin: 5
                selected: FluTheme.nativeText
                clickFunc:function(){
                    FluTheme.nativeText = !FluTheme.nativeText
                }
            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluTheme.primaryColor = FluColors.Orange

FluTheme.dark = true

FluTheme.nativeText = true'
    }


}

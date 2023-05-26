import QtQuick
import QtQuick.Layouts
import FluentUI

Item {



    Item{
        id: leftScheduler
        width: 260
        anchors{
            left: parent.left
            top: parent.top
            bottom: parent.bottom
        }
        FluArea{
            id: schedulerOpen
            anchors.top: parent.top
            width: parent.width
            height: 50
            RowLayout{
                anchors.fill: parent
                FluText{
                    text: 'Scheduler'
                    Layout.leftMargin: 16
                    font: FluTextStyle.Subtitle
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignLeft
                }
                FluToggleButton{
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
                    Layout.rightMargin: 16
                    text:"Start"
                    onClicked: {
                        selected = !selected
                        if(selected){
                            text = "Start"
                        }else{
                            text = "Stop"
                        }
                    }
                }
            }
        }
        FluArea{
            id: schedulerRunning
            anchors.top: schedulerOpen.bottom
            anchors.topMargin: 10
            width: parent.width
            height: 120
            ColumnLayout{
                width: parent.width
                spacing: 8
                FluText{
                    text: 'Running'
                    Layout.leftMargin: 16
                    Layout.topMargin: 6
                    font: FluTextStyle.Subtitle
                }
                Rectangle{
                    width: schedulerRunning.width - 20
                    height: 2
                    Layout.alignment: Qt.AlignHCenter
                    color: FluTheme.dark ? Qt.rgba(64/255, 68/255, 75/255, 1) : Qt.rgba(234/255, 236/255, 239/255, 1)
                    radius: 2
                }
                Taskmini{
                    Layout.leftMargin: 16
                }
            }
        }
        FluArea{
            id: schedulerPending
            anchors.top: schedulerRunning.bottom
            anchors.topMargin: 10
            width: parent.width
            height: 240
            ColumnLayout{
                width: parent.width
                spacing: 8
                FluText{
                    text: 'Pending'
                    Layout.leftMargin: 16
                    Layout.topMargin: 6
                    font: FluTextStyle.Subtitle
                }
                Rectangle{
                    width: schedulerRunning.width - 20
                    height: 2
                    Layout.alignment: Qt.AlignHCenter
                    color: FluTheme.dark ? Qt.rgba(64/255, 68/255, 75/255, 1) : Qt.rgba(234/255, 236/255, 239/255, 1)
                    radius: 2
                }
                Taskmini{
                    Layout.leftMargin: 16
                }
                Taskmini{
                    Layout.leftMargin: 16
                }
                Taskmini{
                    Layout.leftMargin: 16
                }
                Taskmini{
                    Layout.leftMargin: 16
                }
            }
        }
        FluArea{
            id: schedulerWaiting
            anchors.top: schedulerPending.bottom
            anchors.topMargin: 10
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 0
            width: parent.width
            ColumnLayout{
                width: parent.width
                spacing: 8
                FluText{
                    Layout.fillHeight: false
                    text: 'Waiting'
                    Layout.leftMargin: 16
                    Layout.topMargin: 6
                    font: FluTextStyle.Subtitle
                }
                Rectangle{
                    Layout.fillHeight: false
                    width: schedulerPending.width - 20
                    height: 2
                    Layout.alignment: Qt.AlignHCenter
                    color: FluTheme.dark ? Qt.rgba(64/255, 68/255, 75/255, 1) : Qt.rgba(234/255, 236/255, 239/255, 1)
                    radius: 2
                }
                Taskmini{
                    Layout.leftMargin: 16
                    Layout.fillHeight: false
                }
            }
        }
    }
    FluArea{
        anchors.left: leftScheduler.right
        anchors.leftMargin: 10
        height: parent.height
        anchors.right: parent.right
    }
}

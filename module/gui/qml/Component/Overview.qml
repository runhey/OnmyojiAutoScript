import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import FluentUI

Item {
    id: root
    property string configName: ""


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
                FluIconButton{
                     Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
                    text: "Restart"
                    iconSource: FluentIcons.RepeatAll
                    onClicked: {
                        showSuccess("Restart"+" "+configName)
                        process_manager.restart(configName)
                        textLog.text = ""
                    }
                }
                FluToggleButton{
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
                    Layout.rightMargin: 16
                    text:"Start"
                    selected: true
                    onClicked: {
                        selected = !selected
                        if(selected){
                            text = "Start"
                            textLog.text = ""
                            process_manager.stop_script(root.configName)
                        }else{
                            // 如果按键颜色变灰色
                            text = "Stop"
                            process_manager.start_script(root.configName)
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
                    id: task_running
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
        id: logHeader
        anchors.top: parent.top
        anchors.left: leftScheduler.right
        anchors.leftMargin: 10
        anchors.right: parent.right
        height: 50
        RowLayout{
            anchors.fill: parent
            RowLayout.alignment: Qt.AlignRight | Qt.AlignVCenter
            FluText{
                text: 'Log'
                Layout.leftMargin: 16
                font: FluTextStyle.Subtitle
                Layout.alignment: Qt.AlignVCenter | Qt.AlignLeft
            }
            OverStatus{
                Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
            }
            FluToggleButton{
                Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
                Layout.rightMargin: 16
                text:"Auto Scroll On"
                selected: true
                onClicked: {
                    selected = !selected
                    if(selected){
                        text = "Auto Scroll On"
                    }else{
                        text = "Auto Scroll Off"
                    }
                }
            }
        }
    }

    FluArea{
        anchors.top: logHeader.bottom
        anchors.topMargin: 10
        anchors.bottom: parent.bottom
        anchors.left: leftScheduler.right
        anchors.leftMargin: 10
        anchors.right: parent.right
        FluScrollablePage{
            anchors.fill: parent
        FluText{
            id: textLog
            width: parent.width
            padding: 10
            clip: true
            wrapMode: Text.WordWrap // 设置自动换行模式
            text: ""

            function add_log(config, log){
                if(config !== root.configName){
                    return
                }
                textLog.text += log
            }

            Component.onCompleted:{
                process_manager.log_signal.connect(textLog.add_log)
            }


        }}
    }

    Component.onCompleted:{
        process_manager.sig_update_task.connect(update_task)
        process_manager.sig_update_pending.connect(update_pending)
        process_manager.sig_update_waiting.connect(update_waiting)
    }
    function update_task(config, data){
        if(typeof data !== "string"){
            console.error("Pass an incorrect type")
            return
        }

        if(config !== configName){
            return
        }
        task_running.setData(data)
    }
    function update_pending(config, data){
        if(typeof data !== "string"){
            console.error("Pass an incorrect type")
            return
        }
        if(config !== configName){
            return
        }
    }
    function update_waiting(config, data){
        if(typeof data !== "string"){
            console.error("Pass an incorrect type")
            return
        }
        if(config !== configName){
            return
        }
    }
}

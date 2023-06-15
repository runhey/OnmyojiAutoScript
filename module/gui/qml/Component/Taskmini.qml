import QtQuick
import QtQuick.Layouts
import FluentUI
// 这个组件是在总览那儿小小的显示
// 任务的名称 + 时间 以及一个设置的入口

Item {
    id: root
    width: 225
    height: 40
    visible: true

    property alias name: taskName.text
    property alias nextRun: taskTime.text
    signal click(string title)

    FluText{
        id: taskName
        anchors{
            left: parent.left
            leftMargin: 0
            top: parent.top
            topMargin: 0
        }
        text: "taskName"
        font: FluTextStyle.BodyStrong
    }
    FluText{
        id: taskTime
        anchors{
            left: parent.left
            leftMargin: 0
            bottom: parent.bottom
            bottomMargin: 0
        }
        text: "2023-05-26 18:33:55"
        font: FluTextStyle.Caption
    }
    FluButton{
        id: settingButton
        anchors{
            right: parent.right
            rightMargin: 0
            verticalCenter: parent.verticalCenter
        }
        text:"setting"
        onClicked: {
            showSuccess(name)
            root.click(configName)
        }
    }
    // 使用这个的前提是 data 是字符串
    function  setData(data){
        if(data === "{}"){  // 这个表示没有数据，是空的
            root.visible = false
            return
        }
        root.visible = true
        const d = JSON.parse(data)
        task_running.name = d["name"]
        task_running.nextRun = d["next_run"]
    }
}

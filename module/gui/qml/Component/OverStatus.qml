import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import FluentUI
import "../Global/"

Item{

//    width: 200
    height: 40

    id: root
    property int runStatus: MainEvent.RunStatus.Init

    RowLayout{
        anchors.fill: parent
        spacing: 0
        FluText{
            id: menuName
            Layout.alignment: Qt.AlignVCenter
            text: qsTr(MainEvent.menuTitle)
            font: FluTextStyle.BodyStrong
        }
        RunStatusIcon{
            id: runStatusIcon
            Layout.alignment: Qt.AlignVCenter
            Layout.leftMargin: 20
            runStatus: root.runStatus
        }
        FluText{
            id:runStatusText
            Layout.alignment: Qt.AlignVCenter
            text: "初始化"

        }
    }

    onRunStatusChanged: {
        if(root.runStatus === MainEvent.RunStatus.Empty){
            runStatusText.text= ""
        }else if(root.runStatus === MainEvent.RunStatus.Free){
            runStatusText.text= "闲置"
        }else if(root.runStatus === MainEvent.RunStatus.Run){
            runStatusText.text= "运行中"
        }else if(root.runStatus === MainEvent.RunStatus.Error){
            runStatusText.text= "发生错误"
        }else if(root.runStatus === MainEvent.RunStatus.Init){
            runStatusText.text= "初始化"
        }
    }
}

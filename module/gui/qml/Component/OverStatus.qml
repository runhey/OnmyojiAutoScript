import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import FluentUI
import "../Global/"

Item{

//    width: 200
    height: 40
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
            runStatus: MainEvent.runStatus
        }
        FluText{
            id:runStatusText
            property int runStatus: MainEvent.runStatus
            Layout.alignment: Qt.AlignVCenter
            text: ""
            onRunStatusChanged: {
                if(runStatus === MainEvent.RunStatus.Empty){
                    text= ""
                }else if(runStatus === MainEvent.RunStatus.Free){
                    text= "闲置"
                }else if(runStatus === MainEvent.RunStatus.Run){
                    text= "运行中"
                }else if(runStatus === MainEvent.RunStatus.Error){
                    text= "发生错误"
                }
            }
        }
    }
}

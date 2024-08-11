import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls
import FluentUI
import "../component"

FluScrollablePage{

    title:"Dialog"
    leftPadding:10
    rightPadding:10
    bottomPadding:20
    spacing: 0

    FluArea{
        Layout.fillWidth: true
        height: 68
        paddings: 10
        Layout.topMargin: 20
        FluButton{
            anchors.verticalCenter: parent.verticalCenter
            Layout.topMargin: 20
            text:"Show Double Button Dialog"
            onClicked: {
                double_btn_dialog.open()
            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluContentDialog{
    id:dialog
    title:"友情提示"
    message:"确定要退出程序么？"
    negativeText:"取消"
    buttonFlags: FluContentDialog.NegativeButton | FluContentDialog.PositiveButton
    onNegativeClicked:{
        showSuccess("点击取消按钮")
    }
    positiveText:"确定"
    onPositiveClicked:{
        showSuccess("点击确定按钮")
    }
    }
    dialog.open()'
    }

    FluContentDialog{
        id:double_btn_dialog
        title:"友情提示"
        message:"确定要退出程序么？"
        buttonFlags: FluContentDialog.NegativeButton | FluContentDialog.PositiveButton
        negativeText:"取消"
        onNegativeClicked:{
            showSuccess("点击取消按钮")
        }
        positiveText:"确定"
        onPositiveClicked:{
            showSuccess("点击确定按钮")
        }
    }

    FluArea{
        Layout.fillWidth: true
        height: 68
        paddings: 10
        Layout.topMargin: 20
        FluButton{
            anchors.verticalCenter: parent.verticalCenter
            Layout.topMargin: 20
            text:"Show Triple Button Dialog"
            onClicked: {
                triple_btn_dialog.open()
            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluContentDialog{
    id:dialog
    title:"友情提示"
    message:"确定要退出程序么？"
    negativeText:"取消"
    buttonFlags: FluContentDialog.NeutralButton | FluContentDialog.NegativeButton | FluContentDialog.PositiveButton
    negativeText:"取消"
    onNegativeClicked:{
        showSuccess("点击取消按钮")
    }
    positiveText:"确定"
    onPositiveClicked:{
        showSuccess("点击确定按钮")
    }
    neutralText:"最小化"
    onNeutralClicked:{
        showSuccess("点击最小化按钮")
        }
    }
    dialog.open()'
    }

    FluContentDialog{
        id:triple_btn_dialog
        title:"友情提示"
        message:"确定要退出程序么？"
        buttonFlags: FluContentDialog.NeutralButton | FluContentDialog.NegativeButton | FluContentDialog.PositiveButton
        negativeText:"取消"
        onNegativeClicked:{
            showSuccess("点击取消按钮")
        }
        positiveText:"确定"
        onPositiveClicked:{
            showSuccess("点击确定按钮")
        }
        neutralText:"最小化"
        onNeutralClicked:{
            showSuccess("点击最小化按钮")
        }
    }
}

import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls
import FluentUI
import "../Global"

FluContentDialog{
    id:dialog
    title:"Add new config"

    signal updateScriptItems

    contentItem: Rectangle {
        id:layout_content
        implicitWidth:minWidth
        implicitHeight: text_title.height + contextC.height + layout_actions.height
        color:FluTheme.dark ? Qt.rgba(45/255,45/255,45/255,1) : Qt.rgba(249/255,249/255,249/255,1)
        radius:5
        FluShadow{
            radius: 5
        }
        FluText{
            id:text_title
            font: FluTextStyle.Subtitle
            text:title
            topPadding: 20
            leftPadding: 20
            rightPadding: 20
            wrapMode: Text.WrapAnywhere
            horizontalAlignment: Text.AlignHCenter
            anchors{
                top:parent.top
                left: parent.left
                right: parent.right
            }
        }
        Column{
            id: contextC
            anchors{
                horizontalCenter: parent.horizontalCenter
                top: text_title.bottom
            }
            spacing: 10
            FluText{
                text: 'New name'
                leftPadding: 6
                font: FluTextStyle.Caption
            }
            FluTextBox{
                id: newNameBox
                placeholderText:"推荐:oas+number"
//                maxLength: 20
                validator: RegularExpressionValidator { regularExpression: /^[a-zA-Z0-9]*$/ }
            }
            FluText{
                text: 'Copy from existing config'
                leftPadding: 6
                font: FluTextStyle.Caption
            }
            FComboBox{
                id: copyConfig
                width: newNameBox.width
                model: ["Option 1", "Option 2", "Option 3"]
            }
        }
        Rectangle{
            id:layout_actions
            height: 68
            radius: 5
            color: FluTheme.dark ? Qt.rgba(32/255,32/255,32/255,1) : Qt.rgba(243/255,243/255,243/255,1)
            anchors{
                top:contextC.bottom
                topMargin: 12
                left: parent.left
                right: parent.right
            }
            RowLayout{
                anchors
                {
                    centerIn: parent
                    margins: spacing
                    fill: parent
                }
                spacing: 15
                FluButton{
                    id:neutral_btn
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: dialog.buttonFlags&FluContentDialog.NeutralButton
                    text: neutralText
                    onClicked: {
                        dialog.close()
                        neutralClicked()
                    }
                }
                FluButton{
                    id:negative_btn
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: dialog.buttonFlags&FluContentDialog.NegativeButton
                    text: negativeText
                    onClicked: {
                        dialog.close()
                        negativeClicked()
                    }
                }
                FluFilledButton{
                    id:positive_btn
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: dialog.buttonFlags&FluContentDialog.PositiveButton
                    text: positiveText
                    onClicked: {
                        dialog.close()
                        positiveClicked()
                    }
                }
            }
        }
    }

    negativeText:"取消"
    buttonFlags: FluContentDialog.NegativeButton | FluContentDialog.PositiveButton
    onNegativeClicked:{
        showSuccess("取消创建")
    }
    positiveText:"确定"
    onPositiveClicked:{
        showSuccess("已创建")
        add_config.copy(newNameBox.text, copyConfig.currentText)
        dialog.updateScriptItems()
    }

    onOpened: {
        newNameBox.text = add_config.generate_script_name()
        copyConfig.model = add_config.all_json_file()
    }
}

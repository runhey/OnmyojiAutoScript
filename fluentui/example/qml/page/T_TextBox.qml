import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import FluentUI
import "../component"

FluScrollablePage{

    title:"TextBox"
    leftPadding:10
    rightPadding:10
    bottomPadding:20
    spacing: 0

    FluArea{
        Layout.fillWidth: true
        height: 68
        paddings: 10
        Layout.topMargin: 20

        FluTextBox{
            Layout.topMargin: 20
            placeholderText: "单行输入框"
            Layout.preferredWidth: 300
            disabled:text_box_switch.selected
            anchors{
                verticalCenter: parent.verticalCenter
                left: parent.left
            }
        }

        Row{
            spacing: 5
            anchors{
                verticalCenter: parent.verticalCenter
                right: parent.right
            }
            FluToggleSwitch{
                id:text_box_switch
                Layout.alignment: Qt.AlignRight
                text:"Disabled"
            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluTextBox{
    placeholderText:"单行输入框"
}'
    }

    FluArea{
        Layout.fillWidth: true
        height: 68
        paddings: 10
        Layout.topMargin: 20

        FluPasswordBox{
            Layout.topMargin: 20
            placeholderText: "请输入密码"
            Layout.preferredWidth: 300
            disabled:password_box_switch.selected
            anchors{
                verticalCenter: parent.verticalCenter
                left: parent.left
            }
        }

        Row{
            spacing: 5
            anchors{
                verticalCenter: parent.verticalCenter
                right: parent.right
            }
            FluToggleSwitch{
                id:password_box_switch
                Layout.alignment: Qt.AlignRight
                text:"Disabled"
            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluPasswordBox{
    placeholderText:"请输入密码"
}'
    }


    FluArea{
        Layout.fillWidth: true
        height: 36+multiine_textbox.height
        paddings: 10
        Layout.topMargin: 20

        FluMultilineTextBox{
            id:multiine_textbox
            Layout.topMargin: 20
            placeholderText: "多行输入框"
            Layout.preferredWidth: 300
            disabled:text_box_multi_switch.selected
            anchors{
                verticalCenter: parent.verticalCenter
                left: parent.left
            }
        }

        Row{
            spacing: 5
            anchors{
                verticalCenter: parent.verticalCenter
                right: parent.right
            }
            FluToggleSwitch{
                id:text_box_multi_switch
                Layout.alignment: Qt.AlignRight
                text:"Disabled"
            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluMultilineTextBox{
    placeholderText:"多行输入框"
}'
    }


    FluArea{
        Layout.fillWidth: true
        height: 68
        paddings: 10
        Layout.topMargin: 20

        FluAutoSuggestBox{
            Layout.topMargin: 20
            placeholderText: "AutoSuggestBox"
            Layout.preferredWidth: 300
            items:generateRandomNames(100)
            disabled:text_box_suggest_switch.selected
            anchors{
                verticalCenter: parent.verticalCenter
                left: parent.left
            }
        }

        Row{
            spacing: 5
            anchors{
                verticalCenter: parent.verticalCenter
                right: parent.right
            }
            FluToggleSwitch{
                id:text_box_suggest_switch
                Layout.alignment: Qt.AlignRight
                text:"Disabled"
            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluAutoSuggestBox{
    placeholderText:"AutoSuggestBox"
}'
    }


    function generateRandomNames(numNames) {
        const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
        const names = [];
        function generateRandomName() {
            const nameLength = Math.floor(Math.random() * 5) + 4;
            let name = '';
            for (let i = 0; i < nameLength; i++) {
                const letterIndex = Math.floor(Math.random() * 26);
                name += alphabet.charAt(letterIndex);
            }
            return name;
        }
        for (let i = 0; i < numNames; i++) {
            const name = generateRandomName();
            names.push({title:name});
        }
        return names;
    }


}

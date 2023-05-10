import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import FluentUI

FluWindow {

    id:window
    title:"登录"
    width: 400
    height: 400
    minimumWidth: 400
    minimumHeight: 400
    maximumWidth: 400
    maximumHeight: 400

    onInitArgument:
        (argument)=>{
            textbox_uesrname.updateText(argument.username)
            textbox_password.focus =  true
        }

    FluAppBar{
        id:appbar
        title:"登录"
        width:parent.width
    }

    ColumnLayout{
        anchors{
            left: parent.left
            right: parent.right
            verticalCenter: parent.verticalCenter
        }

        FluAutoSuggestBox{
            id:textbox_uesrname
            items:[{title:"Admin"},{title:"User"}]
            placeholderText: "请输入账号"
            Layout.preferredWidth: 260
            Layout.alignment: Qt.AlignHCenter
        }

        FluTextBox{
            id:textbox_password
            Layout.topMargin: 20
            Layout.preferredWidth: 260
            placeholderText: "请输入密码"
            echoMode:TextInput.Password
            Layout.alignment: Qt.AlignHCenter
        }

        FluFilledButton{
            text:"登录"
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 20
            onClicked:{
                if(textbox_password.text === ""){
                    showError("请随便输入一个密码")
                    return
                }
                onResult({password:textbox_password.text})
                window.close()
            }
        }

    }



}

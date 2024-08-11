import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls
import FluentUI
import "../component"

FluScrollablePage{

    property string password: ""
    property var loginPageRegister: registerForWindowResult("/login")

    title:"MultiWindow"
    leftPadding:10
    rightPadding:10
    bottomPadding:20
    spacing: 0

    Connections{
        target: loginPageRegister
        function onResult(data)
        {
            password = data.password
        }
    }

    FluArea{
        Layout.fillWidth: true
        height: 86
        paddings: 10
        Layout.topMargin: 20
        Column{
            spacing: 15
            anchors{
                verticalCenter: parent.verticalCenter
                left: parent.left
            }
            FluText{
                text:"<font color='red'>Standard</font>模式窗口，每次都会创建新窗口"
            }
            FluButton{
                text:"点击创建窗口"
                onClicked: {
                    FluApp.navigate("/standardWindow")
                }
            }
        }
    }

    FluArea{
        Layout.fillWidth: true
        height: 86
        paddings: 10
        Layout.topMargin: 10
        Column{
            spacing: 15
            anchors{
                verticalCenter: parent.verticalCenter
                left: parent.left
            }
            FluText{
                text:"<font color='red'>SingleTask</font>模式窗口，如果窗口存在，这激活该窗口"
                textFormat: Text.RichText
            }
            FluButton{
                text:"点击创建窗口"
                onClicked: {
                    FluApp.navigate("/singleTaskWindow")
                }
            }
        }
    }

    FluArea{
        Layout.fillWidth: true
        height: 86
        paddings: 10
        Layout.topMargin: 10
        Column{
            spacing: 15
            anchors{
                verticalCenter: parent.verticalCenter
                left: parent.left
            }
            FluText{
                text:"<font color='red'>SingleInstance</font>模式窗口，如果窗口存在，则销毁窗口，然后新建窗口"
            }
            FluButton{
                text:"点击创建窗口"
                onClicked: {
                    FluApp.navigate("/singleInstanceWindow")
                }
            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluWindow{
  //launchMode: FluWindow.Standard
  //launchMode: FluWindow.SingleTask
     launchMode: FluWindow.SingleInstance
}
'
    }


    FluArea{
        Layout.fillWidth: true
        height: 100
        paddings: 10
        Layout.topMargin: 20
        Column{
            spacing: 15
            anchors{
                verticalCenter: parent.verticalCenter
                left: parent.left
            }
            FluText{
                text:"页面跳转，不携带任何参数"
            }
            FluButton{
                text:"点击跳转"
                onClicked: {
                    FluApp.navigate("/about")
                }
            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluButton{
    text:"点击跳转"
    onClicked: {
        FluApp.navigate("/about")
    }
}
'
    }

    FluArea{
        Layout.fillWidth: true
        height: 130
        paddings: 10
        Layout.topMargin: 20

        Column{
            spacing: 15
            anchors{
                verticalCenter: parent.verticalCenter
                left: parent.left
            }
            FluText{
                text:"页面跳转，并携带参数用户名：zhuzichu"
            }
            FluButton{
                text:"点击跳转到登录"
                onClicked: {
                    loginPageRegister.launch({username:"zhuzichu"})
                }
            }
            FluText{
                text:"登录窗口返回过来的密码->"+password
            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'property var loginPageRegister: registerForWindowResult("/login")

Connections{
    target: loginPageRegister
    function onResult(data)
    {
        password = data.password
    }
}

FluButton{
    text:"点击跳转"
    onClicked: {
        loginPageRegister.launch({username:"zhuzichu"})
    }
}
'
    }

}

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import FluentUI
import Controller
import QtQuick.Dialogs

FluWindow {

    title:"ChatGPT"
    width: 680
    height: 600
    minimumWidth: 500
    minimumHeight: 600

    onInitArgument:
        (argument)=>{
            scrollview.focus = true
        }

    ChatController{
        id:controller

        onResponseDataChanged: {
            appendMessage(false,responseData)
        }

    }

    ListModel{
        id:model_message
        ListElement{
            isMy:false
            text:"欢迎使用ChatGPT"
        }
        ListElement{
            isMy:true
            text:"好的，3Q"
        }
    }

    FluAppBar{
        id:appbar
        title:"ChatGPT"
        width:parent.width
    }

    Component{
        id:com_text
        TextEdit {
            id:item_text
            text: message
            wrapMode: Text.WrapAnywhere
            readOnly: true
            selectByMouse: true
            selectByKeyboard: true
            selectedTextColor: Qt.rgba(51,153,255,1)
            color:FluColors.Black
            selectionColor: {
                if(FluTheme.dark){
                    return FluTheme.primaryColor.lighter
                }else{
                    return FluTheme.primaryColor.dark
                }
            }
            width: Math.min(list_message.width-200,600,implicitWidth)
            TapHandler{
                acceptedButtons: Qt.RightButton
                onTapped: {
                    menu_item.showMenu(item_text.selectedText)
                }
            }
        }
    }

    FluArea{
        id:layout_content
        anchors{
            top: appbar.bottom
            left: parent.left
            right: parent.right
            bottom: layout_bottom.top
            margins: 10
        }
        color: FluTheme.dark ? Qt.rgba(39/255,39/255,39/255,1) : Qt.rgba(245/255,245/255,245/255,1)
        ListView{
            id:list_message
            anchors.fill: parent
            model:model_message
            clip: true
            ScrollBar.vertical: FluScrollBar {}
            preferredHighlightBegin: 0
            preferredHighlightEnd: 0
            highlightMoveDuration: 0
            header:Item{
                width: list_message.width
                height:20
            }
            footer:Item{
                width: list_message.width
                height:20
            }
            delegate: Item{
                width: ListView.view.width
                height: childrenRect.height

                FluRectangle{
                    id:item_avatar
                    width: 30
                    height: 30
                    radius:[15,15,15,15]
                    anchors{
                        right: isMy ? parent.right : undefined
                        rightMargin: isMy ? 20 : undefined
                        left: isMy ? undefined : parent.left
                        leftMargin: isMy ? undefined : 20
                        top:parent.top
                    }
                    Image {
                        asynchronous: true
                        anchors.fill: parent
                        sourceSize: Qt.size(100,100)
                        source: isMy ? "qrc:/example/res/svg/avatar_2.svg" : "qrc:/example/res/image/logo_openai.png"
                    }
                }

                Rectangle{
                    id:item_layout_content
                    color: isMy ? "#FF95EC69" : "#FFFFFF"
                    width: item_msg_loader.width+10
                    height: item_msg_loader.height+10
                    radius: 3
                    anchors{
                        top: item_avatar.top
                        right: isMy ? item_avatar.left : undefined
                        rightMargin: isMy ? 10 : undefined
                        left: isMy ? undefined : item_avatar.right
                        leftMargin: isMy ? undefined : 10

                    }

                    Loader{
                        id:item_msg_loader
                        property var message: model.text
                        anchors.centerIn: parent
                        sourceComponent: com_text
                    }
                }


                Item{
                    id:item_layout_bottom
                    width: parent.width
                    anchors.top: item_layout_content.bottom
                    height: 20
                }
            }
        }
    }

    FluArea{
        id:layout_bottom
        height: 90
        anchors{
            bottom: parent.bottom
            bottomMargin: 10
            left: parent.left
            right: parent.right
            leftMargin: 10
            rightMargin: 10
        }


        ScrollView{
            id:scrollview
            anchors{
                bottom: parent.bottom
                left: parent.left
                right: button_send.left
                bottomMargin: 10
                leftMargin: 10
                rightMargin: 10
            }
            height: Math.min(textbox.implicitHeight,64)
            FluMultilineTextBox{
                id:textbox
                focus:true
                placeholderText: "请输入消息"
            }
        }

        FluFilledButton{
            id:button_send
            text:controller.isLoading ? timer_loading.loadingText :"发送"
            anchors{
                bottom: parent.bottom
                right: parent.right
                bottomMargin: 10
                rightMargin: 10
            }
            width: 60
            disabled: controller.isLoading
            onClicked:{
                var text = textbox.text
                appendMessage(true,text)
                controller.sendMessage(text)
                textbox.clear()
            }

            Timer{
                id:timer_loading
                property int count : 0
                property string loadingText : ""
                interval: 500
                running: controller.isLoading
                repeat: true
                onTriggered: {
                    switch(count%3){
                    case 0:
                        loadingText = "."
                        break
                    case 1:
                        loadingText = ".."
                        break
                    case 2:
                        loadingText = "..."
                        break
                    default:
                        loadingText = ""
                        break
                    }
                    count++
                }
            }

        }
    }

    FluMenu{
        id:menu_item
        focus: false
        property string selectedText: ""
        FluMenuItem{
            text:"复制"
            onClicked: {
                controller.clipText(menu_item.selectedText)
                showSuccess("复制成功")
            }
        }
        function showMenu(text){
            menu_item.selectedText = text
            menu_item.popup()
        }
    }

    function appendMessage(isMy,text){
        model_message.append({isMy:isMy,text:text})
        list_message.positionViewAtEnd()
    }

}

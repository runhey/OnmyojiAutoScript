import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import FluentUI


FluScrollablePage{
    leftPadding:10
    rightPadding:10
    bottomPadding:20
    spacing: 6

    FluText{
        text: '消息推送测试'
        font: FluTextStyle.Title
    }
    FluArea{
        Layout.fillWidth: true
        height: 500
        paddings: 10

        ColumnLayout{
            id: yyyyy
            spacing: 10
            anchors{
                top: parent.top
                left: parent.left
            }
            width: parent.width
            property int conentWith: 300
            FluText{
                text: '推送配置'
                font: FluTextStyle.BodyStrong
            }
            FluMultilineTextBox{
                id: notifyConfig
                implicitWidth: yyyyy.conentWith
                placeholderText: 'Please input your notify config'
                text: 'provider: null'

            }
            FluText{
                text: '请翻阅文档[消息推送]进行填写上方的参数设置。 \n请填写下方的Title和Conent后点击发送消息测试 \n注意这并不会在当前界面有任何反馈'
            }
            FluText{
                text: '主题'
                font: FluTextStyle.BodyStrong
            }
            FluTextBox{
                id: notifyTitle
                implicitWidth: yyyyy.conentWith
                placeholderText: 'Title'
                text: 'TEST TITLE'
            }
            FluText{
                text: '内容'
                font: FluTextStyle.BodyStrong
            }
            FluMultilineTextBox{
                id: notifyConent
                implicitWidth: yyyyy.conentWith
                placeholderText: 'Conent'
                text: 'TEST conent'
            }
            FluFilledButton{
                id: testSend
                implicitWidth: yyyyy.conentWith
                text: '测试发送'
                onClicked: {
                    const result = utils.test_notify(notifyConfig.text, notifyTitle.text, notifyConent.text)
                    console.debug(result)
                    if(result === "true"){
                        showSuccess('Successful')
                    }else{
                        showError('Failure')
                    }
                }
            }
        }
    }
}

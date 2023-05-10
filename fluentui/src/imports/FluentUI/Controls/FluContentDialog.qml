import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Window
import FluentUI

Popup {
    id: popup

    property string title: "Title"
    property string message: "Message"
    property string neutralText: "Neutral"
    property string negativeText: "Negative"
    property string positiveText: "Positive"
    signal neutralClicked
    signal negativeClicked
    signal positiveClicked
    enum ButtonFlag{
        NegativeButton=1
        ,NeutralButton=2
        ,PositiveButton=4
    }
    property int buttonFlags: FluContentDialog.NegativeButton | FluContentDialog.PositiveButton
    property var minWidth: {
        if(Window.window==null)
            return 400
        return  Math.min(Window.window.width,400)
    }
    modal:true
    anchors.centerIn: Overlay.overlay
    closePolicy: Popup.CloseOnEscape
    background:Item{}

    enter: Transition {
        reversible: true
        NumberAnimation {
            properties: "opacity,scale"
            from:0
            to:1
            duration: 167
            easing.type: Easing.BezierSpline
            easing.bezierCurve: [ 0, 0, 0, 1 ]
        }
    }
    exit:Transition {
        NumberAnimation {
            properties: "opacity,scale"
            from:1
            to:0
            duration: 167
            easing.type: Easing.BezierSpline
            easing.bezierCurve: [ 1, 0, 0, 0 ]
        }
    }
    contentItem: Rectangle {
        id:layout_content
        implicitWidth:minWidth
        implicitHeight: text_title.height + text_message.height + layout_actions.height
        color:FluTheme.dark ? Qt.rgba(45/255,45/255,45/255,1) : Qt.rgba(249/255,249/255,249/255,1)
        radius:5

        FluShadow{
            radius: 5
        }

        FluText{
            id:text_title
            font: FluTextStyle.TitleLarge
            text:title
            topPadding: 20
            leftPadding: 20
            rightPadding: 20
            wrapMode: Text.WrapAnywhere
            anchors{
                top:parent.top
                left: parent.left
                right: parent.right
            }
        }

        FluText{
            id:text_message
            font: FluTextStyle.Body
            wrapMode: Text.WrapAnywhere
            text:message
            topPadding: 14
            leftPadding: 20
            rightPadding: 20
            bottomPadding: 14
            anchors{
                top:text_title.bottom
                left: parent.left
                right: parent.right
            }
        }

        Rectangle{
            id:layout_actions
            height: 68
            radius: 5
            color: FluTheme.dark ? Qt.rgba(32/255,32/255,32/255,1) : Qt.rgba(243/255,243/255,243/255,1)
            anchors{
                top:text_message.bottom
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
                    visible: popup.buttonFlags&FluContentDialog.NeutralButton
                    text: neutralText
                    onClicked: {
                        popup.close()
                        neutralClicked()
                    }
                }

                FluButton{
                    id:negative_btn
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: popup.buttonFlags&FluContentDialog.NegativeButton
                    text: negativeText
                    onClicked: {
                        popup.close()
                        negativeClicked()
                    }
                }

                FluFilledButton{
                    id:positive_btn
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: popup.buttonFlags&FluContentDialog.PositiveButton
                    text: positiveText
                    onClicked: {
                        popup.close()
                        positiveClicked()
                    }
                }
            }
        }
    }
}

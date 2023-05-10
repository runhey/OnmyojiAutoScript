import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import FluentUI

FluContentPage {

    title: "Typography"
    property real textScale: 1
    leftPadding:10
    rightPadding:10
    bottomPadding:20

    Component.onCompleted: {
        slider.seek(0)
    }

    FluArea{
        anchors{
            top:parent.top
            left: parent.left
            right: parent.right
            bottom: parent.bottom
            topMargin: 20
        }
        paddings: 10
        ColumnLayout{
            spacing: 0
            scale: textScale
            transformOrigin: Item.TopLeft
            FluText{
                id:text_Display
                text:"Display"
                padding: 0
                font: FluTextStyle.Display
            }
            FluText{
                id:text_TitleLarge
                text:"Title Large"
                padding: 0
                font: FluTextStyle.TitleLarge
            }
            FluText{
                id:text_Title
                text:"Title"
                padding: 0
                font: FluTextStyle.Title
            }
            FluText{
                id:text_Subtitle
                text:"Subtitle"
                padding: 0
                font: FluTextStyle.Subtitle
            }
            FluText{
                id:text_BodyStrong
                text:"Body Strong"
                padding: 0
                font: FluTextStyle.BodyStrong
            }
            FluText{
                id:text_Body
                text:"Body"
                padding: 0
                font: FluTextStyle.Body
            }
            FluText{
                id:text_Caption
                text:"Caption"
                padding: 0
                font: FluTextStyle.Caption
            }
        }

        FluSlider{
            id:slider
            vertical:true
            anchors{
                right: parent.right
                rightMargin: 45
                top: parent.top
                topMargin: 30
            }
            onValueChanged:{
                textScale = 1+value/100
            }
        }
    }
}

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Templates as T
import FluentUI

T.ItemDelegate {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding,
                             implicitIndicatorHeight + topPadding + bottomPadding)

    padding: 12
    spacing: 8

    icon.width: 24
    icon.height: 24
    icon.color: control.palette.text

    contentItem: FluText {
        text: control.text
        font: control.font
    }

    background: Rectangle {
        implicitWidth: 100
        implicitHeight: 40
        color:{
            if(FluTheme.dark){
                return Qt.rgba(1,1,1,0.05)
            }else{
                return Qt.rgba(0,0,0,0.05)
            }
        }
        visible: control.down || control.highlighted || control.visualFocus
    }
}

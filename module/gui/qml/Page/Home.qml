import QtQuick
import QtQuick.Layouts
import FluentUI

FluScrollablePage{
    spacing: 6

    Image {
        id: name
        Layout.preferredHeight: 40
        Layout.preferredWidth: 40
        Layout.alignment: Qt.AlignHCenter
        source: "qrc:/res/icon.png"
    }
    FluText{
//        Layout.fillWidth: true
        text: "OAS是一款致力于全自动化的阴阳师脚本"
        font: FluTextStyle.Title
        Layout.alignment: Qt.AlignHCenter
    }
    FluText{
        text: "https://github.com/runhey/OnmyojiAutoScript"
        font: FluTextStyle.Body
        Layout.alignment: Qt.AlignHCenter
    }

}

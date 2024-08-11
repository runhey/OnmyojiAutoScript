import QtQuick
import QtQuick.Layouts
import FluentUI

FluScrollablePage{
    spacing: 12

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
        text: "OAS 是一款免费开源软件，如果你在任何渠道付费购买了OAS，请退款。"
        font: FluTextStyle.BodyStrong
        Layout.alignment: Qt.AlignLeft
    }
    FluText{
        text: "OAS 的项目地址 https://github.com/runhey/OnmyojiAutoScript"
        font: FluTextStyle.BodyStrong
        Layout.alignment: Qt.AlignLeft
    }
    FluText{
        text: "OAS 是基于 Alas 的架构上开发，Alas 是碧蓝航线的自动化脚本"
        font: FluTextStyle.BodyStrong
        Layout.alignment: Qt.AlignLeft
    }
    FluText{
        text: "Alas 的项目地址 https://github.com/LmeSzinc/AzurLaneAutoScript"
        font: FluTextStyle.BodyStrong
        Layout.alignment: Qt.AlignLeft
    }
    FluText{
        text: "SRC: 星铁速溶茶，崩坏：星穹铁道脚本，基于下一代Alas框架"
        font: FluTextStyle.BodyStrong
        Layout.alignment: Qt.AlignLeft
    }
    FluText{
        text: "SRC 的项目地址 https://github.com/LmeSzinc/StarRailCopilot"
        font: FluTextStyle.BodyStrong
        Layout.alignment: Qt.AlignLeft
    }

}

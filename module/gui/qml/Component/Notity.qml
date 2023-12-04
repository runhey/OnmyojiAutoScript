import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls
import FluentUI

FluContentDialog{
    title:"全新GUI"
    message:"我们打算在2024.1.1全面切换新到GUI： OASX"
    negativeText:"了解"
    positiveText:"详情"
    onPositiveClicked:{
        Qt.openUrlExternally('https://github.com/runhey/OASX')
    }
}

import QtQuick
import QtQuick.Controls
import FluentUI

FluObject {
    readonly property string key : FluTools.uuid()
    property string title
    property var icon
    property Component cusIcon
    property bool isExpand: false
    property var parent
    property int idx
}

import QtQuick
import QtQuick.Controls
import FluentUI

QtObject {
    readonly property string key : FluTools.uuid()
    readonly property int flag : 0
    property string title
    property int order : 0
    property int icon
    property Component cusIcon
    property bool recentlyAdded: false
    property bool recentlyUpdated: false
    property string desc
    property var image
    property var parent
    property int idx
    signal tap
    property var tapFunc
}

import QtQuick
import QtQuick.Controls
import FluentUI

QtObject {
    readonly property string key : FluTools.uuid()
    property string title
    property var parent
    property int idx
}

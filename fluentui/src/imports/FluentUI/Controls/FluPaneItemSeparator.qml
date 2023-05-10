import QtQuick
import QtQuick.Controls
import FluentUI

QtObject {
    readonly property string key : FluTools.uuid()
    property var parent
    property int idx
}

import QtQuick
import QtQuick.Controls
import FluentUI

FluMenu{

    property string cutText : "剪切"
    property string copyText : "复制"
    property string pasteText : "粘贴"
    property string selectAllText : "全选"
    property var inputItem

    id:menu
    focus:false
    enableAnimation:false

    onVisibleChanged: {
        if(visible){
            inputItem.forceActiveFocus()
        }
    }

    Connections{
        target: inputItem
        function onTextChanged() {
            menu.close()
        }
    }

    FluMenuItem{
        text: cutText
        visible: inputItem.selectedText !== "" && !inputItem.readOnly
        onClicked: {
            inputItem.cut()
        }
    }

    FluMenuItem{
        text: copyText
        visible: inputItem.selectedText !== ""
        onClicked: {
            inputItem.copy()
        }
    }
    FluMenuItem{
        text: pasteText
        visible: inputItem.canPaste
        onClicked: {
            inputItem.paste()
        }
    }
    FluMenuItem{
        text: selectAllText
        visible: inputItem.text !== ""
        onClicked: {
            inputItem.selectAll()
        }
    }
}

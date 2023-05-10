import QtQuick
import QtQuick.Controls
import QtQuick.Window
import FluentUI

MouseArea {

    property int border: 4
    property var window: Window.window
    property bool fixedSize: {
        if(window == null)
            return true
        if(window.visibility === Window.Maximized || window.visibility === Window.FullScreen){
            return true
        }
        return (window.minimumWidth === window.maximumWidth && window.minimumHeight === window.maximumHeight)
    }

    anchors.fill: parent
    acceptedButtons: Qt.LeftButton
    hoverEnabled: true
    preventStealing: true
    propagateComposedEvents: true
    z: -65535

    onPressed :
        (mouse)=> {
            if (fixedSize) {
                return;
            }

            let e = 0;
            if (ptInRect(0,0,border,border, mouse.x, mouse.y)) {
                e = Qt.TopEdge | Qt.LeftEdge;
                window.startSystemResize(e);
                return;
            }

            if (ptInRect(border,0,window.width-border*2,border, mouse.x, mouse.y)) {
                e = Qt.TopEdge;
                window.startSystemResize(e);
                return;
            }

            if (ptInRect(window.width-border,0,border,border, mouse.x, mouse.y)) {
                e = Qt.TopEdge | Qt.RightEdge;
                window.startSystemResize(e);
                return;
            }

            if (ptInRect(window.width-border,border,border,window.height-border*2, mouse.x, mouse.y)) {
                e = Qt.RightEdge;
                window.startSystemResize(e);
                return;
            }

            if (ptInRect(window.width-border,window.height-border,border,border, mouse.x, mouse.y)) {
                e = Qt.BottomEdge | Qt.RightEdge;
                window.startSystemResize(e);
                return;
            }

            if (ptInRect(border,window.height-border,window.width-border*2,border, mouse.x, mouse.y)) {
                e = Qt.BottomEdge;
                window.startSystemResize(e);
                return;
            }

            if (ptInRect(0,window.height-border,border,border, mouse.x, mouse.y)) {
                e = Qt.BottomEdge | Qt.LeftEdge;
                window.startSystemResize(e);
                return;
            }

            if (ptInRect(0,border,border , window.height-border*2, mouse.x, mouse.y)) {
                e = Qt.LeftEdge;
                window.startSystemResize(e);
                return;
            }
        }

    onPositionChanged:
        (mouse)=> {
            if (fixedSize) {
                cursorShape = Qt.ArrowCursor;
                return;
            }
            if (ptInRect(0,0,border,border, mouse.x, mouse.y)) {
                cursorShape = Qt.SizeFDiagCursor;
                return;
            }

            if (ptInRect(border,0,window.width-border*2,border, mouse.x, mouse.y)) {
                cursorShape = Qt.SizeVerCursor;
                return;
            }

            if (ptInRect(window.width-border,0,border,border, mouse.x, mouse.y)) {
                cursorShape = Qt.SizeBDiagCursor;
                return;
            }

            if (ptInRect(window.width-border,border,border,window.height-border*2, mouse.x, mouse.y)) {
                cursorShape = Qt.SizeHorCursor;
                return;
            }

            if (ptInRect(window.width-border,window.height-border,border,border, mouse.x, mouse.y)) {
                cursorShape = Qt.SizeFDiagCursor;
                return;
            }

            if (ptInRect(border,window.height-border,window.width-border*2,border, mouse.x, mouse.y)) {
                cursorShape = Qt.SizeVerCursor;
                return;
            }

            if (ptInRect(0,window.height-border,border,border, mouse.x, mouse.y)) {
                cursorShape = Qt.SizeBDiagCursor;
                return;
            }

            if (ptInRect(0,border,border, window.height-border*2, mouse.x, mouse.y)) {
                cursorShape = Qt.SizeHorCursor;
                return;
            }

            cursorShape = Qt.ArrowCursor;
        }

    onExited: {
        cursorShape = Qt.ArrowCursor;
    }

    function ptInRect(rcx,rcy,rcwidth,rcheight, x, y)
    {
        if ((rcx <= x && x <= (rcx + rcwidth)) &&
                (rcy <= y && y <= (rcy + rcheight))) {
            return true;
        }
        return false;
    }

}

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "Content"

Rectangle {
    id: colorPicker
    property color colorValue: "transparent"
    property bool enableAlphaChannel: true
    property bool enableDetails: true
    property int colorHandleRadius : 8
    property color _changingColorValue : _hsla(hueSlider.value, sbPicker.saturation,sbPicker.brightness, alphaSlider.value)
    on_ChangingColorValueChanged: {
        colorValue = _changingColorValue
    }

    signal colorChanged(color changedColor)

    implicitWidth: picker.implicitWidth
    implicitHeight: picker.implicitHeight
    color: "#00000000"
    clip: true


    RowLayout {
        id: picker
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.rightMargin: colorHandleRadius
        anchors.bottom: parent.bottom
        spacing: 0


        SBPicker {
            id: sbPicker
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumWidth: 200
            Layout.minimumHeight: 200
            hueColor: {
                var v = 1.0-hueSlider.value
                if(0.0 <= v && v < 0.16) {
                    return Qt.rgba(1.0, 0.0, v/0.16, 1.0)
                } else if(0.16 <= v && v < 0.33) {
                    return Qt.rgba(1.0 - (v-0.16)/0.17, 0.0, 1.0, 1.0)
                } else if(0.33 <= v && v < 0.5) {
                    return Qt.rgba(0.0, ((v-0.33)/0.17), 1.0, 1.0)
                } else if(0.5 <= v && v < 0.76) {
                    return Qt.rgba(0.0, 1.0, 1.0 - (v-0.5)/0.26, 1.0)
                } else if(0.76 <= v && v < 0.85) {
                    return Qt.rgba((v-0.76)/0.09, 1.0, 0.0, 1.0)
                } else if(0.85 <= v && v <= 1.0) {
                    return Qt.rgba(1.0, 1.0 - (v-0.85)/0.15, 0.0, 1.0)
                } else {
                    return "red"
                }
            }
        }

        Item {
            id: huePicker
            width: 12
            Layout.fillHeight: true
            Layout.topMargin: colorHandleRadius
            Layout.bottomMargin: colorHandleRadius

            Rectangle {
                anchors.fill: parent
                id: colorBar
                gradient: Gradient {
                    GradientStop { position: 1.0;  color: "#FF0000" }
                    GradientStop { position: 0.85; color: "#FFFF00" }
                    GradientStop { position: 0.76; color: "#00FF00" }
                    GradientStop { position: 0.5;  color: "#00FFFF" }
                    GradientStop { position: 0.33; color: "#0000FF" }
                    GradientStop { position: 0.16; color: "#FF00FF" }
                    GradientStop { position: 0.0;  color: "#FF0000" }
                }
            }
            ColorSlider {
                id: hueSlider; anchors.fill: parent
            }
        }

        Item {
            id: alphaPicker
            visible: enableAlphaChannel
            width: 12
            Layout.leftMargin: 4
            Layout.fillHeight: true
            Layout.topMargin: colorHandleRadius
            Layout.bottomMargin: colorHandleRadius
            Checkerboard { cellSide: 4 }
            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#FF000000" }
                    GradientStop { position: 1.0; color: "#00000000" }
                }
            }
            ColorSlider {
                id: alphaSlider; anchors.fill: parent
            }
        }

        Column {
            id: detailColumn
            Layout.leftMargin: 4
            Layout.fillHeight: true
            Layout.topMargin: colorHandleRadius
            Layout.bottomMargin: colorHandleRadius
            Layout.alignment: Qt.AlignRight
            visible: enableDetails

            PanelBorder {
                width: parent.width
                height: 30
                visible: enableAlphaChannel
                Checkerboard { cellSide: 5 }
                Rectangle {
                    width: parent.width; height: 30
                    border.width: 1; border.color: "black"
                    color: colorPicker.colorValue
                }
            }

            Item {
                width: parent.width
                height: 1
            }


            PanelBorder {
                id: colorEditBox
                height: 15; width: parent.width
                TextInput {
                    anchors.fill: parent
                    color: "#AAAAAA"
                    selectionColor: "#FF7777AA"
                    font.pixelSize: 11
                    maximumLength: 9
                    focus: false
                    text: _fullColorString(colorPicker.colorValue, alphaSlider.value)
                    selectByMouse: true
                }
            }

            Item {
                width: parent.width
                height: 8
            }

            Column {
                width: parent.width
                spacing: 1
                NumberBox { caption: "H:"; value: hueSlider.value.toFixed(2) }
                NumberBox { caption: "S:"; value: sbPicker.saturation.toFixed(2) }
                NumberBox { caption: "B:"; value: sbPicker.brightness.toFixed(2) }
            }

            Item {
                width: parent.width
                height: 8
            }

            Column {
                width: parent.width
                spacing: 1
                NumberBox {
                    caption: "R:"
                    value: _getChannelStr(colorPicker.colorValue, 0)
                    min: 0; max: 255
                }
                NumberBox {
                    caption: "G:"
                    value: _getChannelStr(colorPicker.colorValue, 1)
                    min: 0; max: 255
                }
                NumberBox {
                    caption: "B:"
                    value: _getChannelStr(colorPicker.colorValue, 2)
                    min: 0; max: 255
                }
            }

            Item{
                width: parent.width
                height: 1
            }

            NumberBox {
                visible: enableAlphaChannel
                caption: "A:"; value: Math.ceil(alphaSlider.value*255)
                min: 0; max: 255
            }
        }
    }

    function _hsla(h, s, b, a) {
        var lightness = (2 - s)*b
        var satHSL = s*b/((lightness <= 1) ? lightness : 2 - lightness)
        lightness /= 2

        var c = Qt.hsla(h, satHSL, lightness, a)

        colorChanged(c)

        return c
    }

    function _rgb(rgb, a) {

        var c = Qt.rgba(rgb.r, rgb.g, rgb.b, a)

        colorChanged(c)

        return c
    }

    function _fullColorString(clr, a) {
        return "#" + ((Math.ceil(a*255) + 256).toString(16).substr(1, 2) + clr.toString().substr(1, 6)).toUpperCase()
    }

    function _getChannelStr(clr, channelIdx) {
        return parseInt(clr.toString().substr(channelIdx*2 + 1, 2), 16)
    }

    function setColor(color) {
        var c = Qt.tint(color, "transparent")
        alphaSlider.setValue(c.a)
        colorPicker.colorValue = c
    }
}

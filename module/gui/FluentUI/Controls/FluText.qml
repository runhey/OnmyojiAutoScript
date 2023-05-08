import QtQuick
import QtQuick.Controls
import FluentUI

Text {

    enum FontStyle {
        Display,
        TitleLarge,
        Title,
        SubTitle,
        BodyStrong,
        Body,
        Caption
    }

    property int fontStyle: FluText.Body
    property color textColor: FluTheme.dark ? FluColors.White : FluColors.Grey220
    property int pixelSize : FluTheme.textSize

    id:text
    color: textColor
    renderType: FluTheme.nativeText ? Text.NativeRendering : Text.QtRendering
    font.bold: {
        switch (fontStyle) {
        case FluText.Display:
            return true
        case FluText.TitleLarge:
            return true
        case FluText.Title:
            return true
        case FluText.SubTitle:
            return true
        case FluText.BodyStrong:
            return true
        case FluText.Body:
            return false
        case FluText.Caption:
            return false
        default:
            return false
        }
    }
    font.pixelSize: {
        switch (fontStyle) {
        case FluText.Display:
            return text.pixelSize * 4.857
        case FluText.TitleLarge:
            return text.pixelSize * 2.857
        case FluText.Title:
            return text.pixelSize * 2
        case FluText.SubTitle:
            return text.pixelSize * 1.428
        case FluText.Body:
            return text.pixelSize * 1.0
        case FluText.BodyStrong:
            return text.pixelSize * 1.0
        case FluText.Caption:
            return text.pixelSize * 0.857
        default:
            return text.pixelSize * 1.0
        }
    }

}

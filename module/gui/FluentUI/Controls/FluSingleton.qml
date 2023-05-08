import QtQuick
import QtQuick.Controls
import FluentUI

QtObject {

    id:control

    Component.onCompleted: {
        FluApp.setFluApp(FluApp)
        FluApp.setFluColors(FluColors)
        FluApp.setFluTheme(FluTheme)
        FluApp.setFluTools(FluTools)
    }

}

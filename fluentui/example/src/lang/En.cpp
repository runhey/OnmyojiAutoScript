#include "En.h"

En::En(QObject *parent)
    : Lang{parent}
{
    setObjectName("En");
    home("Home");
    basic_input("Basic Input");
    form("Form");
    surface("Surfaces");
    popus("Popus");
    navigation("Navigation");
    theming("Theming");
    media("Media");
    dark_mode("Dark Mode");
    sys_dark_mode("Sync with system");
    search("Search");
    about("About");
    settings("Settings");
    locale("Locale");
    navigation_view_display_mode("NavigationView Display Mode");
}

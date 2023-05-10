#include "FluApp.h"

#include <QQmlEngine>
#include <QGuiApplication>
#include <QQmlContext>
#include <QQuickItem>
#include <QTimer>
#include <QUuid>
#include <QFontDatabase>
#include <QClipboard>
#include "Def.h"
#ifdef Q_OS_WIN
#pragma comment(lib, "Dwmapi.lib")
#pragma comment(lib, "User32.lib")
#include <dwmapi.h>
#include <Windows.h>
#include <windowsx.h>
static bool isCompositionEnabled()
{
    BOOL composition_enabled = FALSE;
    bool success = ::DwmIsCompositionEnabled(&composition_enabled) == S_OK;
    return composition_enabled && success;
}
#endif

FluApp* FluApp::fluApp = nullptr;

FluTheme* FluApp::fluTheme = nullptr;

FluColors* FluApp::fluColors = nullptr;

FluTools* FluApp::fluTools = nullptr;

FluApp::FluApp(QObject *parent)
    : QObject{parent}
{
    QFontDatabase::addApplicationFont(":/FluentUI/Font/Segoe_Fluent_Icons.ttf");
}

FluApp::~FluApp(){
    if (nativeEvent != Q_NULLPTR) {
        delete nativeEvent;
        nativeEvent = Q_NULLPTR;
    }
}

void FluApp::setFluApp(FluApp* val){
    FluApp::fluApp = val;
}

void FluApp::setFluTheme(FluTheme* val){
    FluApp::fluTheme = val;
}

void FluApp::setFluColors(FluColors* val){
    FluApp::fluColors = val;
}

void FluApp::setFluTools(FluTools* val){
    FluApp::fluTools = val;
}

void FluApp::init(QQuickWindow *window){
    this->appWindow = window;
    QQmlEngine *engine = qmlEngine(appWindow);
    QQmlComponent component(engine, ":/FluentUI/Controls/FluSingleton.qml");
    component.create();
    nativeEvent = new NativeEventFilter();
    qApp->installNativeEventFilter(nativeEvent);
}

void FluApp::run(){
#ifdef Q_OS_WIN
    if(!isCompositionEnabled()){
        fluTheme->frameless(false);
    }
#endif
    navigate(initialRoute());
}

void FluApp::navigate(const QString& route,const QJsonObject& argument,FluRegister* fluRegister){
    if(!routes().contains(route)){
        qErrnoWarning("没有找到当前路由");
        return;
    }
    QQmlEngine *engine = qmlEngine(appWindow);
    QQmlComponent component(engine, routes().value(route).toString());
    QVariantMap properties;
    properties.insert("route",route);
    if(fluRegister){
        properties.insert("pageRegister",QVariant::fromValue(fluRegister));
    }
    properties.insert("argument",argument);
    QQuickWindow *view=nullptr;
    for (auto& pair : wnds) {
        QString r =  pair->property("route").toString();
        if(r == route){
            view = pair;
            break;
        }
    }
    if(view){
        //如果窗口存在，则判断启动模式
        int launchMode = view->property("launchMode").toInt();
        if(launchMode == 1){
            view->setProperty("argument",argument);
            view->show();
            view->raise();
            view->requestActivate();
            return;
        }else if(launchMode == 2){
            view->close();
        }
    }
    view = qobject_cast<QQuickWindow*>(component.createWithInitialProperties(properties));
    if(fluTheme->frameless()){
        view->setFlag(Qt::FramelessWindowHint,true);
    }
    wnds.insert(view->winId(),view);
    if(fluRegister){
        fluRegister->to(view);
    }
    view->setColor(QColor(Qt::transparent));
    view->show();
}

QJsonArray FluApp::awesomelist(const QString& keyword)
{
    QJsonArray arr;
    QMetaEnum enumType = Fluent_Awesome::staticMetaObject.enumerator(Fluent_Awesome::staticMetaObject.indexOfEnumerator("Fluent_AwesomeType"));
    for(int i=0; i < enumType.keyCount(); ++i){
        QString name = enumType.key(i);
        int icon = enumType.value(i);
        if(keyword.isEmpty()){
            QJsonObject obj;
            obj.insert("name",name);
            obj.insert("icon",icon);
            arr.append(obj);
        }else{
            if(name.contains(keyword)){
                QJsonObject obj;
                obj.insert("name",name);
                obj.insert("icon",icon);
                arr.append(obj);
            }
        }
    }
    return arr;
}

void FluApp::closeApp(){
    qApp->exit(0);
}

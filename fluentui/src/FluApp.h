#ifndef FLUAPP_H
#define FLUAPP_H

#include <QObject>
#include <QWindow>
#include <QtQml/qqml.h>
#include <QJsonArray>
#include <QQmlContext>
#include <QJsonObject>
#include <QQmlEngine>
#include "FluTheme.h"
#include "FluTools.h"
#include "FluColors.h"
#include "NativeEventFilter.h"
#include "FluRegister.h"
#include "stdafx.h"

/**
 * @brief The FluApp class
 */
class FluApp : public QObject
{
    Q_OBJECT
    /**
     * @brief initialRoute 初始路由
     */
    Q_PROPERTY_AUTO(QString,initialRoute);

    /**
     * @brief routes 路由表
     */
    Q_PROPERTY_AUTO(QJsonObject,routes);

    QML_NAMED_ELEMENT(FluApp)
    QML_SINGLETON

public:
    explicit FluApp(QObject *parent = nullptr);
    ~FluApp();

    /**
     * @brief run
     */
    Q_INVOKABLE void run();

    /**
     * @brief navigate
     * @param route
     * @param argument
     * @param fluRegister
     */
    Q_INVOKABLE void navigate(const QString& route,const QJsonObject& argument  = {},FluRegister* fluRegister = nullptr);

    /**
     * @brief init
     * @param window
     */
    Q_INVOKABLE void init(QQuickWindow *window);

    /**
     * @brief awesomelist
     * @param keyword
     * @return
     */
    Q_INVOKABLE QJsonArray awesomelist(const QString& keyword = "");

    /**
     * @brief closeApp
     */
    Q_INVOKABLE void closeApp();

    /**
     * @brief setFluApp 在FluSingleton.qml调用，拿到QML中FluApp的单例
     * @param val
     */
    Q_INVOKABLE void setFluApp(FluApp* val);

    /**
     * @brief setFluTheme 在FluSingleton.qml调用，拿到QML中FluTheme的单例
     * @param val
     */
    Q_INVOKABLE void setFluTheme(FluTheme* val);

    /**
     * @brief setFluColors 在FluSingleton.qml调用，拿到QML中FluColors的单例
     * @param val
     */
    Q_INVOKABLE void setFluColors(FluColors* val);

    /**
     * @brief setFluColors 在FluSingleton.qml调用，拿到QML中FluTools的单例
     * @param val
     */
    Q_INVOKABLE void setFluTools(FluTools* val);

public:
    /**
     * @brief wnds
     */
    QMap<quint64, QQuickWindow*> wnds;

    /**
     * @brief fluApp
     */
    static FluApp* fluApp;

    /**
     * @brief fluTheme
     */
    static FluTheme* fluTheme;

    /**
     * @brief fluColors
     */
    static FluColors* fluColors;

    /**
     * @brief fluTools
     */
    static FluTools* fluTools;

private:
    /**
     * @brief nativeEvent
     */
    NativeEventFilter *nativeEvent = Q_NULLPTR;

    /**
     * @brief appWindow
     */
    QWindow *appWindow;
};

#endif // FLUAPP_H

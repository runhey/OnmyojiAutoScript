#ifndef FLUREGISTER_H
#define FLUREGISTER_H

#include <QObject>
#include <QQuickWindow>
#include <QJsonObject>
#include "stdafx.h"

/**
 * @brief The FluRegister class
 */
class FluRegister : public QObject
{
    Q_OBJECT
    Q_PROPERTY_AUTO(QQuickWindow*,from)
    Q_PROPERTY_AUTO(QQuickWindow*,to)
    Q_PROPERTY_AUTO(QString,path);
public:
    explicit FluRegister(QObject *parent = nullptr);

    /**
     * @brief launch 窗口跳转
     * @param argument 跳转携带参数
     */
    Q_INVOKABLE void launch(const QJsonObject& argument  = {});

    /**
     * @brief onResult 将结果数据回传到上一个窗口
     * @param data 结果数据
     */
    Q_INVOKABLE void onResult(const QJsonObject& data  = {});

    /**
     * @brief result 收到结果数据的信号
     * @param data 结果数据
     */
    Q_SIGNAL void result(const QJsonObject& data);

};

#endif // FLUREGISTER_H

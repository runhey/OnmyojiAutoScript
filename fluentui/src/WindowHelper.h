#ifndef WINDOWHELPER_H
#define WINDOWHELPER_H

#include <QObject>
#include <QQuickWindow>
#include <QtQml/qqml.h>
#include <QQuickItem>
#include <QWindow>
#include <QJsonObject>

/**
 * @brief The WindowHelper class
 */
class WindowHelper : public QObject
{
    Q_OBJECT
    QML_NAMED_ELEMENT(WindowHelper)
public:
    explicit WindowHelper(QObject *parent = nullptr);

    /**
     * @brief initWindow FluWindow中初始化调用
     * @param window
     */
    Q_INVOKABLE void initWindow(QQuickWindow* window);

    /**
     * @brief destoryWindow 销毁窗口，释放资源，QML中的Window close并不会销毁窗口，只是把窗口隐藏了
     */
    Q_INVOKABLE void destoryWindow();

    /**
     * @brief createRegister 创建一个FluRegsiter对象，在FluWindow中registerForWindowResult方法调用
     * @param window
     * @param path
     * @return
     */
    Q_INVOKABLE QVariant createRegister(QQuickWindow* window,const QString& path);

    /**
     * @brief firstUpdate 窗口创建成功后调用，只调用一次
     */
    Q_INVOKABLE void firstUpdate();

private:
    QQuickWindow* window;
};

#endif // WINDOWHELPER_H

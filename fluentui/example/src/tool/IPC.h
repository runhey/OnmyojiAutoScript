#ifndef IPC_H
#define IPC_H

#include <QMap>
#include <QObject>
#include <QSharedMemory>
#include <QTimer>
#include <ctime>
#include <functional>

using IPCEventHandler = std::function<bool(const QByteArray&)>;

#define IPC_PROTOCOL_VERSION "1"

class IPC : public QObject
{
    Q_OBJECT

protected:
    static const int EVENT_TIMER_MS = 1000;
    static const int EVENT_GC_TIMEOUT = 5;
    static const int EVENT_QUEUE_SIZE = 32;
    static const int OWNERSHIP_TIMEOUT_S = 5;

public:
    IPC(uint32_t profileId);
    ~IPC();

    struct IPCEvent
    {
        uint32_t dest;
        int32_t sender;
        char name[16];
        char data[128];
        time_t posted;
        time_t processed;
        uint32_t flags;
        bool accepted;
        bool global;
    };

    struct IPCMemory
    {
        uint64_t globalId;
        time_t lastEvent;
        time_t lastProcessed;
        IPCEvent events[IPC::EVENT_QUEUE_SIZE];
    };

    time_t postEvent(const QString& name, const QByteArray& data = QByteArray(), uint32_t dest = 0);
    bool isCurrentOwner();
    void registerEventHandler(const QString& name, IPCEventHandler handler);
    bool isEventAccepted(time_t time);
    bool waitUntilAccepted(time_t time, int32_t timeout = -1);
    bool isAttached() const;

public slots:
    void setProfileId(uint32_t profileId);

private:
    IPCMemory* global();
    bool runEventHandler(IPCEventHandler handler, const QByteArray& arg);
    IPCEvent* fetchEvent();
    void processEvents();
    bool isCurrentOwnerNoLock();

private:
    QTimer timer;
    uint64_t globalId;
    uint32_t profileId;
    QSharedMemory globalMemory;
    QMap<QString, IPCEventHandler> eventHandlers;
};

#endif // IPC_H

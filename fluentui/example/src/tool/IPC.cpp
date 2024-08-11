#include "IPC.h"

#include <QCoreApplication>
#include <QDebug>
#include <QThread>
#include <ctime>
#include <random>


IPC::IPC(uint32_t profileId)
    : profileId{profileId}
    , globalMemory{"ipc-" IPC_PROTOCOL_VERSION}
{
    qRegisterMetaType<IPCEventHandler>("IPCEventHandler");
    timer.setInterval(EVENT_TIMER_MS);
    timer.setSingleShot(true);
    connect(&timer, &QTimer::timeout, this, &IPC::processEvents);
    std::default_random_engine randEngine((std::random_device())());
    std::uniform_int_distribution<uint64_t> distribution;
    globalId = distribution(randEngine);
    qDebug() << "Our global IPC ID is " << globalId;
    if (globalMemory.create(sizeof(IPCMemory))) {
        if (globalMemory.lock()) {
            IPCMemory* mem = global();
            memset(mem, 0, sizeof(IPCMemory));
            mem->globalId = globalId;
            mem->lastProcessed = time(nullptr);
            globalMemory.unlock();
        } else {
            qWarning() << "Couldn't lock to take ownership";
        }
    } else if (globalMemory.attach()) {
        qDebug() << "Attaching to the global shared memory";
    } else {
        qDebug() << "Failed to attach to the global shared memory, giving up. Error:"
                 << globalMemory.error();
        return;
    }

    processEvents();
}

IPC::~IPC()
{
    if (!globalMemory.lock()) {
        qWarning() << "Failed to lock in ~IPC";
        return;
    }

    if (isCurrentOwnerNoLock()) {
        global()->globalId = 0;
    }
    globalMemory.unlock();
}

time_t IPC::postEvent(const QString& name, const QByteArray& data, uint32_t dest)
{
    QByteArray binName = name.toUtf8();
    if (binName.length() > (int32_t)sizeof(IPCEvent::name)) {
        return 0;
    }

    if (data.length() > (int32_t)sizeof(IPCEvent::data)) {
        return 0;
    }

    if (!globalMemory.lock()) {
        qDebug() << "Failed to lock in postEvent()";
        return 0;
    }

    IPCEvent* evt = nullptr;
    IPCMemory* mem = global();
    time_t result = 0;

    for (uint32_t i = 0; !evt && i < EVENT_QUEUE_SIZE; ++i) {
        if (mem->events[i].posted == 0) {
            evt = &mem->events[i];
        }
    }

    if (evt) {
        memset(evt, 0, sizeof(IPCEvent));
        memcpy(evt->name, binName.constData(), binName.length());
        memcpy(evt->data, data.constData(), data.length());
        mem->lastEvent = evt->posted = result = qMax(mem->lastEvent + 1, time(nullptr));
        evt->dest = dest;
        evt->sender = qApp->applicationPid();
        qDebug() << "postEvent " << name << "to" << dest;
    }
    globalMemory.unlock();
    return result;
}

bool IPC::isCurrentOwner()
{
    if (globalMemory.lock()) {
        const bool isOwner = isCurrentOwnerNoLock();
        globalMemory.unlock();
        return isOwner;
    } else {
        qWarning() << "isCurrentOwner failed to lock, returning false";
        return false;
    }
}

void IPC::registerEventHandler(const QString& name, IPCEventHandler handler)
{
    eventHandlers[name] = handler;
}

bool IPC::isEventAccepted(time_t time)
{
    bool result = false;
    if (!globalMemory.lock()) {
        return result;
    }

    if (difftime(global()->lastProcessed, time) > 0) {
        IPCMemory* mem = global();
        for (uint32_t i = 0; i < EVENT_QUEUE_SIZE; ++i) {
            if (mem->events[i].posted == time && mem->events[i].processed) {
                result = mem->events[i].accepted;
                break;
            }
        }
    }
    globalMemory.unlock();

    return result;
}

bool IPC::waitUntilAccepted(time_t postTime, int32_t timeout /*=-1*/)
{
    bool result = false;
    time_t start = time(nullptr);
    forever
    {
        result = isEventAccepted(postTime);
        if (result || (timeout > 0 && difftime(time(nullptr), start) >= timeout)) {
            break;
        }

        qApp->processEvents();
        QThread::msleep(0);
    }
    return result;
}

bool IPC::isAttached() const
{
    return globalMemory.isAttached();
}

void IPC::setProfileId(uint32_t profileId)
{
    this->profileId = profileId;
}

IPC::IPCEvent* IPC::fetchEvent()
{
    IPCMemory* mem = global();
    for (uint32_t i = 0; i < EVENT_QUEUE_SIZE; ++i) {
        IPCEvent* evt = &mem->events[i];
        if ((evt->processed && difftime(time(nullptr), evt->processed) > EVENT_GC_TIMEOUT)
            || (!evt->processed && difftime(time(nullptr), evt->posted) > EVENT_GC_TIMEOUT)) {
            memset(evt, 0, sizeof(IPCEvent));
        }

        if (evt->posted && !evt->processed && evt->sender != qApp->applicationPid()
            && (evt->dest == profileId || (evt->dest == 0 && isCurrentOwnerNoLock()))) {
            return evt;
        }
    }

    return nullptr;
}

bool IPC::runEventHandler(IPCEventHandler handler, const QByteArray& arg)
{
    bool result = false;
    if (QThread::currentThread() == qApp->thread()) {
        result = handler(arg);
    } else {
        QMetaObject::invokeMethod(this, "runEventHandler", Qt::BlockingQueuedConnection,
                                  Q_RETURN_ARG(bool, result), Q_ARG(IPCEventHandler, handler),
                                  Q_ARG(const QByteArray&, arg));
    }
    return result;
}

void IPC::processEvents()
{
    if (!globalMemory.lock()) {
        timer.start();
        return;
    }

    IPCMemory* mem = global();

    if (mem->globalId == globalId) {
        mem->lastProcessed = time(nullptr);
    } else {
        if (difftime(time(nullptr), mem->lastProcessed) >= OWNERSHIP_TIMEOUT_S) {
            qDebug() << "Previous owner timed out, taking ownership" << mem->globalId << "->"
                     << globalId;
            memset(mem, 0, sizeof(IPCMemory));
            mem->globalId = globalId;
            mem->lastProcessed = time(nullptr);
        }
    }

    while (IPCEvent* evt = fetchEvent()) {
        QString name = QString::fromUtf8(evt->name);
        auto it = eventHandlers.find(name);
        if (it != eventHandlers.end()) {
            evt->accepted = runEventHandler(it.value(), evt->data);
            qDebug() << "Processed event:" << name << "posted:" << evt->posted
                     << "accepted:" << evt->accepted;
            if (evt->dest == 0) {
                if (evt->accepted) {
                    evt->processed = time(nullptr);
                }
            } else {
                evt->processed = time(nullptr);
            }
        } else {
            qDebug() << "Received event:" << name << "without handler";
            qDebug() << "Available handlers:" << eventHandlers.keys();
        }
    }

    globalMemory.unlock();
    timer.start();
}

bool IPC::isCurrentOwnerNoLock()
{
    const void* const data = globalMemory.data();
    if (!data) {
        qWarning() << "isCurrentOwnerNoLock failed to access the memory, returning false";
        return false;
    }
    return (*static_cast<const uint64_t*>(data) == globalId);
}

IPC::IPCMemory* IPC::global()
{
    return static_cast<IPCMemory*>(globalMemory.data());
}

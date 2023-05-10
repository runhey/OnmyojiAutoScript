#include "ChatController.h"

ChatController::ChatController(QObject *parent)
    : QObject{parent}
{
    isLoading(false);
    networkManager = new QNetworkAccessManager(this);
}


void ChatController::sendMessage(const QString& text){
    isLoading(true);
    QUrl apiUrl("https://api.openai.com/v1/chat/completions");
    QNetworkRequest request(apiUrl);
    request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
    request.setRawHeader("Authorization", QString::fromStdString("Bearer %1").arg(QString::fromUtf8(QByteArray::fromBase64(baseKey.toUtf8()))).toUtf8());
    QJsonObject requestData;
    requestData.insert("model", "gpt-3.5-turbo");
    messages.append(createMessage("user",text));
    requestData.insert("messages", messages);
    QJsonDocument requestDoc(requestData);
    QByteArray requestDataBytes = requestDoc.toJson();
    QNetworkReply* reply = networkManager->post(request, requestDataBytes);
    connect(reply, &QNetworkReply::finished,this, [=]() {
        if (reply->error() == QNetworkReply::NoError) {
            QString responseString = QString::fromUtf8(reply->readAll());
            qDebug() << responseString;
            QJsonDocument doc = QJsonDocument::fromJson(responseString.toUtf8());
            QJsonObject jsonObj = doc.object();
            QString text = jsonObj.value("choices").toArray().at(0).toObject().value("message").toObject().value("content").toString();
            if(text.isEmpty()){
                text = "响应错误：content为空数据";
            }else{
                messages.append(createMessage("assistant",text));
            }
            responseData(text.trimmed());
        } else {
            responseData("网络错误："+reply->errorString());
        }
        isLoading(false);
        reply->deleteLater();
    });
}

QJsonObject ChatController::createMessage(const QString& role,const QString& content){
    QJsonObject message;
    message.insert("role",role);
    message.insert("content",content);
    return message;
}

void ChatController::clipText(const QString& text){
    qDebug()<<text;
    QClipboard *clipboard = QGuiApplication::clipboard();
    clipboard->setText(text);
}

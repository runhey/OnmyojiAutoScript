# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from random import randint
from paho.mqtt import client as mqtt_client

broker = 'v96bb091.ala.cn-hangzhou.emqxsl.cn'
port = 8883
topic = 'python/mqtt'
client_id = f'python-mqtt-{randint(0, 1000)}'
# 如果 broker 需要鉴权，设置用户名密码
username = 'test-publish'
password = '12345678'

def connect_mqtt():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)

    # Set Connecting Client ID
    client = mqtt_client.Client(client_id)
    client.tls_set(ca_certs='./emqxsl-ca.crt')
    client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(broker, port)
    return client

def subscribe(client: mqtt_client):
    def on_message(client, userdata, msg):
        print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")

    client.subscribe(topic=topic, qos=0)
    client.on_message = on_message


def publish(client):
    msg_count = 0
    while True:
        sleep(1)
        msg = f"messages: {msg_count}"
        result = client.publish(topic, msg)
        # result: [0, 1]
        status = result[0]
        if status == 0:
            print(f"Send `{msg}` to topic `{topic}`")
        else:
            print(f"Failed to send message to topic {topic} {status}")
        msg_count += 1

def on_message(client, userdata, msg):
    print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")

def run():
    client = connect_mqtt()
    client.loop_start()
    publish(client)



if __name__ == '__main__':
    run()


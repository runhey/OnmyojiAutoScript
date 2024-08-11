# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep

import json
from random import randint
from paho.mqtt import client as mqtt_client
from threading import Thread
from queue import Queue

from tasks.GlobalGame.config import TeamFlow, Transport

from module.logger import logger
from module.base.timer import Timer


def on_message(client, userdata, msg):
    if msg.topic == 'FirstNotice':
        return
    logger.info(f"Received `{msg.payload}` from `{userdata}` ")
# ----------------------------------------------------------------------------------------------------------------------
# 使用MQTT是为了做广播，自己手撸的话太麻烦了
# 0. 所有玩家更新自己的策略后必须广播出去, 可以延迟一下
# 1. 当一个玩家启动接入网络后，会向服务器发送FirstNotice，这个时候所有的玩家都要发送一次自己的策略来给新加入的玩家来优化自己的策略
# 2. 当一个玩家退出网络后，会向服务器发送LastNotice，这个时候所有的玩家都要更新自己的策略
# ----------------------------------------------------------------------------------------------------------------------
class Mqtt:
    # 队列的结构必须是一个tuple，第一个元素是topic，第二个元素是msg
    q_publish: Queue = None

    def __init__(self, team_flow: TeamFlow):
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                logger.info("Connected to MQTT Broker!")
            elif rc == 1:
                # 协议版本错误
                logger.error(f"Connection refused - incorrect protocol version. return code: {rc}")
            elif rc == 2:
                # 无效的客户端标识
                logger.error(f"Connection refused - invalid client identifier. return code: {rc}")
            elif rc == 3:
                # 服务器不可用
                logger.error(f"Connection refused - server unavailable. return code: {rc}")
            elif rc == 4:
                # 错误的用户名或密码
                logger.error(f"Connection refused - bad username or password. return code: {rc}")
            elif rc == 5:
                # 未授权
                logger.error(f"Connection refused - not authorised. return code: {rc}")
            else:
                logger.info("Failed to connect, return code %d\n", rc)
        self.q_publish = Queue()
        self.broker = team_flow.broker
        self.port = team_flow.port
        self.protocol = team_flow.transport
        self.ca = team_flow.ca
        self.username = team_flow.username
        self.password = team_flow.password
        self.client_id = f'{self.username}-{randint(0, 1000)}'
        # 连接服务器
        self.client = mqtt_client.Client(self.client_id, clean_session=True, userdata=self)
        if self.protocol == Transport.SSL_TLS:
            self.client.tls_set(ca_certs=self.ca)
        self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = on_connect
        self.client.on_message = on_message
        self.client.will_set(topic='LastWill', payload=json.dumps({self.username: ""}), qos=2)
        self.client.connect(self.broker, self.port)
        # 订阅主题: FirstNotice LastWill TaskStart Strategy
        self.client.subscribe(topic='FirstNotice', qos=2)
        self.client.subscribe(topic='LastWill', qos=2)
        self.client.subscribe(topic='TaskStart', qos=0)
        self.client.subscribe(topic='Strategy', qos=0)
        # publish FirstNotice
        self.publish("FirstNotice", {"type": "join"})
        # 开启一个线程来处理消息
        self.mqtt_timer = Timer(30)
        self.mqtt_timer.start()
        self.mqtt_thread = Thread(target=self.mqtt_loop, name='mqtt_loop', daemon=True)
        self.mqtt_thread.start()



    def set_on_message(self, on_msg):
        self.client.on_message = on_msg

    def publish(self, topic: str, msg: dict) -> bool:
        """

        :param topic:
        :param msg: 必须是一个字典
        :return:
        """
        if not isinstance(msg, dict):
            logger.warning(f"Msg must be a dict, but got {type(msg)}")
            return False
        msg = {self.username: msg}
        result = self.client.publish(topic, json.dumps(msg))
        # result: [0, 1]
        status = result[0]
        if status == 0:
            logger.info(f"Send `msg` to topic `{topic}`")
            return True
        else:
            logger.info(f"Failed to send message to topic {topic} {status}")
            return False

    def TaskStart(self, msg):
        self.publish('TaskStart', msg)

    def Strategy(self, msg):
        self.publish('Strategy', msg)

    def mqtt_loop(self):
        while True:
            # sleep(5)
            # 官方超级不推荐这种方式来处理消息。 但是不打算开一个线程来处理这个mqtt_timer
            try:
                self.client.loop(timeout=5)
            except Exception as e:
                logger.error(e)

            if not self.mqtt_timer.reached():
                continue
            self.mqtt_timer.reset()
            publish_strategy_msg = None
            while not self.q_publish.empty():
                try:
                    topic, msg = self.q_publish.get(block=False)
                except Exception as e:
                    continue
                if topic == 'Strategy':
                    publish_strategy_msg = msg
                    continue
                self.publish(topic, msg)
            if publish_strategy_msg:
                # 先进先出 保证只发送一次最新的
                self.publish('Strategy', publish_strategy_msg)





if __name__ == '__main__':
    team_flow = TeamFlow()
    team_flow.broker = 'v96bb091.ala.cn-hangzhou.emqxsl.cn'
    team_flow.port = 8883
    team_flow.transport = Transport.SSL_TLS
    team_flow.ca = './config/emqxsl-ca.crt'
    team_flow.username = 'test-publish'
    team_flow.password = '12345678'
    mqtt = Mqtt(team_flow)
    sleep(20)



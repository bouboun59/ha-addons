#!/usr/bin/python3
# coding: utf-8
import time
import sys
import os

systemd_available = True
try:
    import systemd
    from systemd.journal import JournalHandler
    from systemd import daemon
    import psutil, os
except:
  print("Systemd is not available. This is the case on docker alpine images and on windows machines")
  systemd_available = False
  
import json
import logging
import time
from logging.handlers import TimedRotatingFileHandler
import paho.mqtt.client as mqtt
import websocket

from _config_ import _MCZport
from _config_ import _MCZip
from _config_ import _MQTT_authentication
from _config_ import _MQTT_TOPIC_PUB, _MQTT_TOPIC_SUB, _MQTT_PAYLOAD_TYPE
from _config_ import _WS_RECONNECTS_BEFORE_ALERT
from _config_ import _VERSION
from _config_ import _REFRESH_INTERVAL
# MQTT
from _config_ import _MQTT_ip
from _config_ import _MQTT_pass
from _config_ import _MQTT_port
from _config_ import _MQTT_user


get_stove_info_interval = _REFRESH_INTERVAL
websocket_connected = False
socket_reconnect_count = 0
client = None
old_connection_status = None
_TEMPS_SESSION = 300


try:
    import thread
except ImportError:
    import _thread as thread

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s :%(name)s :: %(levelname)s :: %(message)s')
file_handler = TimedRotatingFileHandler('maestro.log', when='D', interval=1, backupCount=5)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


class PileFifo(object):
    def __init__(self, maxpile=None):
        self.pile = []
        self.maxpile = maxpile

    def empile(self, element, idx=0):
        if (self.maxpile != None) and (len(self.pile) == self.maxpile):
            raise ValueError("erreur: tentative d'empiler dans une pile pleine")
        self.pile.insert(idx, element)

    def depile(self, idx=-1):
        if len(self.pile) == 0:
            raise ValueError("erreur: tentative de depiler une pile vide")
        if idx < -len(self.pile) or idx >= len(self.pile):
            raise ValueError("erreur: element de pile à depiler n'existe pas")
        return self.pile.pop(idx)

    def element(self, idx=-1):
        if idx < -len(self.pile) or idx >= len(self.pile):
            raise ValueError("erreur: element de pile à lire n'existe pas")
        return self.pile[idx]

    def copiepile(self, imin=0, imax=None):
        if imax == None:
            imax = len(self.pile)
        if imin < 0 or imax > len(self.pile) or imin >= imax:
            raise ValueError("erreur: mauvais indice(s) pour l'extraction par copiepile")
        return list(self.pile[imin:imax])

    def pilevide(self):
        return len(self.pile) == 0

    def pilepleine(self):
        return self.maxpile != None and len(self.pile) == self.maxpile

    def taille(self):
        return len(self.pile)


def on_connect_mqtt(client, userdata, flags, rc):
    logger.info("Connecté au broker MQTT avec le code : " + str(rc))


def on_message_mqtt(client, userdata, message):
    logger.info('Message MQTT reçu : ' + str(message.payload.decode()))
    msg = []
    if message.payload.decode().find(";") > -1:
        msg = message.payload.decode().split(";")
    else: 
        msg.append(message.payload.decode()) 
    for value in msg:
        cmd = value.split(",")
        if cmd[0] == "42":
            cmd[1] = (int(cmd[1]) * 2)
        
        ws.send("C|WriteParametri|" + cmd[0] + "|" + str(cmd[1]))
        ws.send("C|RecuperoInfo")
        logger.info('Contenu Pile Message_MQTT : ' + str("C|WriteParametri|" + cmd[0] + "|" + str(cmd[1])))
   

def secTOdhms(nb_sec):
    qm, s = divmod(nb_sec, 60)
    qh, m = divmod(qm, 60)
    d, h = divmod(qh, 24)
    return "%d:%d:%d:%d" % (d, h, m, s)

#sur message websocket
def on_message(ws, response):
    logger.info("Received message")
    datas = response.split("|")
    from _data_ import RecuperoInfo
    for i in range(0, len(datas)):
        for j in range(0, len(RecuperoInfo)):
            if i == RecuperoInfo[j][0]:
                if len(RecuperoInfo[j]) > 2:
                    for k in range(0, len(RecuperoInfo[j][2])):
                        if int(datas[i], 16) == RecuperoInfo[j][2][k][0]:
                            MQTT_MAESTRO[RecuperoInfo[j][1]] = RecuperoInfo[j][2][k][1]
                            break
                        else:
                            MQTT_MAESTRO[RecuperoInfo[j][1]] = ('Code inconnu :', str(int(datas[i], 16)))
                else:
                    if i == 6 or i == 26 or i == 28:
                        MQTT_MAESTRO[RecuperoInfo[j][1]] = float(int(datas[i], 16)) / 2

                    elif i >= 37 and i <= 42:
                        MQTT_MAESTRO[RecuperoInfo[j][1]] = secTOdhms(int(datas[i], 16))
                    else:
                        MQTT_MAESTRO[RecuperoInfo[j][1]] = int(datas[i], 16)
    logger.info('Publication sur le topic MQTT ' + str(_MQTT_TOPIC_PUB) + ' le message suivant : ' + str(
    json.dumps(MQTT_MAESTRO)))
    client.publish(_MQTT_TOPIC_PUB, json.dumps(MQTT_MAESTRO), 1)




#socket on error
def on_error(ws, error):
    logger.info(error)
    
#socket on close
def on_close(ws, close_status_code, close_msg):
    logger.info('Session websocket fermée: '+ws+' '+close_status_code+' '+close_msg)


#ouverture #def send():
def on_open(ws):
    def run(*args):
        global websocket_connected
        websocket_connected = True
        for i in range(_TEMPS_SESSION):
            cmd = "C|RecuperoInfo"
            logger.info("Envoi de la commande : " + str(cmd) +" boucle " + str(i))
            ws.send(cmd)
            time.sleep(get_stove_info_interval)
            #if Message_MQTT.pilevide():
            #    Message_MQTT.empile("C|RecuperoParametriExtra")
            #cmd = Message_MQTT.depile()
            #logger.info("Envoi de la commande : " + str(cmd))
            #ws.send(cmd)
        ws.close()
    thread.start_new_thread(run, ())
  

  
#mqtt start
def start_mqtt():
    global client
    global Message_MQTT		
    global Message_WS 
    global MQTT_MAESTRO
	
    logger.info('Connection in progress to the MQTT broker (IP:' +
                _MQTT_ip + ' PORT:'+str(_MQTT_port)+')')
    client = mqtt.Client()
    Message_MQTT = PileFifo()
    Message_WS = PileFifo()
    MQTT_MAESTRO = {}
    if _MQTT_authentication:
        print('mqtt authentication enabled')
        client.username_pw_set(username=_MQTT_user, password=_MQTT_pass)
    client.on_connect = on_connect_mqtt
    client.on_message = on_message_mqtt
    client.connect(_MQTT_ip, _MQTT_port)
    client.loop_start()
    logger.info('MQTT: Subscribed to topic "' + str(_MQTT_TOPIC_SUB) + '"')
    client.subscribe(_MQTT_TOPIC_SUB, qos=1)  
        
#init value
def init_config():
    print('Reading config from envionment variables')
    if (os.getenv('MQTT_ip') != None):
        global _MQTT_ip
        _MQTT_ip = os.getenv('MQTT_ip')
    if (os.getenv('MQTT_port') != None):
        global _MQTT_port
        _MQTT_port = int(os.getenv('MQTT_port'))
    if (os.getenv('MQTT_authentication') != None):
        global _MQTT_authentication
        _MQTT_authentication = os.getenv('MQTT_authentication') == "True"
    if (os.getenv('MQTT_user') != None):
        global _MQTT_user
        _MQTT_user = os.getenv('MQTT_user')
    if (os.getenv('MQTT_pass') != None):
        global _MQTT_pass
        _MQTT_pass = os.getenv('MQTT_pass')
    if (os.getenv('MQTT_TOPIC_PUB') != None):
        global _MQTT_TOPIC_PUB
        _MQTT_TOPIC_PUB = os.getenv('MQTT_TOPIC_PUB')
    if (os.getenv('MQTT_TOPIC_SUB') != None):
        global _MQTT_TOPIC_SUB
        _MQTT_TOPIC_SUB = os.getenv('MQTT_TOPIC_SUB')
    if (os.getenv('MQTT_PAYLOAD_TYPE') != None):
        global _MQTT_PAYLOAD_TYPE
        _MQTT_PAYLOAD_TYPE = os.getenv('MQTT_PAYLOAD_TYPE')
    if (os.getenv('WS_RECONNECTS_BEFORE_ALERT') != None):
        global _WS_RECONNECTS_BEFORE_ALERT
        _WS_RECONNECTS_BEFORE_ALERT = int(os.getenv('WS_RECONNECTS_BEFORE_ALERT'))
    if (os.getenv('MCZip') != None):
        global _MCZip
        _MCZip = os.getenv('MCZip')
    if (os.getenv('MCZport') != None):
        global _MCZport
        _MCZport = os.getenv('MCZport')

def recuperoinfo_enqueue():
    """Get Stove information every x seconds as long as there is a websocket connection"""
    threading.Timer(get_stove_info_interval, recuperoinfo_enqueue).start()
    #if websocket_connected:
        #CommandQueue.put(MaestroCommandValue(MaestroCommand('GetInfo', 0, 'GetInfo', 'GetInfo'), 0))
        #client.publish(_MQTT_TOPIC_PUB + 'state',  'ON',  1) 
        
#connection au poele
if __name__ == "__main__":
    logger.info('Lancement du deamon')
    logger.info('Anthony L. 2019')
    logger.info("Bouboun59's version")
    logger.info('Niveau de LOG : DEBUG')
    init_config()        
    #recuperoinfo_enqueue()
    socket_reconnect_count = 0
    start_mqtt()
    if systemd_available:
        systemd.daemon.notify('READY=1')
    while True:
        logger.info("Websocket: Establishing connection to server (IP:"+_MCZip+" PORT:"+_MCZport+")")
        ws = websocket.WebSocketApp("ws://" + _MCZip + ":" + _MCZport,
                                    on_message=on_message,
                                    on_error=on_error,
                                    on_close=on_close)
        ws.on_open = on_open
        ws.run_forever(ping_interval=5, ping_timeout=2, suppress_origin=True)
        time.sleep(1)
        socket_reconnect_count = socket_reconnect_count + 1
        logger.info("Socket Reconnection Count: " + str(socket_reconnect_count))
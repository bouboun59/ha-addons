#coding: utf-8
'''
Edit as needed
'''
_MQTT_ip = 'core.mosquitto'			# Mqtt broker address
_MQTT_port = 1883						# Mqtt port
_MQTT_authentication = False            # Mqtt use authentication? 
_MQTT_user = ''			                # Mqtt User name
_MQTT_pass = ''			                # Mqtt password
_MQTT_TOPIC_SUB = 'Maestro/Command'	# Publish command messages here (mandatory trailing slash)
_MQTT_TOPIC_PUB = 'Maestro/State'	        # Information messages by daemon are published here (mandatory trailing slash)
_MQTT_PAYLOAD_TYPE = 'TOPIC'            # Payload as seperate subtopic (_MQTT_PAYLOAD_TYPE='TOPIC') or as JSON (_MQTT_PAYLOAD_TYPE='JSON'), recommended is TOPIC.
_WS_RECONNECTS_BEFORE_ALERT = 5         # Attempts to reconnect to webserver before publishing a alert on topic Maestro/Status
_REFRESH_INTERVAL = 15.0                # Refresh interval for stove information in seconds
_MCZip ='192.168.120.1'				    # Stove IP Address. This probably is always this address.
_MCZport = '81'						    # Websocket Port
_VERSION = '1.03'					    # Version

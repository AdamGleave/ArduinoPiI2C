#!/usr/bin/env python

from __future__ import print_function
import socket
import mosquitto
import yaml
import fcntl
import time
import datetime
import sys
import csv

ISO_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'
CONFIG_FILENAME = "config.yaml"

def printErr(*args):
    '''Print to stderr so we can separate information messages with readings from I2C'''
    print(*args, file=sys.stderr)

class LockingFile(file):
    def __init__(self,*args,**kwargs):
        file.__init__(self,*args,**kwargs)
        self.EOFEncountered = False

    def __iter__(self):
        return self

    def next(self):
        if self.EOFEncountered:
            raise StopIteration

        # block until we acquire lock on file
        # makes sure we don't read at the same time as i2cpoll.py is writing to the file
        fcntl.lockf(self, fcntl.LOCK_SH)

        line = self.readline()
        
        # release lock
        fcntl.lockf(self, fcntl.LOCK_UN) 

        if line == '':
            self.EOFEncountered = True
            raise StopIteration
        else:
            return line
    
    # WARNING: Technically this breaks the Python iterator interface!
    # Once StopIteration has been raised once, it should always be raised on
    # subsequent calls to next.
    #
    # This should be okay so long as we're careful, though.
    def clearEOF(self):
        self.EOFEncountered = False

class LastUpdated():
    def __init__(self, path):
        try:
            self.f = open(path, 'r+b')
        except IOError:
            # perhaps file doesn't exist as first time we've been run
            self.f = open(path, 'rwb')

        # acquire exclusive lock
        # (only one instance of this program should be running at a time)
        fcntl.flock(self.f, fcntl.LOCK_EX)

        lastUpdatedStr = self.f.read()
        try:
            self.lastUpdated = datetime.datetime.strptime(lastUpdatedStr, ISO_FORMAT)
        except ValueError:
            printErr("Cannot read last updated time. Will upload all data.")
            # initialise to UNIX epoch
            self.lastUpdated = datetime.datetime(1970, 1, 1)
        
    def getTime(self):
        return self.lastUpdated

    def setTime(self, dt):
        dtStr = datetime.datetime.strftime(dt, ISO_FORMAT)
        self.f.truncate(0)
        self.f.seek(0)
        self.f.write(dtStr)
        self.f.flush()

def load_config():
    with open(CONFIG_FILENAME, 'rb') as configFile:
        config = yaml.load(configFile)
        return config

def mqtt_connect():
    # Get the hostname of this computer
    clientHostName = socket.gethostname()
    # Use the hostname as the MQTT client name
    mqttc = mosquitto.Mosquitto(clientHostName)
    # Connect to the MQTT broker
    serverHostName = config['mqtt']['server']
    port = config['mqtt']['port']
    keepAlive = config['mqtt']['keepAlive']
    printErr("Connecting to %s:%d with client hostname %s (keep alive %d)" %
             (serverHostName, port, clientHostName, keepAlive))
    mqttc.connect(serverHostName, port, keepAlive)

    return mqttc

config = load_config()
mqttc = mqtt_connect()
lastUpdated = LastUpdated(config['lastUpdatedPath'])

# Process CSV
# Format: timestamp, sensor ID, reading
printErr("Opening %s" % config['csvPath'])
with LockingFile(config['csvPath'], 'rb') as csvfile:
    while True:    
        sensorReader = csv.reader(csvfile, strict=True)
        for row in sensorReader:
            (timeStampStr, sensorID, value) = row
            timeStamp = datetime.datetime.strptime(timeStampStr, ISO_FORMAT)
            if timeStamp > lastUpdated.getTime():
                topicConfig = config['mqtt']['topic']
                topic = "/".join([topicConfig['prefix'],
                                  topicConfig['instance'], sensorID])
                printErr("Publishing %s to %s" % (value, topic))
                mqttc.publish(topic,value, config['mqtt']['reliability'])
                lastUpdated.setTime(timeStamp)
        
        csvfile.clearEOF()    
        time.sleep(1)

printErr("DONE! Disconnecting.")
mqttc.disconnect()

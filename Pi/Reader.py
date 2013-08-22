from __future__ import print_function
from smbus import SMBus
import sys
import csv
import datetime
import time
import signal
import RPi.GPIO as GPIO
import yaml

CONFIG_FILENAME = "config.yaml"

def load_config():
    with open(CONFIG_FILENAME, 'rb') as configFile:
        config = yaml.load(configFile)
        if config['powerCtl']['enabled']:
            onIfHigh = config['powerCtl']['onIfHigh']
            config['powerCtl']['onOutput'] = 1 if onIfHigh else 0
            config['powerCtl']['offOutput'] = 0 if onIfHigh else 1
        return config

def formatSensorList(sensors):
    return "\t".join(sensors)

def printErr(*args):
    '''Print to stderr so we can separate information messages with readings from I2C'''
    print(*args, file=sys.stderr)

def escapeSpecials(s):
    '''Escapes any special characters. e.g. escapeSpecials("hello") returns "hello". escapeSpecials("\nhi\t") returns "\\nhi\\t".'''
    escaped = repr(s)
    return escaped[1:-1] # removes leading and trailing '

def open_bus():
    deviceId = config['i2c']['device-id']
    try:
        bus = SMBus(deviceId)
        printErr("Opened I2C bus #%d" % deviceId)
    except IOError:
        printErr("Could not open /dev/i2c-%d. Have you run `gpio load i2c`?" % deviceId)
        sys.exit(-1)
    return bus

def scan():
    global i2c_error

    devices = {}
    
    startAddress = config["i2c"]["slaves"]["start"]
    endAddress = config["i2c"]["slaves"]["end"]
    for address in range(startAddress, endAddress + 1):
        try:
            bus.write_byte(address, ord("?"))

            response = readResponse(address)
            response = response.rstrip("\t") # remove trailing newline
            sensors = response.split("\t") # response is a newline delimited sensor list
            devices[address] = sensors
        except IOError:
            pass # No device at this address
        except TimeoutException:
            printErr("Timed out reading from address %d. Incorrectly configured device?" % address)
            i2c_error = True

    return devices

class TimeoutException(Exception):
    pass

def readResponse(address):
    def timeout_handler(signum, frame):
        raise TimeoutException()

    response = ""

    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(config['i2c']['timeout'])
    try:
        while True:
            byte = bus.read_byte(address)
            if byte == 0:
                # ignore zero's; we use these as pauses
                # in the Arduino slave code
                continue
            char = chr(byte)
            if char == "\n":
                # used to terminate a read
                break
            response = response + char
    finally:
        signal.alarm(0) # disable alarm
        signal.signal(signal.SIGALRM, old_handler) # reset to old signal handler

    return response

def writeRequest(address, string):
    for character in string:
        ascii_value = ord(character)
        bus.write_byte(address, ascii_value)

def difference(devices, oldDevices):
    addresses = set(devices.keys())
    oldAddresses = set(oldDevices.keys())

    connected = addresses - oldAddresses
    detached = oldAddresses - addresses
    unchanged = set.intersection(addresses, oldAddresses)

    for address in connected:
        sensors = devices[address]

        sensors_desc = formatSensorList(sensors)
        printErr("Address %d: Device connected, with sensors: %s" % (address, sensors_desc))

    for address in detached:
        printErr("Address %d: Device detached" % address)

    for address in unchanged:
        sensors = set(devices[address])
        oldSensors = set(oldDevices[address])
        
        added = sensors - oldSensors
        removed = oldSensors - sensors

        messages = []
        if added: # not empty set
             msg = "added %s" % formatSensorList(added)
             messages.append(msg)
        if removed:
            msg = "removed %s" % formatSensorList(removed)
            messages.append(msg)

        if added or removed: # there has been some change
            messagesStr = ",".join(messages)
            printErr("Address %d: %s" % (address, messagesStr))

def poll(devices):
    global i2c_error

    response = {}
    for address in devices:
        sensors = devices[address]
        values = {}

        for sensor in sensors:
            try:
                writeRequest(address, sensor)
                value = readResponse(address)
                values[sensor] = value
            except IOError as e:
                values[sensor] = "IOError({0}): {1}".format(e.errno, e.strerror)
                i2c_error = True
            except TimeoutException:
                values[sensor] = "TIMEOUT"
                i2c_error = True

        response[address] = values

    return response

def power_control_setup():
    if config['powerCtl']['enabled']:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(config['powerCtl']['pin'], GPIO.OUT)    
        GPIO.output(config['powerCtl']['pin'], config['powerCtl']['onOutput'])

        time.sleep(config['powerCtl']['waitFor'])

def power_control_cycle():
    if config['powerCtl']:
        printErr("Turning power OFF.")
        GPIO.output(config['powerCtl']['pin'], config['powerCtl']['offOutput'])

        time.sleep(config['powerCtl']['powerOffTime'])

        GPIO.output(config['powerCtl']['pin'], config['powerCtl']['onOutput'])
        printErr("Turning power ON.")

        time.sleep(config['powerCtl']['waitFor'])

config = load_config()
bus = open_bus()
power_control_setup()
i2c_error = False

with open(config['csv-log'], 'ab') as csvfile:
    csv = csv.writer(csvfile)

    printErr("I will list all connected I2C devices and attached sensors, and tell you whenever this changes.")
    oldDevices = None
    devices = {}
    while True:
        print("\n*****")
        oldDevices = devices
        devices = scan()

        difference(devices, oldDevices)

        print("")
        allReadings = poll(devices)

        # Print to terminal
        for address in allReadings:
            print("Address %d:" % address, end=" ")
            deviceReadings = allReadings[address]
            for sensorName in deviceReadings:
                value = deviceReadings[sensorName]
                value = escapeSpecials(value) # in case we read malformed data
                print("%s = %s" % (sensorName, value), end=" ")
            print("")
                
        # Log to CSV
        dt = datetime.datetime.utcnow()
        timeStamp = dt.isoformat() + "+00:00" # specify we're in UTC timezone
        for address in allReadings:
            deviceReadings = allReadings[address]
            for sensorName in deviceReadings:
                value = deviceReadings[sensorName]
                row = [timeStamp, sensorName, value]
                csv.writerow(row)

        # Have we encountered an error in the read?
        if i2c_error:
            printErr("An I2C error occurred at some point in this cycle (see above for details.")
            power_control_cycle()
            i2c_error = False

        time.sleep(config['poll-interval'])

from __future__ import print_function
from smbus import SMBus
import sys
import csv
import datetime
import time
import signal

START_ADDRESS = 8 # includes start address
END_ADDRESS = 120 # omits end address
DEVICE_ID = 1 # indicates /dev/i2c-DEVICE_ID
POLL_INTERVAL = 10 # in seconds
TIMEOUT = 3 # in seconds
CSV_FILENAME = "Sensors.csv"

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
    try:
        bus = SMBus(DEVICE_ID)
        printErr("Opened I2C bus #%d" % DEVICE_ID)
    except IOError:
        printErr("Could not open /dev/i2c-%d. Have you run `gpio load i2c`?" % DEVICE_ID)
        sys.exit(-1)
    return bus

def scan():
    devices = {}

    for address in range(START_ADDRESS, END_ADDRESS):
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

    return devices

class TimeoutException(Exception):
    pass

def readResponse(address):
    def timeout_handler(signum, frame):
        raise TimeoutException()

    response = ""

    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(TIMEOUT)
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
        signal.alarm(0) # disable alarm
    finally:
        signal.signal(signal. SIGALRM, old_handler) # reset to old signal handler

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
            except TimeoutException:
                values[sensor] = "TIMEOUT"

        response[address] = values

    return response
    
bus = open_bus()

with open(CSV_FILENAME, 'ab') as csvfile:
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

        time.sleep(POLL_INTERVAL)

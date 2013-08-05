/**************************** INSERT YOUR CODE HERE ***************************/

/* This is example code. It stores the (approximate) time the Arduino has been running
 * into sensorVal1. You can then access that value over I2C, e.g. using the Raspberry Pi.
 *
 * To use your own code, delete the code below.
 * Then, copy and paste your setup() and loop() functions.
 * Finally, rename them to your_setup() and your_loop().
 */

float sensorVal1;

void your_setup()
{
  sensorVal1 = 0.0;
}

void your_loop()
{
  sensorVal1 = sensorVal1 + 1.0;
  delay(1);
}

/************************* CONFIGURATION -- EDIT THIS! *************************/

// Do NOT need to change this
typedef struct {
  const char *name;
  float *value;
} sensor;

// DO need to change the next two things:
#define I2C_ADDRESS 42 // must be between 8-120. Make sure this is different to other devices you connect!

/* To add a new sensor:
 * 1. Uncomment a line below, i.e. remove the // before it. Otherwise the line is ignored.
 * 2. Change the name to something which describes what you're sending, e.g. change SENSOR1 to TEMPERATURE.
 *
 *    IMPORTANT: Keep the double quotes (") either side of the name -- it means it is a string, not an identifier.
 * 3. Change the variable to what you're using to store your value; e.g. if your loop stores the temperature to temp_c,
 *    then change &sensorVal1 to &temp_c.
 *
 *    Note that the variable must be a numeric type, i.e. either an int or a float 
 *
 *    IMPORTANT: Keep the & before the variable (look up 'pointers' to understand why this is necessary.)
 */
sensor sensors[] = {
                      {"SENSOR1", &sensorVal1},
                      //{"SENSOR2", &sensorVal2},
                      //{"SENSOR3", &sensorVal3},
                      //{"SENSOR4", &sensorVal4},
                    };

/************************* NO NEED TO CHANGE THE CODE BELOW *******************/

#include <Wire.h>
#include <stdbool.h>

char request[128];
char *responseStr = NULL;
char *sensorList = NULL;
int posIn = 0;
int posOut = 0;

#define CONVERSION_WIDTH 2
#define CONVERSION_PRECISION 5
char responseBuf[16]; // for storing output of number to string conversions

void receiveEvent(int howMany)
{
  while (howMany > 0)
  {
    if (posIn < sizeof(request)-1) 
    {
      request[posIn++] = Wire.read();
      request[posIn] = 0; // maintain it as a string by NIL-terminating
    }
    else {
      Serial.println("WARNING: Read too many bytes before receiving a request.");
      posIn = 0;
    }
    howMany--;
  }
}

#define LENGTH(arr) (sizeof(arr)/sizeof(arr[0]))

void requestEvent()
{
  if (!responseStr)
  { 
    float responseNum;
    
    for (int i = 0; i < LENGTH(sensors); i++)
    {
      sensor aSensor = sensors[i];
      
      if (strcmp(request, aSensor.name) == 0)
      { // match
        responseNum = *aSensor.value;
        dtostrf(responseNum, CONVERSION_WIDTH, CONVERSION_PRECISION, responseBuf);
        responseStr = responseBuf;
        break;
      }
    }
    if (!responseStr) { // no match
      if (strcmp(request, "TEST") == 0) {
        responseStr = "HELLO";
      }
      else
      { // not a recognised sensor or built-in command
        responseStr = "ERR"; 
      }
    }
    
    if (strcmp(request, "TEST") == 0) {
      responseStr = "HELLO";
    } else {
      responseStr = "ERR";
    }
      
    Serial.print("Received ");
    Serial.println(request);
    posIn = posOut = 0;
    request[0] = 0;
    
    Wire.write(0);
  }
  else
  {
    if (responseStr[posOut] != '\0') {
      Wire.write(responseStr[posOut++]);
    } else
    {
      Wire.write("\n");
      Serial.println(responseStr);
      responseStr = NULL;
    }
  }
}

void setup()
{
  Serial.begin(115200);
  
  // Initialise I2C
  Wire.begin(I2C_ADDRESS);
  Wire.onRequest(requestEvent);
  Wire.onReceive(receiveEvent);
  
  Serial.println("I2C Bus Initialized");
  
  // Produce list of connected sensors
  size_t length;
  for (int i = 0; i < LENGTH(sensors); i++)
  {
    length += strlen(sensors[i].name) + 1; // +1 for separation character \n
  } 
  sensorList = (char *)malloc(length);
  sensorList[0] = '\0';
  for (int i = 0; i < LENGTH(sensors); i++)
  {
    strcat(sensorList, sensors[i].name);
    strcat(sensorList, "\n");
  }
  
  // Now call the user's code
  your_setup();
}

void loop()
{
  your_loop();
}


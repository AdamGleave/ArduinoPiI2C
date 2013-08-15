/**************************** INSERT YOUR CODE HERE ***************************/

/* This is example code. It stores the (approximate) time the Arduino has been running into sensorVal1.
 * sensorVal2 contains a brief string description of how long the Arduino has been running.
 * You can then access both values over I2C, e.g. using the Raspberry Pi.
 *
 * To use your own code, delete the code below.
 * Then, copy and paste your setup() and loop() functions.
 * Finally, rename them to your_setup() and your_loop().
 */

float sensorVal1;
char *sensorVal2;

void your_setup()
{
  sensorVal1 = 0.0;
  sensorVal2 = "Just started";
}

void your_loop()
{
  sensorVal1 = sensorVal1 + 1.0;
  
  if (sensorVal1 < 1000)
  {
    sensorVal2 = "Running for < 1 s";
  }
  else 
  {
    sensorVal2 = "Running for >1 s";
  }
  delay(1);
}

/************************* CONFIGURATION -- EDIT THIS! *************************/

// Do NOT need to change the next two things
enum datatype {
  FLOAT,
  INT,
  STRING
};

typedef struct {
  const char *name;
  enum datatype type;
  void *value;
} sensor;

// DO need to change the two things below
#define I2C_ADDRESS 42 // must be between 8 and 119. Make sure this is different to other devices you connect!

/* To add a new sensor:
 * 1. Uncomment a line below, by removing the // before it. Otherwise, the line is ignored.
 *
 * 2. Each line consists of three values, e.g:
           {"SENSOR1", FLOAT, &sensorVal1}
                ^         ^          ^
                |         |          |
                |         |          |
              Name    Datatype   Variable             
 * 3. Change the name to something which describes what you're sending, e.g. change SENSOR1 to TEMPERATURE.
 *
 *    IMPORTANT: Keep the double quotes (") either side of the name -- it means it is a string, not an identifier.
 * 4. Change the variable to the identifier you're using to store your value.
 *    e.g. if your loop stores the temperature to temp_c, then change &sensorVal1 to &temp_c.
 *
 *    IMPORTANT: Keep the & before the variable (look up 'pointers' to understand why this is necessary.)
 *  5. Change the datatype to one of FLOAT, INT or STRING depending on the type of your variable. 
 *     The type is before your variable. e.g. if you declare your variable like:
 *         float sensorVal1; // in the example code
 *     then the datatype should be FLOAT. If it was declared like:
 *          int sensorVal1; 
 *     then the datatype should be INT. If it is declared like:
 *          char sensorVal1[32];
 *     OR:
 *          char *sensorVal1;
 *     then the datatype should be STRING.
 */
sensor sensors[] = {
                      {"SENSOR1", FLOAT, &sensorVal1},
                      {"SENSOR2", STRING, &sensorVal2},
                      //{"SENSOR3", FLOAT, &sensorVal3},
                      //{"SENSOR4", FLOAT, &sensorVal4},
                      //{"SENSOR5", STRING, &sensorVal5},
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
    /* There will be problems using I2C if we don't respond within a fixed period of time
     * so send a zero, which we program the master to ignore. This makes sure we have
     * enough time to do some computation. */
    Wire.write(0);
    
    for (int i = 0; i < LENGTH(sensors); i++)
    {
      sensor aSensor = sensors[i];
      
      if (strcmp(request, aSensor.name) == 0)
      { // match
        float responseFloat;
        int responseInt;
        switch (aSensor.type)
        { // perform conversion to string depending on data type
          case FLOAT:
            responseFloat = *((float *)aSensor.value);
            dtostrf(responseFloat, CONVERSION_WIDTH, CONVERSION_PRECISION, responseBuf);
            responseStr = responseBuf;
            break;
          case INT:
            responseInt = *((int *)aSensor.value);
            itoa(responseInt, responseBuf, 10);
            responseStr = responseBuf;
            break;
          case STRING:
            // it would make more sense to point directly to a string (char *)
            // than a pointer to a pointer to a string (char **),
            // but use the latter to keep things consistent in configuration
            responseStr = *((char **)aSensor.value);
            break;
          default:
            Serial.println("ERROR: Unrecognised sensor data type.");          
            break;
        }
        
        break; // leave for loop
      }
    }
    
    if (!responseStr) { // no match
      if (strcmp(request, "?") == 0)
      {
        responseStr = sensorList;  
      }
      else if (strcmp(request, "TEST") == 0) {
        responseStr = "HELLO";
      }
      else
      { // not a recognised sensor or built-in command
        responseStr = "ERR"; 
      }
    }
      
    Serial.print("Read ");
    Serial.println(request);
    posIn = posOut = 0;
    request[0] = 0;
  }
  else
  {
    if (responseStr[posOut] != '\0')
    {
      Wire.write(responseStr[posOut++]);
    } 
    else
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
    strcat(sensorList, "\t");
  }
  
  // Now call the user's code
  your_setup();
}

void loop()
{
  your_loop();
}


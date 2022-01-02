#include <Wire.h>

//#if ESP8266
//  #define SDA 4 // D2 - A4 - GPIO4
//  #define SCL 5 // D1 - A5 - GPIO5
//#endif
//#if ESP32
//  #define SDA 21
//  #define SCL 22
//#endif
//#define USBI2C_ADDR 0
#define I2CS_START_ADDR 1
#define WIRE_MAX 127
#define WIRE_CLOCK 100000

void wire_setup()
{
//    Wire.begin(SDA, SCL, USBI2C_ADDR);
//    Wire.begin(SDA, SCL);
    Wire.begin();
    Wire.setClock(WIRE_CLOCK);
}

void scan_i2c() {
    // this should serial print 
    // Scan I2CS address [1 .. 127]
    // 00 01 02 .. ff \n
    byte address, error;
    bool found = false;

    SerialPrintln("Scanning I2CS address ["+String(I2CS_START_ADDR)+" .. "+String(WIRE_MAX)+"]");
    for (address = I2CS_START_ADDR; address < WIRE_MAX; address++) {
        Wire.beginTransmission(address);
        error = Wire.endTransmission();

        if (error == 0) {
            found = true;
            if (address < 16)
                Serial.print("0");
            SERIAL_LOGGER.print(address, HEX);
            SERIAL_LOGGER.print(" ");
        }
    }

    if (found == false)
        SERIAL_LOGGER.println("no I2CS detected");
    else
        SERIAL_LOGGER.print("\n");
}

void wire_flush(int address) {
    byte i = 0;
    
    SerialPrintln("Flush I2CS data from ["+String(address)+"]");
    while (i++ < 40) {
        wire_setup();
        Wire.requestFrom(address, 1);
        while (Wire.available())
            Wire.read();
    }
}

void wire_send(byte address, char *msg) {
    wire_setup();
    Wire.beginTransmission(address);
    Wire.write(msg);
    Wire.endTransmission();
}

void wire_read(int address) {
    char c = '\n';
    wire_setup();
    Wire.requestFrom(address, 1);
    if (address < 16)
        SERIAL_LOGGER.print("0");
    SERIAL_LOGGER.print(address, HEX);
    SERIAL_LOGGER.print(":");
    if (Wire.available())
        c = Wire.read();
    SERIAL_LOGGER.print(String(c));
    SERIAL_LOGGER.print(LINE_EOL);
}

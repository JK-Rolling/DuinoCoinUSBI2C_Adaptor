/*
 * DuinoCoin_USBI2C_Adaptor.ino
 * 
 * JK Rolling
 * 31-Dec-2021
 * https://github.com/JK-Rolling/DuinoCoinUSBI2C_Adaptor
 * v0.1
 * 
 * this code should make the AVR/ESP with USB-Serial capability to passthrough Serial data command
 * to I2C bus. the command should be similar to I2C format. the read/write data length is always 1.
 * for write - address:write:1-byte data$. e.g. 1:w:a$
 *           - I2CS should see address=1, direction=write, data=a
 * for read - address:read$ e.g. 1:r$
 *          - I2CS should see address=1, direction=1
 * for scan - scn$ - scan I2CS range 1-127. address 0 is reserved.
 * 
 * I2CS Duino-Coin Miner code
 * https://github.com/JK-Rolling/DuinoCoinI2C_RPI
 */
//#define DEBUG_ON

// BAUDRATE 115200 should match I2C 100KHz
// other BAUDRATE includes 128000, 153600, 230400, 460800, 921600, 1500000, 2000000
#define BAUDRATE 115200

#ifdef DEBUG_ON
  #define SerialBegin()              Serial.begin(115200);
  #define SerialPrint(x)             Serial.print(x);
  #define SerialPrintln(x)           Serial.println(x);
#else
  #define SerialBegin()
  #define SerialPrint(x)
  #define SerialPrintln(x)
#endif

#if ESP8266
  #define LED_ON LOW
  #define LED_OFF HIGH  
#else
  #define LED_ON HIGH
  #define LED_OFF LOW
#endif
#define ON true
#define OFF false
#define LINE_SEP '$'

// max usb_data length could be 8. e.g 127:w:f$
const byte num_chars = 9;
static char usb_data[num_chars];
static bool new_data = false;

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  led(OFF);
  Serial.begin(BAUDRATE);
  Serial.setTimeout(10000);
  wire_setup();
  while (!Serial);
  Serial.flush();
  SerialPrintln("\nStartup Done!");
}

void loop() {
    recv_usb();
    process_usb_data();
}

void recv_usb() {
    static byte idx = 0;
    char rc;

    while (Serial.available() > 0 && new_data == false) {
        rc = Serial.read();

        if (rc != LINE_SEP) {
            usb_data[idx++] = rc;
            if (idx >= num_chars) {
                idx = num_chars - 1;
            }
        }
        else {
            usb_data[idx] = '\0';
            idx = 0;
            new_data = true;
            SerialPrintln("Received USB:["+String(usb_data)+LINE_SEP+"]");
        }
    }
}

void process_usb_data() {
    char * idx;
    char delimiter[] = ":";

    if (new_data) {
        // command | I2CS address
        char *usb_cmd = strtok(usb_data,delimiter);
    
        // direction
        char *usbi2c_rw = strtok(NULL,delimiter);
    
        // data
        char *usbi2c_data = strtok(NULL,delimiter);
        
        bool wire_sent = usbi2c(usb_cmd, usbi2c_rw, usbi2c_data);
        led(OFF);
        new_data = false; 
    }
}

bool usbi2c(char * cmd, char * rw, char * wdata) {
    byte i2cs_addr;
    
    if (cmd == NULL) {
        SerialPrintln("USB cmd corrupted");
        return false;
    }
    SerialPrintln("usbi2c usb_cmd: ["+String(cmd) + "]");
    if (strcmp(cmd, "scn") == 0) {
        led(ON);
        scan_i2c();
    }
    else {
        if (rw == NULL) {
            SerialPrintln("USB rw corrupted");
            return false;
        }
        i2cs_addr = atoi(cmd);

        if (atoi(cmd) > 127 || i2cs_addr == 0) {
            SerialPrintln("Invalid address range:["+String(cmd)+"]");
            return false;
        }
        
        if (strcmp(rw, "w") == 0) {
            if (wdata == NULL) {
                SerialPrintln("USB wdata corrupted");
                return false;
            }
            SerialPrintln("I2C Write:["+String(rw)+"] with address:["+String(i2cs_addr)+"]  data:["+String(wdata)+"]");
            led(ON);
            wire_send(i2cs_addr, wdata);
        }
        else if (strcmp(rw, "r") == 0) {
            SerialPrintln("I2C Read:["+String(rw)+"] with address:["+String(i2cs_addr)+"]");
            led(ON);
            wire_read(i2cs_addr);
        }
        else {
            SerialPrintln("Unrecognized operation  cmd:["+String(cmd)+"]  rw:["+String(rw)+"]  data:["+String(wdata)+"]");
        }
    }
    return true;
}

void led(bool state) {
    if (state) {
        #if defined(ARDUINO_ARCH_AVR)
            PORTB = PORTB & B11011111;
        #else
            digitalWrite(LED_BUILTIN, LED_ON);
        #endif
    }
    else {
        #if defined(ARDUINO_ARCH_AVR)
            PORTB = PORTB | B00100000;
        #else
            digitalWrite(LED_BUILTIN, LED_OFF);
        #endif
    }
}

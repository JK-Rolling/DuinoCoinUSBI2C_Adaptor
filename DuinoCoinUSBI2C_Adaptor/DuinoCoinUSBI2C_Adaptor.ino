/*
 * DuinoCoin_USBI2C_Adaptor.ino
 * 
 * JK Rolling
 * 31-Dec-2021
 * https://github.com/JK-Rolling/DuinoCoinUSBI2C_Adaptor
 * v0.2 - support i2c bus flush, add source i2cs addr to wire_read()
 * v0.1 - alpha version
 * 
 * this code should make the AVR/ESP with USB-Serial capability to passthrough Serial data command
 * to I2C bus. the command should be similar to I2C format. the read/write data length is always 1.
 * for write - address:write:1-byte data$. e.g. 1:w:a$
 *           - I2CS should see address=1, direction=write, data=a
 * for read - address:read$ e.g. 1:r$
 *          - I2CS should see address=1, direction=1
 * for scan - scn$ - scan I2CS range 1-127. address 0 is reserved
 * for flush - fl - flush 40 bytes from target I2CS
 * 
 * I2CS Duino-Coin Miner code
 * https://github.com/JK-Rolling/DuinoCoinI2C_RPI
 */
//#define DEBUG_ON
#pragma GCC optimize ("-Ofast")
#define BAUDRATE 115200

#define SERIAL_LOGGER Serial
#ifdef DEBUG_ON
  #define SerialPrint(x)             SERIAL_LOGGER.print(x);
  #define SerialPrintln(x)           SERIAL_LOGGER.println(x);
#else
  #define SerialPrint(x)
  #define SerialPrintln(x)
#endif

#define LINE_EOL '$'

const byte num_chars = 9;
static char usb_data[num_chars];
static bool new_data = false;

void setup() {
  SERIAL_LOGGER.begin(BAUDRATE);
  SERIAL_LOGGER.setTimeout(10000);
  wire_setup();
  while (!SERIAL_LOGGER);
  SERIAL_LOGGER.flush();
  SerialPrintln("\nStartup Done!");
}

void loop() {
    recv_usb();
    process_usb_data();
}

void recv_usb() {
    static byte idx = 0;
    char rc;

    while (SERIAL_LOGGER.available() > 0 && new_data == false) {
        rc = SERIAL_LOGGER.read();

        if (rc != LINE_EOL) {
            usb_data[idx++] = rc;
            if (idx >= num_chars) {
                idx = num_chars - 1;
            }
        }
        else {
            usb_data[idx] = '\0';
            idx = 0;
            new_data = true;
            SerialPrintln("Received USB:["+String(usb_data)+LINE_EOL+"]");
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
    
        // data | flush target address
        char *usbi2c_data = strtok(NULL,delimiter);
        
        bool wire_sent = usbi2c(usb_cmd, usbi2c_rw, usbi2c_data);
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
        scan_i2c();
    }
    else if (strcmp(cmd, "fl") == 0) {
        i2cs_addr = atoi(wdata);
        if (atoi(wdata) > 127 || i2cs_addr == 0) {
            SerialPrintln("Invalid address range:["+String(wdata)+"]");
            return false;
        }
        wire_flush(i2cs_addr);
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
            wire_send(i2cs_addr, wdata);
        }
        else if (strcmp(rw, "r") == 0) {
            SerialPrintln("I2C Read:["+String(rw)+"] with address:["+String(i2cs_addr)+"]");
            wire_read(i2cs_addr);
        }
        else {
            SerialPrintln("Unrecognized operation  cmd:["+String(cmd)+"]  rw:["+String(rw)+"]  data:["+String(wdata)+"]");
        }
    }
    return true;
}

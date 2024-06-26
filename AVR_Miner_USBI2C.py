#!/usr/bin/env python3
"""
USBI2C AVR Miner 4.1 © MIT licensed
Modified by JK-Rolling
20220101

Full credit belong to
https://duinocoin.com
https://github.com/revoxhere/duino-coin
Duino-Coin Team & Community 2019-2024
"""

from os import _exit, mkdir
from os import name as osname
from os import path
from os import system as ossystem
from platform import machine as osprocessor
from platform import system
import sys

from configparser import ConfigParser
from pathlib import Path

from json import load as jsonload
import json
from locale import LC_ALL, getdefaultlocale, getlocale, setlocale

from re import sub
from socket import socket
from datetime import datetime
from statistics import mean
from signal import SIGINT, signal
from time import ctime, sleep, strptime, time
import pip

from subprocess import DEVNULL, Popen, check_call, call
from threading import Thread
from threading import Lock as thread_lock
from threading import Semaphore

import base64 as b64

import os
printlock = Semaphore(value=1)
serlock = Semaphore(value=1)

# Python <3.5 check
f"Your Python version is too old. Duino-Coin Miner requires version 3.6 or above. Update your packages and try again"


def install(package):
    try:
        pip.main(["install",  package])
    except AttributeError:
        check_call([sys.executable, '-m', 'pip', 'install', package])
    call([sys.executable, __file__])

try:
    from serial import Serial
    import serial.tools.list_ports
except ModuleNotFoundError:
    print("Pyserial is not installed. "
          + "Miner will try to automatically install it "
          + "If it fails, please manually execute "
          + "python3 -m pip install pyserial")
    install('pyserial')

try:
    import requests
except ModuleNotFoundError:
    print("Requests is not installed. "
          + "Miner will try to automatically install it "
          + "If it fails, please manually execute "
          + "python3 -m pip install requests")
    install('requests')

try:
    from colorama import Back, Fore, Style, init
    init(autoreset=True)
except ModuleNotFoundError:
    print("Colorama is not installed. "
          + "Miner will try to automatically install it "
          + "If it fails, please manually execute "
          + "python3 -m pip install colorama")
    install("colorama")

try:
    from pypresence import Presence
except ModuleNotFoundError:
    print("Pypresence is not installed. "
          + "Miner will try to automatically install it "
          + "If it fails, please manually execute "
          + "python3 -m pip install pypresence")
    install("pypresence")


def now():
    return datetime.now()


def port_num(com):
    #return str(''.join(filter(str.isdigit, com)))
    return com


class Settings:
    VER = '4.1'
    SOC_TIMEOUT = 15
    REPORT_TIME = 60
    AVR_TIMEOUT = 10  # diff 16 * 100 / 269 h/s = 5.94 s
    DELAY_START = 10  # 60 seconds start delay between worker to help kolka sync efficiency drop
    CRC8_EN = "y"
    BAUDRATE = 115200
    DATA_DIR = "Duino-Coin AVR Miner " + str(VER)
    SEPARATOR = ","
    USBI2C_SEPARATOR = ":"
    USBI2C_EOL = "$"
    ENCODING = "utf-8"
    try:
        # Raspberry Pi latin users can't display this character
        "‖".encode(sys.stdout.encoding)
        BLOCK = " ‖ "
    except:
        BLOCK = " | "
    PICK = ""
    COG = " @"
    if (osname != "nt"
        or bool(osname == "nt"
                and os.environ.get("WT_SESSION"))):
        # Windows' cmd does not support emojis, shame!
        # And some codecs same, for example the Latin-1 encoding don`t support emoji
        try:
            "⛏ ⚙".encode(sys.stdout.encoding) # if the terminal support emoji
            PICK = " ⛏"
            COG = " ⚙"
        except UnicodeEncodeError: # else
            PICK = ""
            COG = " @"

def check_mining_key(user_settings):
    user_settings = user_settings["AVR Miner"]

    if user_settings["mining_key"] != "None":
        key = "&k=" + b64.b64decode(user_settings["mining_key"]).decode('utf-8')
    else:
        key = ''

    response = requests.get(
        "https://server.duinocoin.com/mining_key"
            + "?u=" + user_settings["username"]
            + key,
        timeout=10
    ).json()

    if response["success"] and not response["has_key"]: # if the user doesn't have a mining key
        user_settings["mining_key"] = "None"
        config["AVR Miner"] = user_settings

        with open(Settings.DATA_DIR + '/Settings.cfg',
            "w") as configfile:
            config.write(configfile)
            print("sys0",
                Style.RESET_ALL + get_string("config_saved"),
                "info")
        return

    if not response["success"]:
        if user_settings["mining_key"] == "None":
            pretty_print(
                "sys0",
                get_string("mining_key_required"),
                "warning")

            mining_key = input("Enter your mining key: ")
            user_settings["mining_key"] = b64.b64encode(mining_key.encode("utf-8")).decode('utf-8')
            config["AVR Miner"] = user_settings

            with open(Settings.DATA_DIR + '/Settings.cfg',
                      "w") as configfile:
                config.write(configfile)
                print("sys0",
                    Style.RESET_ALL + get_string("config_saved"),
                    "info")
            check_mining_key(config)
        else:
            pretty_print(
                "sys0",
                get_string("invalid_mining_key"),
                "error")

            retry = input("Do you want to retry? (y/n): ")
            if retry == "y" or retry == "Y":
                mining_key = input("Enter your mining key: ")
                user_settings["mining_key"] = b64.b64encode(mining_key.encode("utf-8")).decode('utf-8')
                config["AVR Miner"] = user_settings

                with open(Settings.DATA_DIR + '/Settings.cfg',
                        "w") as configfile:
                    config.write(configfile)
                print("sys0",
                    Style.RESET_ALL + get_string("config_saved"),
                    "info")
                sleep(1.5)
                check_mining_key(config)
            else:
                return
                
                
class Client:
    """
    Class helping to organize socket connections
    """
    def connect(pool: tuple):
        s = socket()
        s.settimeout(Settings.SOC_TIMEOUT)
        s.connect((pool))
        return s

    def send(s, msg: str):
        sent = s.sendall(str(msg).encode(Settings.ENCODING))
        return True

    def recv(s, limit: int = 128):
        data = s.recv(limit).decode(Settings.ENCODING).rstrip("\n")
        return data

    def fetch_pool():
        while True:
            pretty_print("net0", " " + get_string("connection_search"),
                         "info")
            try:
                response = requests.get(
                    "https://server.duinocoin.com/getPool",
                    timeout=10).json()

                if response["success"] == True:
                    pretty_print("net0", get_string("connecting_node")
                                 + response["name"],
                                 "info")

                    NODE_ADDRESS = response["ip"]
                    NODE_PORT = response["port"]
                    debug_output(f"Fetched pool: {response['name']}")
                    return (NODE_ADDRESS, NODE_PORT)

                elif "message" in response:
                    pretty_print(f"Warning: {response['message']}"
                                 + ", retrying in 15s", "warning", "net0")
                    sleep(15)
                else:
                    raise Exception(
                        "no response - IP ban or connection error")
            except Exception as e:
                if "Expecting value" in str(e):
                    pretty_print("net0", get_string("node_picker_unavailable")
                                 + f"15s {Style.RESET_ALL}({e})",
                                 "warning")
                else:
                    pretty_print("net0", get_string("node_picker_error")
                                 + f"15s {Style.RESET_ALL}({e})",
                                 "error")
                sleep(15)


class Donate:
    def load(donation_level):
        if donation_level > 0:
            if osname == 'nt':
                if not Path(
                        f"{Settings.DATA_DIR}/Donate.exe").is_file():
                    url = ('https://server.duinocoin.com/'
                           + 'donations/DonateExecutableWindows.exe')
                    r = requests.get(url, timeout=15)
                    with open(f"{Settings.DATA_DIR}/Donate.exe",
                              'wb') as f:
                        f.write(r.content)
            elif osname == "posix":
                if osprocessor() == "aarch64":
                    url = ('https://server.duinocoin.com/'
                           + 'donations/DonateExecutableAARCH64')
                elif osprocessor() == "armv7l":
                    url = ('https://server.duinocoin.com/'
                           + 'donations/DonateExecutableAARCH32')
                else:
                    url = ('https://server.duinocoin.com/'
                           + 'donations/DonateExecutableLinux')
                if not Path(
                        f"{Settings.DATA_DIR}/Donate").is_file():
                    r = requests.get(url, timeout=15)
                    with open(f"{Settings.DATA_DIR}/Donate",
                              "wb") as f:
                        f.write(r.content)

    def start(donation_level):
        donation_settings = requests.get(
            "https://server.duinocoin.com/donations/settings.json").json()

        if os.name == 'nt':
            cmd = (f'cd "{Settings.DATA_DIR}" & Donate.exe '
                   + f'-o {donation_settings["url"]} '
                   + f'-u {donation_settings["user"]} '
                   + f'-p {donation_settings["pwd"]} '
                   + f'-s 4 -e {donation_level*2}')
        elif os.name == 'posix':
            cmd = (f'cd "{Settings.DATA_DIR}" && chmod +x Donate '
                   + '&& nice -20 ./Donate '
                   + f'-o {donation_settings["url"]} '
                   + f'-u {donation_settings["user"]} '
                   + f'-p {donation_settings["pwd"]} '
                   + f'-s 4 -e {donation_level*2}')

        if donation_level <= 0:
            pretty_print(
                'sys0', Fore.YELLOW
                + get_string('free_network_warning').lstrip()
                + get_string('donate_warning').replace("\n", "\n\t\t")
                + Fore.GREEN + 'https://duinocoin.com/donate'
                + Fore.YELLOW + get_string('learn_more_donate'),
                'warning')
            sleep(5)

        if donation_level > 0:
            debug_output(get_string('starting_donation'))
            donateExecutable = Popen(cmd, shell=True, stderr=DEVNULL)
            pretty_print('sys0',
                         get_string('thanks_donation').replace("\n", "\n\t\t"),
                         'error')


shares = [0, 0, 0]
bad_crc8 = 0
i2c_retry_count = 0
hashrate_mean = []
ping_mean = []
diff = 0
shuffle_ports = "y"
donator_running = False
job = ''
debug = 'n'
discord_presence = 'y'
rig_identifier = 'None'
donation_level = 0
hashrate = 0
config = ConfigParser()
mining_start_time = time()

if not path.exists(Settings.DATA_DIR):
    mkdir(Settings.DATA_DIR)

if not Path(Settings.DATA_DIR + '/Translations.json').is_file():
    url = ('https://raw.githubusercontent.com/'
           + 'revoxhere/'
           + 'duino-coin/master/Resources/'
           + 'AVR_Miner_langs.json')
    r = requests.get(url, timeout=5)
    with open(Settings.DATA_DIR + '/Translations.json', 'wb') as f:
        f.write(r.content)

# Load language file
with open(Settings.DATA_DIR + '/Translations.json', 'r',
          encoding='utf8') as lang_file:
    lang_file = jsonload(lang_file)

# OS X invalid locale hack
if system() == 'Darwin':
    if getlocale()[0] is None:
        setlocale(LC_ALL, 'en_US.UTF-8')

try:
    if not Path(Settings.DATA_DIR + '/Settings.cfg').is_file():
        locale = getdefaultlocale()[0]
        if locale.startswith('es'):
            lang = 'spanish'
        elif locale.startswith('sk'):
            lang = 'slovak'
        elif locale.startswith('ru'):
            lang = 'russian'
        elif locale.startswith('pl'):
            lang = 'polish'
        elif locale.startswith('de'):
            lang = 'german'
        elif locale.startswith('fr'):
            lang = 'french'
        elif locale.startswith('jp'):
            lang = 'japanese'
        elif locale.startswith('tr'):
            lang = 'turkish'
        elif locale.startswith('it'):
            lang = 'italian'
        elif locale.startswith('pt'):
            lang = 'portuguese'
        if locale.startswith("zh_TW"):
            lang = "chinese_Traditional"
        elif locale.startswith('zh'):
            lang = 'chinese_simplified'
        elif locale.startswith('th'):
            lang = 'thai'
        elif locale.startswith('az'):
            lang = 'azerbaijani'
        elif locale.startswith('nl'):
            lang = 'dutch'
        elif locale.startswith('ko'):
            lang = 'korean'
        elif locale.startswith("id"):
            lang = "indonesian"
        elif locale.startswith("cz"):
            lang = "czech"
        elif locale.startswith("fi"):
            lang = "finnish"
        else:
            lang = 'english'
    else:
        try:
            config.read(Settings.DATA_DIR + '/Settings.cfg')
            lang = config["AVR Miner"]['language']
        except Exception:
            lang = 'english'
except:
    lang = 'english'


def get_string(string_name: str):
    if string_name in lang_file[lang]:
        return lang_file[lang][string_name]
    elif string_name in lang_file['english']:
        return lang_file['english'][string_name]
    else:
        return string_name


def get_prefix(symbol: str,
               val: float,
               accuracy: int):
    """
    H/s, 1000 => 1 kH/s
    """
    if val >= 1_000_000_000_000:  # Really?
        val = str(round((val / 1_000_000_000_000), accuracy)) + " T"
    elif val >= 1_000_000_000:
        val = str(round((val / 1_000_000_000), accuracy)) + " G"
    elif val >= 1_000_000:
        val = str(round((val / 1_000_000), accuracy)) + " M"
    elif val >= 1_000:
        val = str(round((val / 1_000))) + " k"
    else:
        if symbol:
            val = str(round(val)) + " "
        else:
            val = str(round(val))
    return val + symbol


def debug_output(text: str):
    if debug == 'y':
        print(Style.RESET_ALL + Fore.WHITE
              + now().strftime(Style.DIM + '%H:%M:%S.%f ')
              + Style.NORMAL + f'DEBUG: {text}')

def ondemand_print(text: str):
    print(Style.RESET_ALL + Fore.WHITE
          + now().strftime(Style.DIM + '%H:%M:%S.%f ')
          + Style.NORMAL + f'DEBUG: {text}')

def title(title: str):
    if osname == 'nt':
        """
        Changing the title in Windows' cmd
        is easy - just use the built-in
        title command
        """
        ossystem('title ' + title)
    else:
        """
        Most *nix terminals use
        this escape sequence to change
        the console window title
        """
        try:
            print('\33]0;' + title + '\a', end='')
            sys.stdout.flush()
        except Exception as e:
            print(e)


def handler(signal_received, frame):
    pretty_print(
        'sys0', get_string('sigint_detected')
        + Style.NORMAL + Fore.RESET
        + get_string('goodbye'), 'warning')

    _exit(0)


# Enable signal handler
signal(SIGINT, handler)


def load_config():
    global username
    global donation_level
    global avrport
    global hashrate_list
    global debug
    global rig_identifier
    global discord_presence
    global shuffle_ports
    global SOC_TIMEOUT
    global ser
    global usbi2c_port
    global usbi2c_baudrate

    if not Path(str(Settings.DATA_DIR) + '/Settings.cfg').is_file():
        print(
            Style.BRIGHT + get_string('basic_config_tool')
            + Settings.DATA_DIR
            + get_string('edit_config_file_warning'))

        print(
            Style.RESET_ALL + get_string('dont_have_account')
            + Fore.YELLOW + get_string('wallet') + Fore.RESET
            + get_string('register_warning'))

        correct_username = False
        while not correct_username:
            username = input(
                Style.RESET_ALL + Fore.YELLOW
                + get_string('ask_username')
                + Fore.RESET + Style.BRIGHT)
            if not username:
                username = choice(["revox", "Bilaboz"])

            r = requests.get(f"https://server.duinocoin.com/users/{username}", 
                             timeout=Settings.SOC_TIMEOUT).json()
            correct_username = r["success"]
            if not correct_username:
                print(get_string("incorrect_username"))

        response = requests.get(
            "https://server.duinocoin.com/mining_key"
                + "?u=" + username, timeout=10
        ).json()

        mining_key = "None"
        if response["has_key"]:
            mining_key = input(Style.RESET_ALL + Fore.YELLOW
                           + get_string("ask_mining_key")
                           + Fore.RESET + Style.BRIGHT)
            mining_key = b64.b64encode(mining_key.encode("utf-8")).decode('utf-8')

        print(Style.RESET_ALL + Fore.YELLOW
              + get_string('ports_message'))
        portlist = serial.tools.list_ports.comports(include_links=True)

        for port in portlist:
            print(Style.RESET_ALL
                  + Style.BRIGHT + Fore.RESET
                  + '  ' + str(port))
        print(Style.RESET_ALL + Fore.YELLOW
              + get_string('ports_notice'))

        port_names = []
        for port in portlist:
            port_names.append(port.device)
            
        usbi2c_port = ''
        while True:
            current_port = input(
                Style.RESET_ALL + Fore.YELLOW
                + get_string('ask_avrport')
                + Fore.RESET + Style.BRIGHT)
                      

            if current_port in port_names:
                usbi2c_port += current_port
                break
            else:
                print(Style.RESET_ALL + Fore.RED
                      + 'Please enter a valid COM port from the list above')
        
        try:
            ser.close()
            sleep(2)
        except:
            pass
            
        usbi2c_baudrate = input(
            Style.RESET_ALL + Fore.YELLOW
            + str("USBI2C Baudrate (e.g. 115200): ")
            + Fore.RESET + Style.BRIGHT)
        Settings.BAUDRATE = int(usbi2c_baudrate)
            
        try:
            ser = Serial(usbi2c_port, baudrate=int(Settings.BAUDRATE),
                         timeout=float(Settings.AVR_TIMEOUT))
            sleep(2)
        except Exception as e:
            pretty_print(
                    'sys'
                    + port_num(usbi2c_port),
                    get_string('board_connection_error')
                    + str(usbi2c_port)
                    + get_string('board_connection_error2')
                    + Style.NORMAL
                    + Fore.RESET
                    + f' (avr connection err: {e})',
                    'error')
            raise Exception("USBI2C Adaptor port access failure")

        try:
            ser.write(bytes(str("scn"+ Settings.USBI2C_EOL),
                        encoding=Settings.ENCODING))
            sleep(1)
            debug_output(usbi2c_port + ': Reading I2CS scan result from the board')
            result = ser.read_until(b'\n').decode()
            ser.flush()
        except Exception as e:
            debug_output(usbi2c_port + f': USBI2C scan failure: {e}')
            raise Exception("USBI2C Adaptor I2CS address scan failure")
        finally:
            ser.close()
            
        print(Style.RESET_ALL
                  + Style.BRIGHT + Fore.RESET
                  + '  ' + str(result))
                
        avrport = ''
        while True:
            current_port = input(
                Style.RESET_ALL + Fore.YELLOW
                + 'Enter your I2C slave address (e.g. 8): '
                + Fore.RESET + Style.BRIGHT)

            avrport += current_port
            confirmation = input(
                Style.RESET_ALL + Fore.YELLOW
                + get_string('ask_anotherport')
                + Fore.RESET + Style.BRIGHT)

            if confirmation == 'y' or confirmation == 'Y':
                avrport += ','
            else:
                break
                
        Settings.CRC8_EN = input(
            Style.RESET_ALL + Fore.YELLOW
            + 'Do you want to turn on CRC8 feature? (Y/n): '
            + Fore.RESET + Style.BRIGHT)
        Settings.CRC8_EN = Settings.CRC8_EN.lower()
        if len(Settings.CRC8_EN) == 0: Settings.CRC8_EN = "y"
        elif Settings.CRC8_EN != "y": Settings.CRC8_EN = "n"
        
        rig_identifier = input(
            Style.RESET_ALL + Fore.YELLOW
            + get_string('ask_rig_identifier')
            + Fore.RESET + Style.BRIGHT)
        if rig_identifier == 'y' or rig_identifier == 'Y':
            rig_identifier = input(
                Style.RESET_ALL + Fore.YELLOW
                + get_string('ask_rig_name')
                + Fore.RESET + Style.BRIGHT)
        else:
            rig_identifier = 'None'

        donation_level = '0'
        if osname == 'nt' or osname == 'posix':
            donation_level = input(
                Style.RESET_ALL + Fore.YELLOW
                + get_string('ask_donation_level')
                + Fore.RESET + Style.BRIGHT)

        donation_level = sub(r'\D', '', donation_level)
        if donation_level == '':
            donation_level = 1
        if float(donation_level) > int(5):
            donation_level = 5
        if float(donation_level) < int(0):
            donation_level = 0
        donation_level = int(donation_level)

        config["AVR Miner"] = {
            'username':         username,
            'avrport':          avrport,
            'donate':           donation_level,
            'language':         lang,
            'identifier':       rig_identifier,
            'debug':            'n',
            "soc_timeout":      45,
            "avr_timeout":      10,
            "delay_start":      Settings.DELAY_START,
            "crc8_en":          Settings.CRC8_EN,
            "discord_presence": "y",
            "periodic_report":  60,
            "shuffle_ports":    "y",
            "mining_key":       mining_key,
            "usbi2c_port":      usbi2c_port,
            "usbi2c_baudrate":  usbi2c_baudrate}

        with open(str(Settings.DATA_DIR)
                  + '/Settings.cfg', 'w') as configfile:
            config.write(configfile)

        avrport = avrport.split(',')
        print(Style.RESET_ALL + get_string('config_saved'))
        hashrate_list = [0] * len(avrport)

    else:
        config.read(str(Settings.DATA_DIR) + '/Settings.cfg')
        username = config["AVR Miner"]['username']
        avrport = config["AVR Miner"]['avrport']
        avrport = avrport.replace(" ", "").split(',')
        donation_level = int(config["AVR Miner"]['donate'])
        debug = config["AVR Miner"]['debug']
        rig_identifier = config["AVR Miner"]['identifier']
        Settings.SOC_TIMEOUT = int(config["AVR Miner"]["soc_timeout"])
        Settings.AVR_TIMEOUT = float(config["AVR Miner"]["avr_timeout"])
        Settings.DELAY_START = int(config["AVR Miner"]["delay_start"])
        Settings.CRC8_EN = config["AVR Miner"]["crc8_en"]
        discord_presence = config["AVR Miner"]["discord_presence"]
        shuffle_ports = config["AVR Miner"]["shuffle_ports"]
        Settings.REPORT_TIME = int(config["AVR Miner"]["periodic_report"])
        hashrate_list = [0] * len(avrport)
        usbi2c_port = config["AVR Miner"]['usbi2c_port']
        Settings.BAUDRATE = int(config["AVR Miner"]['usbi2c_baudrate'])


def greeting():
    global greeting
    print(Style.RESET_ALL)

    current_hour = strptime(ctime(time())).tm_hour
    if current_hour < 12:
        greeting = get_string('greeting_morning')
    elif current_hour == 12:
        greeting = get_string('greeting_noon')
    elif current_hour > 12 and current_hour < 18:
        greeting = get_string('greeting_afternoon')
    elif current_hour >= 18:
        greeting = get_string('greeting_evening')
    else:
        greeting = get_string('greeting_back')

    print(
        Style.DIM + Fore.MAGENTA
        + Settings.BLOCK + Fore.YELLOW
        + Style.BRIGHT + '\n  Unofficial Duino-Coin USBI2C AVR Miner'
        + Style.RESET_ALL + Fore.MAGENTA
        + f' {Settings.VER}' + Fore.RESET
        + ' 2021-2024')

    print(
        Style.DIM + Fore.MAGENTA
        + Settings.BLOCK + Style.NORMAL + Fore.MAGENTA
        + 'https://github.com/JK-Rolling  '
        + 'https://github.com/revoxhere/duino-coin')

    if lang != "english":
        print(
            Style.DIM + Fore.MAGENTA
            + Settings.BLOCK + Style.NORMAL
            + Fore.RESET + lang.capitalize()
            + " translation: " + Fore.MAGENTA
            + get_string("translation_autor"))

    print(
        Style.DIM + Fore.MAGENTA
        + Settings.BLOCK + Style.NORMAL
        + Fore.RESET + get_string('avr_on_port')
        + Style.BRIGHT + Fore.YELLOW
        + ', '.join(avrport))

    if osname == 'nt' or osname == 'posix':
        print(
            Style.DIM + Fore.MAGENTA + Settings.BLOCK
            + Style.NORMAL + Fore.RESET
            + get_string('donation_level') + Style.BRIGHT
            + Fore.YELLOW + str(donation_level))

    print(
        Style.DIM + Fore.MAGENTA
        + Settings.BLOCK + Style.NORMAL
        + Fore.RESET + get_string('algorithm')
        + Style.BRIGHT + Fore.YELLOW
        + 'DUCO-S1A ⚙ AVR diff')

    if rig_identifier != "None":
        print(
            Style.DIM + Fore.MAGENTA
            + Settings.BLOCK + Style.NORMAL
            + Fore.RESET + get_string('rig_identifier')
            + Style.BRIGHT + Fore.YELLOW + rig_identifier)

    print(
        Style.DIM + Fore.MAGENTA
        + Settings.BLOCK + Style.NORMAL
        + Fore.RESET + str(greeting) + ', '
        + Style.BRIGHT + Fore.YELLOW
        + str(username) + '!\n')


def init_rich_presence():
    # Initialize Discord rich presence
    global RPC
    try:
        RPC = Presence(905158274490441808)
        RPC.connect()
        Thread(target=update_rich_presence).start()
    except Exception as e:
        #print("Error launching Discord RPC thread: " + str(e))
        pass


def update_rich_presence():
    startTime = int(time())
    while True:
        try:
            total_hashrate = get_prefix("H/s", sum(hashrate_list), 2)
            RPC.update(details="Hashrate: " + str(total_hashrate),
                       start=mining_start_time,
                       state=str(shares[0]) + "/"
                       + str(shares[0] + shares[1])
                       + " accepted shares",
                       large_image="avrminer",
                       large_text="Duino-Coin, "
                       + "a coin that can be mined with almost everything"
                       + ", including AVR boards",
                       buttons=[{"label": "Visit duinocoin.com",
                                 "url": "https://duinocoin.com"},
                                {"label": "Join the Discord",
                                 "url": "https://discord.gg/k48Ht5y"}])
        except Exception as e:
            #print("Error updating Discord RPC thread: " + str(e))
            pass
        sleep(15)


def pretty_print(sender: str = "sys0",
                 msg: str = None,
                 state: str = "success"):
    """
    Produces nicely formatted CLI output for messages:
    HH:MM:S |sender| msg
    """
    if sender.startswith("net"):
        bg_color = Back.BLUE
    elif sender.startswith("avr"):
        bg_color = Back.MAGENTA
    else:
        bg_color = Back.GREEN

    if state == "success":
        fg_color = Fore.GREEN
    elif state == "info":
        fg_color = Fore.BLUE
    elif state == "error":
        fg_color = Fore.RED
    else:
        fg_color = Fore.YELLOW

    with thread_lock():
        printlock.acquire()
        print(Fore.WHITE + datetime.now().strftime(Style.DIM + "%H:%M:%S ")
              + bg_color + Style.BRIGHT + " " + sender + " "
              + Back.RESET + " " + fg_color + msg.strip())
        printlock.release()


def share_print(id, type, accept, reject, total_hashrate,
                computetime, diff, ping, reject_cause=None):
    """
    Produces nicely formatted CLI output for shares:
    HH:MM:S |avrN| ⛏ Accepted 0/0 (100%) ∙ 0.0s ∙ 0 kH/s ⚙ diff 0 k ∙ ping 0ms
    """
    try:
        diff = get_prefix("", int(diff), 0)
    except:
        diff = "?"

    try:
        total_hashrate = get_prefix("H/s", total_hashrate, 2)
    except:
        total_hashrate = "? H/s"

    if type == "accept":
        share_str = get_string("accepted")
        fg_color = Fore.GREEN
    elif type == "block":
        share_str = get_string("block_found")
        fg_color = Fore.YELLOW
    else:
        share_str = get_string("rejected")
        if reject_cause:
            share_str += f"{Style.NORMAL}({reject_cause}) "
        fg_color = Fore.RED

    with thread_lock():
        printlock.acquire()
        print(Fore.WHITE + datetime.now().strftime(Style.DIM + "%H:%M:%S ")
              + Fore.WHITE + Style.BRIGHT + Back.MAGENTA + Fore.RESET
              + " avr" + str(id) + " " + Back.RESET
              + fg_color + Settings.PICK + share_str + Fore.RESET
              + str(accept) + "/" + str(accept + reject) + Fore.MAGENTA
              + " (" + str(round(accept / (accept + reject) * 100)) + "%)"
              + Style.NORMAL + Fore.RESET
              + " ∙ " + str("%04.1f" % float(computetime)) + "s"
              + Style.NORMAL + " ∙ " + Fore.BLUE + Style.BRIGHT
              + str(total_hashrate) + Fore.RESET + Style.NORMAL
              + Settings.COG + f" diff {diff} ∙ " + Fore.CYAN
              + f"ping {(int(ping))}ms")
        printlock.release()

def usbi2c_write(ser,com,data):
    serlock.acquire()
    ser.write(bytes(str(str(com)
                        + Settings.USBI2C_SEPARATOR
                        + "w"
                        + Settings.USBI2C_SEPARATOR
                        + str(data)
                        + Settings.USBI2C_EOL),
                        encoding=Settings.ENCODING))
    serlock.release()
        
def usbi2c_read(ser,com):
    serlock.acquire()
    ser.write(bytes(str(str(com)
                        + Settings.USBI2C_SEPARATOR
                        + "r"
                        + Settings.USBI2C_EOL),
                        encoding=Settings.ENCODING))
    data = ser.read_until(b'$').decode().strip(Settings.USBI2C_EOL).split(Settings.USBI2C_SEPARATOR)
    serlock.release()
        
    return data
        
def flush_i2c(ser,com,period=2):
    # period is not useful here. ignore
    with thread_lock():
        usbi2c_write(ser,"fl",com)
        sleep(0.1)

def crc8(data):
    crc = 0
    for i in range(len(data)):
        byte = data[i]
        for b in range(8):
            fb_bit = (crc ^ byte) & 0x01
            if fb_bit == 0x01:
                crc = crc ^ 0x18
            crc = (crc >> 1) & 0x7f
            if fb_bit == 0x01:
                crc = crc | 0x80
            byte = byte >> 1
    return crc

result_pool = {}
def mine_avr(com, threadid, fastest_pool):
    global hashrate
    global bad_crc8
    global i2c_retry_count
    start_time = time()
    report_shares = 0
    last_report_share = 0
    last_bad_crc8 = 0
    last_i2c_retry_count = 0
    _com = hex(int(com,base=16)).replace("0x","")
    result_pool[_com] = ""
    
    while True:
        
        retry_counter = 0
        while True:
            try:
                if retry_counter > 3:
                    fastest_pool = Client.fetch_pool()
                    retry_counter = 0

                debug_output(f'Connecting to {fastest_pool}')
                s = Client.connect(fastest_pool)
                server_version = Client.recv(s, 6)

                if threadid == 0:
                    if float(server_version) <= float(Settings.VER):
                        pretty_print(
                            'net0', get_string('connected')
                            + Style.NORMAL + Fore.RESET
                            + get_string('connected_server')
                            + str(server_version) + ")",
                            'success')
                    else:
                        pretty_print(
                            'sys0', f"{get_string('miner_is_outdated')} (v{Settings.VER}) -"
                            + get_string('server_is_on_version')
                            + server_version + Style.NORMAL
                            + Fore.RESET + get_string('update_warning'),
                            'warning')
                        sleep(10)

                    Client.send(s, "MOTD")
                    motd = Client.recv(s, 1024)

                    if "\n" in motd:
                        motd = motd.replace("\n", "\n\t\t")

                    pretty_print("net" + str(threadid),
                                 get_string("motd") + Fore.RESET
                                 + Style.NORMAL + str(motd),
                                 "success")
                break
            except Exception as e:
                pretty_print('net0', get_string('connecting_error')
                             + Style.NORMAL + f' (connection err: {e})',
                             'error')
                retry_counter += 1
                sleep(10)

        pretty_print('sys' + port_num(com),
                     get_string('mining_start') + Style.NORMAL + Fore.RESET
                     + get_string('mining_algorithm') + str(com) + ')',
                     'success')

        flush_i2c(ser,com)
                
        while True:
            try:
                
                if config["AVR Miner"]["mining_key"] != "None":
                    key = b64.b64decode(config["AVR Miner"]["mining_key"]).decode("utf-8")
                else:
                    key = config["AVR Miner"]["mining_key"]
                    
                debug_output(com + ': Requesting job')
                Client.send(s, 'JOB'
                            + Settings.SEPARATOR
                            + str(username)
                            + Settings.SEPARATOR
                            + 'AVR'
                            + Settings.SEPARATOR
                            + str(key)
                )
                job = Client.recv(s, 128).split(Settings.SEPARATOR)
                debug_output(com + f": Received: {job[0]}")

                try:
                    diff = int(job[2])
                except:
                    pretty_print("sys" + port_num(com),
                                 f" Node message: {job[1]}", "warning")
                    sleep(3)
            except Exception as e:
                pretty_print('net' + port_num(com),
                             get_string('connecting_error')
                             + Style.NORMAL + Fore.RESET
                             + f' (err handling result: {e})', 'error')
                sleep(3)
                break

            retry_counter = 0
            while True:
                if retry_counter > 10:
                    flush_i2c(ser,com)
                    break

                try:
                    debug_output(com + ': Sending job to the board')
                    i2c_data = str(job[0]
                                    + Settings.SEPARATOR
                                    + job[1]
                                    + Settings.SEPARATOR
                                    + job[2]
                                    + Settings.SEPARATOR)
                                    
                    if Settings.CRC8_EN == "y":
                        i2c_data = str(i2c_data + str(crc8(i2c_data.encode())) + '\n')
                        debug_output(com + f': Job+crc8: {i2c_data}')
                    else:
                        i2c_data = str(i2c_data + '\n')
                        debug_output(com + f': Job: {i2c_data}')
                                    
                    with thread_lock():
                        for i in range(0, len(i2c_data)):
                            try:
                                usbi2c_write(ser,int(com, base=16),i2c_data[i])
                                sleep(0.02)
                            except Exception as e:
                                debug_output(com + f': {e}')
                                pass
                    debug_output(com + ': Reading result from the board')
                    i2c_responses = ''
                    i2c_rdata = []
                    result = []
                    result_pool[_com] = ""
                    i2c_start_time = time()
                    sleep_en = True
                    while True:
                        with thread_lock():
                            try:
                                i2c_rdata = usbi2c_read(ser, int(com, base=16))
                            except Exception as e:
                                debug_output(com + f': {e}')
                                pass
                                
                        # put i2c_rdata into their respective worker response
                        i2cs_raddr = hex(int(i2c_rdata[0],base=16)).replace("0x","")
                            
                        if ((i2c_rdata[1].isalnum()) or (',' in i2c_rdata[1])):
                            sleep_en = False
                            result_pool[i2cs_raddr] += i2c_rdata[1].strip()
                        elif ('#' in i2c_rdata[1]):
                            flush_i2c(ser,com)
                                                                                       
                            debug_output(com + f': Retry Job: {job}')
                            raise Exception("I2C data corrupted")
                        elif sleep_en:
                            # feel free to play around this number to find sweet spot for shares/s vs. stability
                            sleep(0.05)
                            
                        result = result_pool[i2cs_raddr].split(',')
                        if ((len(result)==4) and ('\n' in i2c_rdata[1]) and (Settings.CRC8_EN == "y")):
                            debug_output(com + " i2c_responses:" + f'{result_pool[i2cs_raddr]}')
                            break
                        
                        elif ((len(result)==3) and ('\n' in i2c_rdata[1]) and (Settings.CRC8_EN == "n")):
                            debug_output(com + " i2c_responses:" + f'{i2c_responses}')
                            break
                            
                        i2c_end_time = time()
                        if (i2c_end_time - i2c_start_time) > Settings.AVR_TIMEOUT:
                            flush_i2c(ser,com)
                            debug_output(com + ' I2C timed out')
                            raise Exception("I2C timed out")

                    if result[0] and result[1]:
                        _ = int(result[0])
                        if not _:
                            debug_output(com + ' Invalid result')
                            raise Exception("Invalid result")
                        _ = int(result[1])
                        if not result[2].isalnum():
                            debug_output(com + ' Corrupted DUCOID')
                            raise Exception("Corrupted DUCOID")
                        if Settings.CRC8_EN == "y":
                            _resp = result_pool[i2cs_raddr].rpartition(Settings.SEPARATOR)[0]+Settings.SEPARATOR
                            result_crc8 = crc8(_resp.encode())
                            if int(result[3]) != result_crc8:
                                bad_crc8 += 1
                                debug_output(com + f': crc8:: expect:{result_crc8} measured:{result[3]}')
                                raise Exception("crc8 checksum failed")
                        break
                    else:
                        raise Exception("No data received from AVR")
                except Exception as e:
                    debug_output(com + f': Retrying data read: {e}')
                    retry_counter += 1
                    i2c_retry_count += 1
                    #flush_i2c(ser,com,1)
                    continue

            try:
                computetime = round(int(result[1]) / 1000000, 5)
                num_res = int(result[0])
                hashrate_t = round(num_res / computetime, 2)

                hashrate_mean.append(hashrate_t)
                hashrate = mean(hashrate_mean[-5:])
                hashrate_list[threadid] = hashrate
            except Exception as e:
                pretty_print('sys' + port_num(com),
                             get_string('mining_avr_connection_error')
                             + Style.NORMAL + Fore.RESET
                             + ' (no response from the board: '
                             + f'{e}, please check the connection, '
                             + 'port setting or reset the AVR)', 'warning')
                debug_output(com + f': Retry count: {retry_counter}')
                debug_output(com + f': Job: {job}')
                debug_output(com + f': Result: {result}')
                flush_i2c(ser,com)
                break

            try:
                Client.send(s, str(num_res)
                            + Settings.SEPARATOR
                            + str(hashrate_t)
                            + Settings.SEPARATOR
                            + f'USBI2C AVR Miner {Settings.VER}'
                            + Settings.SEPARATOR
                            + str(rig_identifier)
                            + str(port_num(com))
                            + Settings.SEPARATOR
                            + str(result[2]))

                responsetimetart = now()
                feedback = Client.recv(s, 64).split(",")
                responsetimestop = now()

                time_delta = (responsetimestop -
                              responsetimetart).microseconds
                ping_mean.append(round(time_delta / 1000))
                ping = mean(ping_mean[-10:])
                diff = get_prefix("", int(diff), 0)
                debug_output(com + f': retrieved feedback: {" ".join(feedback)}')
            except Exception as e:
                pretty_print('net' + port_num(com),
                             get_string('connecting_error')
                             + Style.NORMAL + Fore.RESET
                             + f' (err handling result: {e})', 'error')
                debug_output(com + f': error parsing response: {e}')
                sleep(5)
                break

            if feedback[0] == 'GOOD':
                shares[0] += 1
                share_print(port_num(com), "accept",
                            shares[0], shares[1], hashrate,
                            computetime, diff, ping)
            elif feedback[0] == 'BLOCK':
                shares[0] += 1
                shares[2] += 1
                share_print(port_num(com), "block",
                            shares[0], shares[1], hashrate,
                            computetime, diff, ping)
            elif feedback[0] == 'BAD':
                shares[1] += 1
                reason = feedback[1] if len(feedback) > 1 else None
                share_print(port_num(com), "reject",
                            shares[0], shares[1], hashrate_t,
                            computetime, diff, ping, reason)
            else:
                shares[1] += 1
                share_print(port_num(com), "reject",
                            shares[0], shares[1], hashrate_t,
                            computetime, diff, ping, feedback)
                debug_output(com + f': Job: {job}')
                debug_output(com + f': Result: {result}')
                flush_i2c(ser,com,5)

            title(get_string('duco_avr_miner') + str(Settings.VER)
                  + f') - {shares[0]}/{(shares[0] + shares[1])}'
                  + get_string('accepted_shares'))

            end_time = time()
            elapsed_time = end_time - start_time
            if threadid == 0 and elapsed_time >= Settings.REPORT_TIME:
                report_shares = shares[0] - last_report_share
                report_bad_crc8 = bad_crc8 - last_bad_crc8
                report_i2c_retry_count = i2c_retry_count - last_i2c_retry_count
                uptime = calculate_uptime(mining_start_time)
                pretty_print("net" + str(threadid),
                                 " POOL_INFO: " + Fore.RESET
                                 + Style.NORMAL + str(motd),
                                 "success")
                periodic_report(start_time, end_time, report_shares,
                                shares[2], hashrate, uptime, 
                                report_bad_crc8, report_i2c_retry_count)
                
                start_time = time()
                last_report_share = shares[0]
                last_bad_crc8 = bad_crc8
                last_i2c_retry_count = i2c_retry_count


def periodic_report(start_time, end_time, shares,
                    blocks, hashrate, uptime, bad_crc8, i2c_retry_count):
    seconds = round(end_time - start_time)
    pretty_print("sys0", " " + get_string("periodic_mining_report")
                 + Fore.RESET + Style.NORMAL
                 + get_string("report_period")
                 + str(seconds) + get_string("report_time")
                 + get_string("report_body1")
                 + str(shares) + get_string("report_body2")
                 + str(round(shares/seconds, 1))
                 + get_string("report_body3")
                 + get_string("report_body7")
                 + str(blocks)
                 + get_string("report_body4")
                 + str(get_prefix("H/s", hashrate, 2))
                 + get_string("report_body5")
                 + str(int(hashrate*seconds))
                 + get_string("report_body6")
                 + get_string("total_mining_time") 
                 + str(uptime)
                 + "\n\t\t‖ CRC8 Error Rate: " + str(round(bad_crc8/seconds, 6)) + " E/s"
                 + "\n\t\t‖ I2C Retry Rate: " + str(round(i2c_retry_count/seconds, 6)) + " R/s", "success")


def calculate_uptime(start_time):
    uptime = time() - start_time
    if uptime >= 7200: # 2 hours, plural
        return str(uptime // 3600) + get_string('uptime_hours')
    elif uptime >= 3600: # 1 hour, not plural
        return str(uptime // 3600) + get_string('uptime_hour')
    elif uptime >= 120: # 2 minutes, plural
        return str(uptime // 60) + get_string('uptime_minutes')
    elif uptime >= 60: # 1 minute, not plural
        return str(uptime // 60) + get_string('uptime_minute')
    else: # less than 1 minute
        return str(round(uptime)) + get_string('uptime_seconds')


if __name__ == '__main__':
    global ser
    init(autoreset=True)
    title(f"{get_string('duco_avr_miner')}{str(Settings.VER)})")
    
    if sys.platform == "win32":
        os.system('') # Enable VT100 Escape Sequence for WINDOWS 10 Ver. 1607
        
    try:
        load_config()
        debug_output('Config file loaded')
    except Exception as e:
        pretty_print(
            'sys0', get_string('load_config_error')
            + Settings.DATA_DIR + get_string('load_config_error_warning')
            + Style.NORMAL + Fore.RESET + f' ({e})', 'error')
        debug_output(f'Error reading configfile: {e}')
        sleep(10)
        _exit(1)

    try:
        greeting()
        debug_output('Greeting displayed')
    except Exception as e:
        debug_output(f'Error displaying greeting message: {e}')
    
    try:
        check_mining_key(config)
    except Exception as e:
        debug_output(f'Error checking miner key: {e}')
        
    if donation_level > 0:
        try:
            Donate.load(donation_level)
            Donate.start(donation_level)
        except Exception as e:
            debug_output(f'Error launching donation thread: {e}')

    try:
        ser = Serial(usbi2c_port, baudrate=int(Settings.BAUDRATE),
                     timeout=float(Settings.AVR_TIMEOUT))
        fastest_pool = Client.fetch_pool()
        threadid = 0
        for port in avrport:
            Thread(target=mine_avr,
                   args=(port, threadid,
                         fastest_pool)).start()
            threadid += 1
            if ((len(avrport) > 1) and (threadid != len(avrport))):
                pretty_print('sys' + str(threadid),
                                f" Started {threadid}/{len(avrport)} worker(s). Next I2C AVR Miner starts in "
                                + str(Settings.DELAY_START)
                                + "s",
                                "success")
                sleep(Settings.DELAY_START)
            else:
                pretty_print('sys' + str(threadid),
                                f" All {threadid}/{len(avrport)} worker(s) started",
                                "success")
    except Exception as e:
        debug_output(f'Error launching AVR thread(s): {e}')

    if discord_presence == "y":
        try:
            init_rich_presence()
        except Exception as e:
            debug_output(f'Error launching Discord RPC thread: {e}')
            

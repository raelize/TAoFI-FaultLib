import sqlite3
import time
import serial
import sys
import chipwhisperer as cw
import datetime
from termcolor import colored
import os

import pyboard

class Database():
    def __init__(self, argv):
        script_name = os.path.basename(sys.argv[0])
        self.dbname = f"{script_name}_%s.sqlite" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if os.path.isdir('databases') == False:
            os.mkdir("databases")
        self.con = sqlite3.connect("databases/" + self.dbname)
        self.cur = self.con.cursor()
        self.argv = argv
        self.cur.execute("CREATE TABLE experiments(id integer, delay integer, length integer, color text, response blob)")
        self.cur.execute("CREATE TABLE metadata (stime_seconds integer, argv blob)")

    def insert(self,experiment_id, delay, length, color, response):
        if experiment_id == 0:
            s_argv = ' '.join(self.argv[1:])
            self.cur.execute("INSERT INTO metadata (stime_seconds,argv) VALUES (?,?)", [int(time.time()), s_argv])
        self.cur.execute("INSERT INTO experiments (id,delay,length,color,response) VALUES (?,?,?,?,?)", [experiment_id, delay, length, color, response])
        self.con.commit()

    def close(self):
        self.con.close()

class Database_New():
    def __init__(self, argv):
        self.argv = argv

        script_name = os.path.basename(self.argv[0])
        self.dbname = f"{script_name}_%s.sqlite" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if os.path.isdir('databases') == False:
            os.mkdir("databases")
        
        self.con = None
        self.cur = None
        self.init()

    def open(self):
        database_path = os.path.join('database/',self.dbname)
        self.con = sqlite3.connect(database_path, timeout=10)
        self.cur = self.con.cursor()

    def close(self):
        if self.cur != None:
            self.cur.close()
        if self.con != None:
            self.con.close()

    def init(self):
        self.open()
        self.cur.execute("CREATE TABLE experiments(id integer, delay integer, length integer, color text, response blob)")
        self.cur.execute("CREATE TABLE metadata (stime_seconds integer, argv blob)")        
        self.close()

    def insert(self,experiment_id, delay, length, color, response):
        self.open()
        if experiment_id == 0:
            s_argv = ' '.join(self.argv[1:])
            self.cur.execute("INSERT INTO metadata (stime_seconds,argv) VALUES (?,?)", [int(time.time()), s_argv])
        self.cur.execute("INSERT INTO experiments (id,delay,length,color,response) VALUES (?,?,?,?,?)", [experiment_id, delay, length, color, response])
        self.con.commit()
        self.close()

class DatabaseRCG():
    def __init__(self, argv):
        script_name = os.path.basename(sys.argv[0])
        self.dbname = f"{script_name}_%s.sqlite" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if os.path.isdir('databases') == False:
            os.mkdir("databases")
        self.con = sqlite3.connect("databases/" + self.dbname)
        self.cur = self.con.cursor()
        self.argv = argv
        self.cur.execute("CREATE TABLE experiments(id integer, clock integer, delay integer, length integer, color text, response blob)")
        self.cur.execute("CREATE TABLE metadata (stime_seconds integer, argv blob)")

    def insert(self,experiment_id, clock, delay, length, color, response):
        if experiment_id == 0:
            s_argv = ' '.join(self.argv[1:])
            self.cur.execute("INSERT INTO metadata (stime_seconds,argv) VALUES (?,?)", [int(time.time()), s_argv])
        self.cur.execute("INSERT INTO experiments (id,clock,delay,length,color,response) VALUES (?,?,?,?,?,?)", [experiment_id, clock,delay, length, color, response])
        self.con.commit()

    def close(self):
        self.con.close()

class Serial():
    def __init__(self, port="/dev/ttyUSB0", baudrate=115200, timeout=0.1):
        self.ser = None
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.init()

    def init(self):
        self.ser = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=self.timeout)

    def write(self, message):
        self.ser.write(message)

    def read(self, length):
        response = self.ser.read(length)
        return response
    
    def reset(self, debug=False):
        print("[+] Resetting target...")
        self.ser.dtr = True
        time.sleep(0.1)
        self.ser.dtr = False
        response = self.ser.read(4096)
        if debug:
            for line in response.splitlines():
                print('\t', line.decode())
        return False

    def empty_read_buffer(self):
        self.ser.reset_input_buffer()

    def empty_read_buffer_v2(self,timeout=0.01):
        self.ser.timeout = timeout
        self.ser.read(8192)
        self.ser.timeout = self.timeout

class Glitcher():
    def __init__(self):
        self.scope = None

    def init(self):
        self.scope = cw.scope()

        self.scope.clock.adc_mul             = 1
        self.scope.clock.clkgen_freq         = 200e6

        self.scope.clock.clkgen_src          = 'system'
        self.scope.adc.basic_mode            = "rising_edge"
        
        self.scope.io.tio1                  = 'serial_rx'
        self.scope.io.tio2                  = 'serial_tx'
        self.scope.io.tio3                  = 'gpio_low'
        self.scope.io.tio4                  = 'high_z'

        self.scope.trigger.triggers          = 'tio4'

        self.scope.io.hs2                    = "disabled"
        self.scope.io.glitch_trig_mcx        = 'glitch'

        self.scope.glitch.enabled            = True
        self.scope.glitch.clk_src            = 'pll'
        
        self.scope.io.glitch_hp              = True
        self.scope.io.glitch_lp              = False

        self.scope.glitch.output             = 'enable_only'
        self.scope.glitch.trigger_src        = 'ext_single'

        self.scope.glitch.num_glitches       = 1

    def arm(self, delay, length):
        self.scope.glitch.ext_offset        = delay // (int(1e9) // int(self.scope.clock.clkgen_freq))
        self.scope.glitch.repeat            = length // (int(1e9) // int(self.scope.clock.clkgen_freq))
        self.scope.arm()

    def capture(self):
        self.scope.capture()

    def disable(self):
        self.scope.glitch.enabled = False

    def enable(self):
        self.scope.glitch.enabled = True

    def classify(self, expected, response):
        if response == expected:
            color = 'G'
        elif b'Falling' in response:
            color = 'R'
        elif b'Fatal exception' in response:
            color = 'M'
        else:
            color = 'Y'
        return color

    def reset(self,reset_time=0.2):
        self.scope.io.tio3 = 'gpio_low'
        time.sleep(reset_time)
        self.scope.io.tio3 = 'gpio_high'

    def reset_and_eat_it_all(self,target,target_timeout=0.3):
        self.scope.io.tio3 = 'gpio_low'
        target.ser.timeout = target_timeout
        target.read(4096)
        target.ser.timeout = target.timeout
        self.scope.io.tio3 = 'gpio_high'

    def reset_wait(self, target, token, reset_time=0.2, debug=False):
        self.scope.io.tio3 = 'gpio_low'
        time.sleep(reset_time)
        self.scope.io.tio3 = 'gpio_high'

        response = target.read(4096)
        for i in range(0,5):
            if token in response:
                break
            response += target.read(4096)

        if debug:
            for line in response.splitlines():
                print('\t', line.decode())

    husky_reset_wait = reset_wait

    def colorize(self, s, color):
        colors = { 
            'G': 'green', 
            'Y': 'yellow', 
            'R': 'red', 
            'M': 'magenta',
        }
        return colored(s, colors[color])
    
    def get_speed(self, start_time, number_of_experiments):
        elapsed_time = int(time.time()) - start_time
        if elapsed_time == 0:
            return 'NA'
        else:
            return number_of_experiments // elapsed_time

    def uart_trigger(self, pattern):
        self.scope.io.hs2 = "clkgen"
        self.scope.trigger.module = 'UART'
        self.scope.trigger.triggers = 'tio1'
        self.scope.UARTTrigger.enabled = True
        self.scope.UARTTrigger.baud = 115200
        self.scope.UARTTrigger.set_pattern_match(0, pattern)
        self.scope.UARTTrigger.trigger_source = 0

class StateMachine():
    def __init__(self, port='/dev/ttyACM1', debug=False):
        self.port   = None
        self.pyb    = None
        self.debug = debug

    def init(self, port, sm_name, debug=False):
        self.port = port
        self.pyb = pyboard.Pyboard(self.port)
        self.pyb.enter_raw_repl()
        self.pyb.exec(f'import {sm_name}')
        self.pyb.exec(f'sm = {sm_name}.RaelizeStateMachine()')

class Helper():
    def __init__(self):
        pass

    def go_into_directory_of_script(self, file):
        abspathfile = os.path.abspath(file)
        directory = os.path.dirname(abspathfile)
        os.chdir(directory)

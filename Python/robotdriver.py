'''
Created on Mar 10, 2016

@author: e0064435
'''

from threading import Thread
import Queue
import telnetlib
import requests
import json
import re
import time
import sys
import tty
import termios
import curses
import random
import tweepy

## Through guest wifi:
robot_ip = "ROBOT_IP"
## Direct connection:
#robot_ip = "192.168.4.1"

class RFID(object):
    '''
    Keep track of RFIDs and let know if goal found
    '''
    
    goal_rfid = "RFID_NUMBER"   # TODO: correct ID
    
    def __init__(self):
        self.found_rfids = []
    
    def RFID_found(self, rfid):
        if (rfid in self.found_rfids):
            return 0
        else:
            self.found_rfids.append(rfid)
            if (rfid == self.goal_rfid):
                return 2
            return 1

class Driver(object):
    '''
    Commands the robot to drive on.
    Keeps track of necessary compensation info etc.
    '''
    ADJUST_DIR = 4  # compensate robot leaning right
    #ADJUST_DIR = 3  # compensate robot leaning left
    ADJUST_POW = 20 # roughly: percentage, 100 means doesn't move forward at all, valid range 0 to 99

    #TURNING_TIME_90_DEG = 10000  # TODO: set here correct time to in ms to turn 90 degrees (may have to be different time for different dirs)
    TURNING_TIME_90_DEG = 350  # TODO: set here correct time to in ms to turn 90 degrees (may have to be different time for different dirs)

    STATE_DRIVE = 1
    STATE_COMPENSATE = 2

    def __init__(self):
        self.state = self.STATE_DRIVE
        if (self.ADJUST_POW < 1 or self.ADJUST_POW >= 100):
            sys.exit("ADJUST_POW invalid value")
    
    # Command robot to drive forward, return time in ms after which moving stops
    def drive_forward(self):
        if (self.state == self.STATE_DRIVE):
            drive_time_ms = 100 - self.ADJUST_POW
            self.command_drive(1, drive_time_ms)
            if (self.ADJUST_POW != 0):
                self.state = self.STATE_COMPENSATE
            return drive_time_ms
        else:
            self.command_drive(self.ADJUST_DIR, self.ADJUST_POW)
            self.state = self.STATE_DRIVE
            return self.ADJUST_POW

    def drive_always(self):
        command = {'text': '{"command":"drivealways",mdata:[1,100,1000]}\n'}  # need \n in the end!!
        try:
            r = requests.post('http://'+robot_ip + '/console/send', params=command, timeout=1.0)
            print("Drive command is: " + r.url.decode('utf-8'))
        except:
            print("Drive command sending caused some kind of exception! Ignoring it.")

    def reverse(self):
        command = {'text': '{"command":"drive",mdata:[2,100,500]}\n'}  # need \n in the end!!
        try:
            r = requests.post('http://'+robot_ip + '/console/send', params=command, timeout=1.0)
            print("Drive command is: " + r.url.decode('utf-8'))
        except:
            print("Drive command sending caused some kind of exception! Ignoring it.")

    def stop(self):
        command = {'text': '{"command":"stop",mdata:[1,100,500]}\n'}  # need \n in the end!!
        try:
            r = requests.post('http://'+robot_ip + '/console/send', params=command, timeout=1.0)
            print("Drive command is: " + r.url.decode('utf-8'))
        except:
            print("Drive command sending caused some kind of exception! Ignoring it.")

    def turn_left(self, degrees):
        self.command_drive(6, int(float(degrees) / 90.0 * self.TURNING_TIME_90_DEG))
    
    def turn_right(self, degrees):
        self.command_drive(5, int(float(degrees) / 90.0 * self.TURNING_TIME_90_DEG))

    # Private methods, not supposed to be called from outside
    def command_drive(self, dir, time):
        command = {'text': '{"command":"drive",mdata:[' + str(dir) + ',100,' + str(time) + ']}\n'}  # need \n in the end!!
        try:
            r = requests.post('http://'+robot_ip + '/console/send', params=command, timeout=1.0)
            print("Drive command is: " + r.url.decode('utf-8'))
        except:
            print("Drive command sending caused some kind of exception! Ignoring it.")
        

def TelnetListener(out_queue, kill_queue):
    print("start telnet to robot..")
    tn = telnetlib.Telnet(robot_ip, 23)
    while (1):
        if (not kill_queue.empty()):
            break;
        try:
            output = tn.read_until("]}", timeout=2.0)
            # Correct the JSON, can remove once JSON generation fixed, but don't have to
            output = re.sub('}:\[', ',"data":[', output)
            print("Sensor data: " + output)
            jdata = json.loads(output)
            out_queue.put(jdata)
        except:
            pass
            #print("JSON exception, ignored")

def getch():
    """getch() -> key character

    Read a single keypress from stdin and return the resulting character. 
     Nothing is echoed to the console. This call will block if a keypress 
    is not already available, but will not wait for Enter to be pressed. 

    If the pressed key was a modifier key, nothing will be detected; if
    it were a special function key, it may return the first character of
    of an escape sequence, leaving additional characters in the buffer.
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def KeyboardListener(kb_queue):
    while (1):
        ch = getch()
        kb_queue.put(ch)
        if (ch == 'q'):
            sys.exit("Quit kb thread")
            
def KeyboardListenerCurses(kb_queue, kill_queue):
    
    stdscr = curses.initscr()
    curses.cbreak()
    stdscr.keypad(1)

    stdscr.addstr(0,10,"Hit 'q' to quit")
    stdscr.refresh()

    key = ''
    while key != ord('q'):
        key = stdscr.getch()
        stdscr.addch(20,25,key)
        stdscr.refresh()
        if key == curses.KEY_UP: 
            stdscr.addstr(2, 20, "Up")
        elif key == curses.KEY_DOWN: 
            stdscr.addstr(3, 20, "Down")
        kb_queue.put(key)

    kill_queue.put("Die, please")
    curses.endwin()
 
 
def command_lights(enable):
    command = {'text': '{"command":"lights",data:[12,' + str(enable) + ',0]}\n'}  # need \n in the end!!
    try:
        r = requests.post('http://'+robot_ip + '/console/send', params=command, timeout=1.0)
    except:
        print("Lights command sending caused some kind of exception! Ignoring it.")
    #print("Lights command is: " + r.url)
    
def tweet(twt):
    CONSUMER_KEY ="CONSUMER_KEY"
    CONSUMER_SECRET = "CONSUMER_SECRET"   
    ACCESS_KEY = "ACCESS_KEY"    
    ACCESS_SECRET = "ACCESS_SECRET"

    auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.set_access_token(ACCESS_KEY, ACCESS_SECRET)

    api = tweepy.API(auth)
    api.update_status(twt+'@kampusareena #codingrally')

#sys.exit("disabled")
command_lights(0)

# Blink some lights - forever
# while(1):
#     command_lights(0)
#     time.sleep(0.5)
#     command_lights(1)
#     time.sleep(0.5)

# Drive backwards and forwards - forever
# while(1):
#     command_drive(1)
#     time.sleep(0.5)
#     command_drive(2)
#     time.sleep(0.5)

# Init
driver = Driver()
kill_queue = Queue.Queue()
sensor_q = Queue.Queue()
# kb_q = Queue.Queue()
kb_q_curses = Queue.Queue()
listener = Thread(target=TelnetListener, args=(sensor_q,kill_queue,))
# kb_listener = Thread(target=KeyboardListener, args=(kb_q,))
kb_listener_curses = Thread(target=KeyboardListenerCurses, args=(kb_q_curses,kill_queue,))
listener.start()
# kb_listener.start()
kb_listener_curses.start()
rfid_tracker = RFID()

STATE_DRIVING = 0
STATE_TURNING = 1
STATE_WAIT_FORWARD = 2

state = STATE_DRIVING

go_forward_time = 0
turn_end_time = 0
debug_time = 0

while (1):
    #next_tmo_ms = driver.drive_forward()
    next_tmo_ms = 10

    cur_time = int(round(time.time() * 1000))
    
    if (state == STATE_TURNING):
        if (turn_end_time < cur_time):
            state = STATE_WAIT_FORWARD
            go_forward_time = cur_time + 1000
    if (state == STATE_WAIT_FORWARD):
        if (go_forward_time < cur_time):
            state = STATE_DRIVING
            driver.drive_always()
    
    if (debug_time < cur_time):
        print("State: " + str(state))
        debug_time = cur_time + 2000
    
    
    # check if we want to die
    if (not kill_queue.empty()):
        break;
    
    # check keyboard output
    try:
        #char_pressed = kb_q.get(True, float(next_tmo_ms) / 1000.0)
        char_pressed = kb_q_curses.get(True, float(next_tmo_ms) / 1000.0)
    except Queue.Empty:
        pass
    else:
#         if (char_pressed == 'w'):
#             driver.drive_always()
#         if (char_pressed == 'a'):
#             driver.turn_left(45)
#         if (char_pressed == 'd'):
#             driver.turn_right(45)
#         if (char_pressed == 's'):
#             driver.reverse()
#         if (char_pressed == 'q'):
#             listener
#             sys.exit("Quit pressed")
        if (char_pressed == curses.KEY_UP):
            driver.drive_always()
        if (char_pressed == curses.KEY_DOWN):
            driver.reverse()
        if (char_pressed == curses.KEY_LEFT):
            driver.turn_left(45)
        if (char_pressed == curses.KEY_RIGHT):
            driver.turn_right(45)
        if (char_pressed == ord(' ')):
            driver.stop()
            
    # check sensor output
    try:
        sensor_info = sensor_q.get(True, float(next_tmo_ms) / 1000.0)
    except Queue.Empty:
        pass
    else:
        if (sensor_info['sensor'] == "distance"):
            print('Distance is ' + str(sensor_info['data'][0]))
            if (sensor_info['data'][0] < 8):
                if (state == STATE_DRIVING or state == STATE_WAIT_FORWARD):
                    if (random.random() < 0.5):
                        driver.turn_left(random.randint(90,165))
                    else:
                        driver.turn_right(random.randint(90,165))
                    turn_end_time = cur_time + 500
                    state = STATE_TURNING
        elif (sensor_info['sensor'] == "acc_gyro"):
            pass
            #print("Acc + Gyro data: " + str(sensor_info['data']))
        elif (sensor_info['sensor'] == "edge"):
            left_blocked = ''
            right_blocked = ''
            if (sensor_info['data'][0]):
                left_blocked = 'left_blocked'
            if (sensor_info['data'][1]):
                right_blocked = 'right_blocked'
                print("Edge sensors: " + left_blocked + " " + right_blocked)
        elif (sensor_info['sensor'] == "rfid"):
            rfid = sensor_info['data'][0]
            status = rfid_tracker.RFID_found(rfid)
            if (status == 0):
                print("RFID " + str(rfid) + " seen already")
            elif (status == 1):
                print("New RFID " + str(rfid) + " added")
            elif (status == 2):
                tweet('RFID reached by Soccers!')
                print("Reached goal! RFID = " + str(rfid))


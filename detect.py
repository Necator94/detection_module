#!/usr/bin/env python


# _______________________________________________________________________________________________
# Author: Ivan Matveev
# E-mail: ivan.matveev@student.emw.hs-anhalt.de
# Project: "Development of the detection module for a SmartLighting system"
# Name: "Detection module"
# Source code available on github: https://github.com/Necator94/sensors.git.
# _______________________________________________________________________________________________

# Program is targeted for human detection module.
# Program includes signal processing and algorithm of human detection.
# sys.argv[0] - time duration;
# sys.argv[1] - standard deviation criteria of human detection;
# sys.argv[2] - mean value criteria of human detection;

import threading
import Queue
import sys
import time
import Adafruit_BBIO.GPIO as GPIO  # The library for GPIO handling
import logging
import numpy as np

logging.basicConfig(level=logging.INFO)  # Setting up logger
logger = logging.getLogger("detection module")


def PIRpolling(gpio_pins, out_signal, e):  # Function for PIR sensor polling

    logger.info(threading.currentThread().getName() + "has started")
    while e.isSet():
        out_signal.put(GPIO.input(gpio_pins['signal_pin']))     # Check GPIO and put to the queue
        time.sleep(0.01)                                         # Set sleeping time
    logger.info(threading.currentThread().getName() + "has finished")

def control(pir_status, exp_parameter, e):  # Function for human detection
    logger.info(threading.currentThread().getName() + "has started")
    starttime = time.time()
    while (time.time() - starttime) < 10:
        print pir_status.get()
    e.clear()
    logger.info(threading.currentThread().getName() + "has finished")


if len(sys.argv) < 3:
    exp_parameter = {'duration': 10, 'st_dev_cr': 20, 'mean_cr': 20}
    logger.info('parameters are set by default')
else:
    exp_parameter = {'duration': int(sys.argv[0]),  # argv[0] -  time duration;
                     'st_dev_cr': int(sys.argv[1]),  # - standard deviation criteria of human detection;
                     'mean_cr': int(sys.argv[2])}  # sys.argv[2] - mean value criteria of human detection;
    logger.info('parameters are set manually')

# Pins configuration
# 0 - out pin     1 - LED pin
xBandPins = {'signal_pin': 'P8_12', 'LED_pin': 'P8_11'}  # GPIO assigned for RW sensor
pir1Pins = {'signal_pin': 'P8_15', 'LED_pin': 'P8_13'}  # GPIO assigned for PIR-1 sensor

# Required configurations for GPIO
GPIO.setup(xBandPins['signal_pin'], GPIO.IN)
GPIO.setup(pir1Pins['signal_pin'], GPIO.IN)

event = threading.Event()
event.set()
pir1_detect_signal_queue = Queue.Queue()
stop = Queue.Queue()

pir1Thread = threading.Thread(name='PIRpolling', target=PIRpolling, args=(pir1Pins, pir1_detect_signal_queue, event))
controlTread = threading.Thread(name='controlTread', target=control, args=(pir1_detect_signal_queue, exp_parameter, event))

pir1Thread.start()
controlTread.start()

pir1Thread.join()
controlTread.join()

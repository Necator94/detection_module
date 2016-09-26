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
import Adafruit_BBIO.GPIO as GPIO                               # The library for GPIO handling
import logging
import numpy as np

logging.basicConfig(level=logging.INFO)                         # Setting up logger
logger = logging.getLogger("experimental_setup")

def PIRpolling(gpio_pins, out_signal, exp_parameter):           # Function for PIR sensor polling
    starttime = time.time()                                     # Get start time
    logger.info('PIR started')
    t_time = 0
    while t_time < exp_parameter['duration']:                   # Perform during defined time
        out_signal.put(GPIO.input(gpio_pins['signal_pin']))     # Check GPIO and put to the queue
        time.sleep(0.1)                                         # Set sleeping time
        t_time = time.time() - starttime                        # Calculate time from program start
    logger.info('PIR finished')

def RWpolling(gpio_pins, out_data, exp_parameter):              # Function for RW sensor polling and signal processing
    periods = []
    temp = []
    for i in range(2): temp.append([])
    rw_parameters  = []
    for i in range(2): rw_parameters.append([])
    t_time = 0
    slide_window = []
    logger.info('RW started')
    startTime = time.time()                                     # Get start time
    while t_time < exp_parameter['duration']:                   # Perform during defined time
        check = GPIO.input(gpio_pins['signal_pin'])             # Check GPIO
        t_time = time.time() - startTime                        # Calculate time from program start
        # Frequency transformation
        temp[0].append(check)
        temp[1].append(t_time)
        if len(temp[0]) > 1 and temp[0][-1] > temp[0][-2]:
            periods.append(temp[1][-2])
            if len(periods) > 1:
                freq = 1 / (periods[-1] - periods[-2])
                slide_window.append(freq)
                if len(slide_window) > 3:
                    slide_window = []
                if len(slide_window) == 3:
                    rw_parameters[0] = np.std(slide_window)     # Standard deviation value calculation
                    rw_parameters[1] = np.mean(slide_window)    # Mean value calculation
                    out_data.put(rw_parameters)                 # Put values to the queue
                del periods[0]
            del temp[0][:-1]
            del temp[1][:-1]
        time.sleep(0.001)
    logger.info('RW finished')

def control(pir_status, rw_parameters, exp_parameter):          # Function for human detection
    while True:
        std, mean = rw_parameters.get()
        if std < (exp_parameter['st_dev_cr'] + 10) and mean > (exp_parameter['mean_cr'] - 10): flag_rw = True
        else: flag_rw = False

        if pir_status.get() and flag_rw:                        # If both sensors detected movement
            logger.info('Both sensors triggered')
            # Action to be performed in case of human detection
            #{...........}
            #{...........}
        if pir_status.get() and not flag_rw:
            logger.info('PIR sensor triggered')
        if flag_rw and not pir_status.get():
            logger.info('RW sensor triggered')

# if arguments were not received, set some by default
if len(sys.argv) < 3:
    exp_parameter = {'duration': 10, 'st_dev_cr': 20, 'mean_cr': 20}
    logger.info('parameters are set by default')
else:
    exp_parameter = {'duration': int(sys.argv[0]),              # argv[0] -  time duration;
                     'st_dev_cr': int(sys.argv[1]),             #- standard deviation criteria of human detection;
                     'mean_cr': int(sys.argv[2])}               # sys.argv[2] - mean value criteria of human detection;
    logger.info('parameters are set manually')

# Pins configuration
# 0 - out pin     1 - LED pin
xBandPins = {'signal_pin': 'P8_12', 'LED_pin': 'P8_11'}         # GPIO assigned for RW sensor
pir1Pins = {'signal_pin': 'P8_15', 'LED_pin': 'P8_13'}          # GPIO assigned for PIR-1 sensor

logger.info('Program start')

# Required configurations for GPIO
GPIO.setup(xBandPins['signal_pin'], GPIO.IN)
GPIO.setup(pir1Pins['signal_pin'], GPIO.IN)

# Create objects for resource sharing
xBand_raw_data_queue = Queue.Queue()
pir1_detect_signal_queue = Queue.Queue()

# Define threads targets and input arguments
xBandThread = threading.Thread(target=RWpolling, args=(xBandPins, xBand_raw_data_queue, exp_parameter))
pir1Thread = threading.Thread(target=PIRpolling, args=(pir1Pins, pir1_detect_signal_queue, exp_parameter))

# Start threads for RW, PIR-2 and PIR-2 sensors
xBandThread.start()
pir1Thread.start()

# Wait for threads finishing
xBandThread.join()
pir1Thread.join()
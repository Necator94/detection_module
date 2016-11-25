#!/usr/bin/env python

import Queue
import numpy as np
import threading
import time
import logging.config

import Adafruit_BBIO.GPIO as GPIO       # The library for GPIO handling
from statistic_lib import Statistic

logger = logging.getLogger(__name__)


class Module(threading.Thread):
    def __init__(self, st_event, pir=False, rw=False, control=False):
        threading.Thread.__init__(self, name="Main thread")
        self.pir_flag = pir
        self.rw_flag = rw
        self.st_flag = False
        self.control_flag = control
        if self.control_flag:
            self.pir_flag = True
            self.rw_flag = True

        self.stop_ev = st_event

        self.pir_polling_qs = 0
        self.rw_polling_qs = 0
        self.rw_processing_qs = 0
        self.control_qs = 0

        if self.pir_flag:
            self.pir_gpio = {'signal_pin': 'P8_15', 'LED_pin': 'P8_13'}
            self.pir_polling_qs += 1
            self.pir_tm = 0.1
            self.pir_sample = 0

        if self.rw_flag:
            self.rw_gpio = {'signal_pin': 'P8_12', 'LED_pin': 'P8_18'}
            self.rw_polling_qs += 1
            self.rw_processing_qs += 1
            self.rw_tm = 0.01
            self.rw_sample = 0

        self.st_args = []

    def parser(self):
        self.pir_polling_qs = [Queue.Queue() for x in range(self.pir_polling_qs)]
        self.rw_polling_qs = [Queue.Queue() for x in range(self.rw_polling_qs)]
        self.rw_processing_qs = [Queue.Queue() for x in range(self.rw_processing_qs)]
        if len(self.pir_polling_qs) == 2:
            self.st_args.append(["PIR", self.pir_polling_qs[1], "Time|Value"])
        if len(self.rw_polling_qs) == 2:
            self.st_args.append(["RW", self.rw_polling_qs[1], "Time|Value"])
        if len(self.rw_processing_qs) == 2:
            self.st_args.append(["RW_proc", self.rw_processing_qs[1], "Time|Value"])

    def get_status_pir(self):
        return self.pir_sample

    def get_status_rw(self):
        return self.rw_sample

    def set_statistic_lvl(self, full=False, pir_pol=False, rw_pol=False, rw_proc=False, control=False):
        if full:
            pir_pol = True
            rw_pol = True
            rw_proc = True
            control = True
        if pir_pol and self.pir_flag:
            self.st_flag = True
            self.pir_polling_qs += 1
        if pir_pol and not self.pir_flag:
            logger.warning("pir sensor is not defined, polling data collection is not possible")
        if rw_pol and self.rw_flag:
            self.st_flag = True
            self.rw_polling_qs +=1
        if rw_pol and not self.rw_flag:
            logger.warning("rw sensor is not defined, polling data collection is not possible")
        if rw_proc and self.rw_flag:
            self.st_flag = True
            self.rw_processing_qs += 1
        if rw_proc and not self.rw_flag:
            logger.warning("rw sensor is not defined, processing data collection is not possible")
        if control and self.rw_flag and self.pir_flag:
            self.st_flag = True
            self.control_qs = Queue.Queue()
        if control and (not self.rw_flag or not self.pir_flag):
            logger.warning("rw or pir sensor are not defined, processing data collection is not possible")

    def polling(self, gpio, qs):
        logger.info("Started")
        start_time = time.time()
        while self.stop_ev.isSet():
            sample = [time.time() - start_time, GPIO.input(gpio['signal_pin'])]
            for i in range(len(qs)):
                qs[i].put(sample)
            time.sleep(self.pir_tm)
        logger.info("Finished")

    def rw_processing(self):
        logger.info("Started")
        f_buffer_time = []
        f_buffer_data = []
        s_buffer = []
        result_buffer_fr = []
        result_buffer_time = []
        while self.stop_ev.isSet():
            try:
                check = self.rw_polling_qs[0].get(timeout=3)
                f_buffer_time.append(check[0])
                f_buffer_data.append(check[1])

                if len(f_buffer_data) == 300:
                    for i in range(len(f_buffer_data) - 1):
                        if f_buffer_data[i + 1] > f_buffer_data[i]:
                            s_buffer.append(f_buffer_time[i + 1])
                    if len(s_buffer) > 1:
                        for k in range(len(s_buffer) - 1):
                            freq = 1 / (s_buffer[k + 1] - s_buffer[k])
                            result_buffer_fr.append(freq)
                            result_buffer_time.append(s_buffer[k + 1])
                        mean_vol = np.mean(result_buffer_fr)            # make a sample of mean value and do not put 2 times
                        for x in range(len(self.rw_processing_qs)):
                            self.rw_processing_qs[x].put(mean_vol)
                        result_buffer_fr = []
                    else:
                        for x in range(len(self.rw_processing_qs)):
                            self.rw_processing_qs[x].put(0)

                    s_buffer = []
                    f_buffer_time = []
                    f_buffer_data = []
            except Queue.Empty:
                logger.info("RW queue timeout")
        logger.info("Finished")

    def control(self):
        logger.info("Started")
        while self.stop_ev.isSet():

            if self.pir_flag:
                try:
                    self.pir_sample = self.pir_polling_qs[0].get(timeout=3)
                except Queue.Empty:
                    logger.info("PIR queue timeout")

            if self.rw_flag:
                try:
                    self.rw_sample = self.rw_processing_qs[0].get(timeout=3)
                  #  logger.info("RW mean_val = " + str(self.status_rw))
                except Queue.Empty:
                    logger.info("RW queue timeout")

            if self.control_flag:
                if self.rw_sample > 0 and self.pir_sample > 0:
                     GPIO.output('P8_18', GPIO.HIGH)
                     if self.st_flag:
                         self.dm_result_statistic_q.put([time.time(), 1])
                else:
                     GPIO.output('P8_18', GPIO.LOW)
        logger.info("Finished")

    def set_fr(self, pir_fr=10, rw_fr=100):
        self.pir_tm = 1/pir_fr
        self.rw_tm = 1/rw_fr

    def run(self):
        self.parser()

        if len(self.pir_polling_qs) > 0:
            GPIO.setup(self.pir_gpio['signal_pin'], GPIO.IN)
            pir_polling = threading.Thread(name='Polling PIR', target=self.polling,
                                           args=(self.pir_gpio, self.pir_polling_qs))
            pir_polling.start()

        if len(self.rw_polling_qs) > 0:
            GPIO.setup(self.rw_gpio['signal_pin'], GPIO.IN)
            rw_polling = threading.Thread(name='Polling RW', target=self.polling,
                                          args=(self.rw_gpio, self.rw_polling_qs))
            rw_processing = threading.Thread(name='Rw processing ', target=self.rw_processing)
            rw_polling.start()
            rw_processing.start()

        if len(self.pir_polling_qs) > 0 or len(self.rw_polling_qs) > 0:
            control_thread = threading.Thread(name='Control thread', target=self.control)
            control_thread.start()

        if self.control_flag:
            GPIO.setup('P8_18', GPIO.OUT)
            self.st_args.append(["DM", self.dm_result_statistic_q, "Time|Value"])

        if self.st_flag:
            st_module = Statistic(self.stop_ev, self.st_args)
            st_module.start()

        if not self.pir_flag and not self.rw_flag:
            self.stop_ev.clear()
            logger.error("No sensors are specified. Exit")
            return 1

        while self.stop_ev.is_set():
            time.sleep(1)
        logger.info("Stop event received")

        if self.pir_flag:
            pir_polling.join()
        if self.rw_flag:
            rw_polling.join()
            rw_processing.join()
        if self.rw_flag or self.pir_flag:
            control_thread.join()
        if self.st_flag:
            st_module.join()
        logger.info("Finished")

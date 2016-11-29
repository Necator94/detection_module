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
    def __init__(self, st_event, pir=False, rw=False, control=False, full=False):
        threading.Thread.__init__(self, name="Main thread")
        self.start_time = time.time()

        self.pir_flag = pir
        self.rw_flag = rw
        self.control_flag = control

        if full:
            self.pir_flag = True
            self.rw_flag = True
            self.control_flag = True

        self.st_flag = False
        self.st_args = {}
        self.control_qs = {}

        if self.control_flag:
            self.control_stat = {}

        if self.pir_flag:
            self.pir_gpio = {'signal_pin': 'P8_15', 'LED_pin': 'P8_13'}
            self.pir_polling_qs = {"polling": Queue.Queue()}
            self.control_qs.update({"PIR": self.pir_polling_qs["polling"]})
            self.pir_tm = 0.1
            self.pir_sample = 0

        if self.rw_flag:
            self.rw_gpio = {'signal_pin': 'P8_12', 'LED_pin': 'P8_18'}
            self.rw_polling_qs = {"polling": Queue.Queue()}
            self.rw_processing_qs = {"processing": Queue.Queue()}
            self.control_qs.update({"RW": self.rw_processing_qs["processing"]})
            self.rw_tm = 0.001
            self.rw_sample = 0

        self.stop_ev = st_event

    def get_status_pir(self):
        return self.pir_sample

    def get_status_rw(self):
        return self.rw_sample

    def set_stat_param(self, name, q, args, clms):
        self.st_flag = True
        q.update({"statistic": Queue.Queue()})
        args.update({name: {"col_name": clms, "queue": q["statistic"]}})

    def set_statistic_lvl(self, full=False, pir_pol=False, rw_pol=False, rw_proc=False, control=False):
        def except_log(name):
            logger.warning("%s is not defined in the module, data collection is not possible" % name)

        if full:
            pir_pol = True
            rw_pol = True
            rw_proc = True
            control = True

        if pir_pol and self.pir_flag:
            self.set_stat_param("PIR_polling", self.pir_polling_qs, self.st_args, ["Time", "Value"] )
        if pir_pol and not self.pir_flag:
            except_log("PIR sensor")

        if rw_pol and self.rw_flag:
            self.set_stat_param("RW_polling", self.rw_polling_qs, self.st_args, ["Time", "Value"] )
        if rw_pol and not self.rw_flag:
            except_log("RW sensor")

        if rw_proc and self.rw_flag:
            self.set_stat_param("RW_processing", self.rw_processing_qs, self.st_args, ["Time", "Value"] )
        if rw_proc and not self.rw_flag:
            except_log("RW processing")

        if control and self.control_flag:
            self.set_stat_param("Control", self.control_stat, self.st_args, ["Time", "Value"])
        if control and (not self.rw_flag or not self.pir_flag):
            except_log("Control")

    def polling(self, gpio, qs, tm):
        logger.info("Started")
        while self.stop_ev.isSet():
            sample = [time.time() - self.start_time, GPIO.input(gpio['signal_pin'])]
            for key in qs:
                qs[key].put(sample)
            time.sleep(tm)
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
                check = self.rw_polling_qs["polling"].get(timeout=3)

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
                        mean_vol = np.mean(result_buffer_fr)
                        result_buffer_fr = []
                    else:
                        mean_vol = 0

                    for x in self.rw_processing_qs:
                        self.rw_processing_qs[x].put([time.time() - self.start_time, mean_vol])

                    s_buffer = []
                    f_buffer_time = []
                    f_buffer_data = []
            except Queue.Empty:
                logger.info("RW queue timeout")
        logger.info("Finished")

    def control(self, in_qs):
        logger.info("Started")
        qs = dict.fromkeys(in_qs)
        light = False
        while self.stop_ev.isSet():
            for name in qs:
                try:
                    qs[name] = (in_qs[name].get(timeout=3))
                except Queue.Empty:
                    logger.info("%s queue timeout" % name)

            if len(qs) == 2:
                if qs["PIR"][1] > 0 and qs["RW"][1] > 0:
                    light = True
                else:
                    light = False

            if len(qs) == 1:
                for name in qs:
                    if name == "PIR":
                        if qs["PIR"][1] > 0:
                            light = True
                        else:
                            light = False

                    if name == "RW":
                        if qs["RW"][1] > 0:
                            light = True
                        else:
                            self.rw_sample = 0
                            light = False

            if self.st_flag:
                if light: status = 1
                else: status = 0
                self.control_stat["statistic"].put([time.time() - self.start_time, status])

            if light: GPIO.output('P8_18', GPIO.HIGH)
            else: GPIO.output('P8_18', GPIO.LOW)

        logger.info("Finished")

    def set_fr(self, pir_fr=10, rw_fr=100):
        self.pir_tm = 1 / pir_fr
        self.rw_tm = 1 / rw_fr

    def run(self):

        if not self.pir_flag and not self.rw_flag:
            self.stop_ev.clear()
            logger.error("No sensors are specified. Exit")
            return 1

        if self.pir_flag:
            GPIO.setup(self.pir_gpio['signal_pin'], GPIO.IN)
            pir_polling = threading.Thread(name='Polling PIR', target=self.polling,
                                           args=(self.pir_gpio, self.pir_polling_qs, self.pir_tm))
            pir_polling.start()

        if self.rw_flag:
            GPIO.setup(self.rw_gpio['signal_pin'], GPIO.IN)
            rw_polling = threading.Thread(name='Polling RW', target=self.polling,
                                          args=(self.rw_gpio, self.rw_polling_qs, self.rw_tm))
            rw_processing = threading.Thread(name='Rw processing ', target=self.rw_processing)
            rw_polling.start()
            rw_processing.start()

        if self.control_flag:
            GPIO.setup('P8_18', GPIO.OUT)
            control_thread = threading.Thread(name='Control thread', target=self.control, args=(self.control_qs,))
            control_thread.start()

        if self.st_flag:
            st_module = Statistic(self.stop_ev, self.st_args)
            st_module.start()


        while self.stop_ev.is_set():
            time.sleep(1)
        logger.info("Stop event received")

        if self.pir_flag:
            pir_polling.join()
        if self.rw_flag:
            rw_polling.join()
            rw_processing.join()
        if self.control_flag:
            control_thread.join()
        if self.st_flag:
            st_module.join()
        logger.info("Finished")

import Queue
import logging
import numpy as np
import threading
import time

import Adafruit_BBIO.GPIO as GPIO       # The library for GPIO handling
from statistic_log import Statistic

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

formatter = logging.Formatter('%(relativeCreated)6d - %(name)s - %(threadName)s - %(levelname)s - %(message)s')

ch.setFormatter(formatter)
logger.addHandler(ch)

pir_gpio = {'signal_pin': 'P8_15', 'LED_pin': 'P8_13'}
rw_gpio = {'signal_pin': 'P8_12', 'LED_pin': 'P8_18'}


class Module:
    def __init__(self, tm_pir=0.5, tm_rw=0.1, duration=20, pir=False, rw=False):
        self.gen_time = time.time()

        self.pir_flag = pir
        if self.pir_flag:
            self.pir_queue = Queue.Queue()
            self.pir_out_queue = Queue.Queue()
            self.tm_pir = tm_pir
            self.pir_gpio = pir_gpio
            GPIO.setup(self.pir_gpio['signal_pin'], GPIO.IN)
            self.pir_thread = threading.Thread(name='Polling PIR', target=self.polling,
                                               args=(self.pir_queue, self.pir_gpio, self.tm_pir))
        self.rw_flag = rw
        if self.rw_flag:
            self.rw_queue = Queue.Queue()
            self.rw_queue_res = Queue.Queue()
            self.rw_gpio = rw_gpio
            self.tm_rw = tm_rw
            GPIO.setup(self.rw_gpio['signal_pin'], GPIO.IN)
            self.rw_thread = threading.Thread(name='Polling RW', target=self.polling,
                                              args=(self.rw_queue, self.rw_gpio, self.tm_rw))
            self.rw_proc_thread = threading.Thread(name='Rw processing ', target=self.rw_processing)

        self.duration = duration
        self.stop_ev = threading.Event()
        self.stop_ev.set()

        if self.pir_flag or self.rw_flag:
            self.in_ar = [["PIR", self.pir_out_queue, "Time|Value"]]
            self.st_module = Statistic(self.in_ar, self.stop_ev, commit_interval=10)
            GPIO.setup('P8_18', GPIO.OUT)
            self.control_thread = threading.Thread(name='Control thread', target=self.control)

    def polling(self, queue, gpio, tm):
        logger.info("Started")
        start_time = time.time()
        while self.stop_ev.isSet():
            queue.put([time.time() - start_time, GPIO.input(gpio['signal_pin'])])
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
                check = self.rw_queue.get(timeout=3)
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
                        self.rw_queue_res.put(mean_vol)
                        result_buffer_fr = []
                    else: self.rw_queue_res.put(0)
                    s_buffer = []
                    f_buffer_time = []
                    f_buffer_data = []

            except Queue.Empty:
                logger.info("RW queue timeout")
        logger.info("Finished")

    def control(self):
        logger.info("Started")
        while self.stop_ev.isSet():
            try:
                status_pir = self.pir_queue.get(timeout=3)
                self.pir_out_queue.put(status_pir)
#                logger.info(threading.currentThread().getName() + "PIR status = " + str(status_pir))
            except Queue.Empty:
                logger.info("PIR queue timeout")
        '''
            try:
                status_rw = self.rw_queue_res.get(timeout=0.5)
                logger.info(threading.currentThread().getName() + "RW mean_val = " + str(status_rw))
            except Queue.Empty:
                logger.info(threading.currentThread().getName() + "RW queue timeout")

            if status_rw > 0 and status_pir > 0:
                GPIO.output('P8_18', GPIO.HIGH)
            else:
                GPIO.output('P8_18', GPIO.LOW)
        '''
        logger.info("Finished")

    def run(self):
        if self.rw_flag or self.pir_flag:
            self.st_module.start()
            self.control_thread.start()

        if self.rw_flag:
            self.rw_thread.start()
            self.rw_proc_thread.start()

        if self.pir_flag:
            self.pir_thread.start()

        try:
            while (time.time() - self.gen_time) < self.duration and self.stop_ev.is_set():
                time.sleep(1)
            logger.info("Time is over")
        except KeyboardInterrupt:
            logger.info("Keyboard Interrupt, threads are going to stop")

        self.stop_ev.clear()
        logger.info("Stop event set to %s" % (self.stop_ev.isSet()))
        logger.info("Execution time %s", time.time() - self.gen_time)

        if self.rw_flag:
            self.pir_thread.join()
        if self.rw_flag:
            self.rw_thread.join()
            self.rw_proc_thread.join()
        if self.rw_flag or self.pir_flag:
            self.control_thread.join()
            self.st_module.join()
        logger.info("All threads have finished")


if __name__ == '__main__':
    mod = Module(duration=100, pir=True, tm_pir=0.1)
 #   s = Statistic()
    mod.run()

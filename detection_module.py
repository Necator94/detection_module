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


class Module(threading.Thread):
    def __init__(self, st_event, pir=False, rw=False, dm=False):
        threading.Thread.__init__(self, name="Main thread")
        self.pir_flag = pir
        self.rw_flag = rw
        if dm:
            self.pir_flag = True
            self.rw_flag = True
        self.stop_ev = st_event

        if self.pir_flag:
            self.pir_gpio = {'signal_pin': 'P8_15', 'LED_pin': 'P8_13'}
            self.pir_control_q = Queue.Queue()
            self.pir_statistic_q = Queue.Queue()
            self.pir_tm = 0.1
            self.pir_sample = 0
            GPIO.setup(self.pir_gpio['signal_pin'], GPIO.IN)

        if self.rw_flag:
            self.rw_gpio = {'signal_pin': 'P8_12', 'LED_pin': 'P8_18'}
            self.rw_processing_q = Queue.Queue()
            self.rw_statistic_q = Queue.Queue()
            self.rw_result_q = Queue.Queue()
            self.rw_tm = 0.01
            self.status_rw = 0
            GPIO.setup(self.rw_gpio['signal_pin'], GPIO.IN)

        if self.pir_flag or self.rw_flag:
            self.st_args = []
            GPIO.setup('P8_18', GPIO.OUT)

    def pir_polling(self):
        logger.info("Started")
        start_time = time.time()
        while self.stop_ev.isSet():
            self.pir_sample = [time.time() - start_time, GPIO.input(self.pir_gpio['signal_pin'])]
            self.pir_control_q.put(self.pir_sample)
            self.pir_statistic_q.put(self.pir_sample)
            time.sleep(self.pir_tm)
        logger.info("Finished")

    def rw_polling(self):
        logger.info("Started")
        start_time = time.time()
        while self.stop_ev.isSet():
            rw_sample = [time.time() - start_time, GPIO.input(self.rw_gpio['signal_pin'])]
            self.rw_processing_q.put(rw_sample)
            self.rw_statistic_q.put(rw_sample)
            time.sleep(self.rw_tm)
        logger.info("Finished")

    def get_status_pir(self):
        return self.pir_sample

    def rw_processing(self):
        logger.info("Started")
        f_buffer_time = []
        f_buffer_data = []
        s_buffer = []
        result_buffer_fr = []
        result_buffer_time = []
        while self.stop_ev.isSet():
            try:
                check = self.rw_processing_q.get(timeout=3)
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
                        self.rw_result_q.put(mean_vol)
                        result_buffer_fr = []
                    else:
                        self.rw_result_q.put(0)
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
                self.pir_sample = self.pir_control_q.get(timeout=3)
            except Queue.Empty:
                logger.info("PIR queue timeout")
            try:
                self.status_rw = self.rw_result_q.get(timeout=3)
                logger.info("RW mean_val = " + str(self.status_rw))
            except Queue.Empty:
                logger.info("RW queue timeout")

            # if self.status_rw > 0 and self.pir_sample > 0:
            #     GPIO.output('P8_18', GPIO.HIGH)
            # else:
            #     GPIO.output('P8_18', GPIO.LOW)
        logger.info("Finished")

    def set_fr(self, pir_fr=10, rw_fr=100):
        self.pir_tm = 1/pir_fr
        self.rw_tm = 1/rw_fr

    def run(self):

        if self.pir_flag:
            self.st_args.append(["PIR", self.pir_statistic_q, "Time|Value"])
            pir_polling = threading.Thread(name='Polling PIR', target=self.pir_polling)
            pir_polling.start()

        if self.rw_flag:
            self.st_args.append(["RW", self.rw_statistic_q, "Time|Value"])
            rw_polling = threading.Thread(name='Polling RW', target=self.rw_polling)
            rw_processing = threading.Thread(name='Rw processing ', target=self.rw_processing)
            rw_polling.start()
            rw_processing.start()

        if self.rw_flag or self.pir_flag:
            st_module = Statistic(self.stop_ev, self.st_args, commit_interval=10)
            st_module.start()
            control_thread = threading.Thread(name='Control thread', target=self.control)
            control_thread.start()

        else:
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
            st_module.join()
            control_thread.join()
        logger.info("Finished")

if __name__ == '__main__':

    stop_ev = threading.Event()
    stop_ev.set()

    module = Module(stop_ev)

    st_time = time.time()
    module.start()

    try:
        while time.time() - st_time < 20:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard Interrupt, threads are going to stop")
    stop_ev.clear()


    module.join()


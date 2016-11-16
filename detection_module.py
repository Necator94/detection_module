import Queue
import logging
import numpy as np
import sqlite3 as lite
import threading
import time

import Adafruit_BBIO.GPIO as GPIO  # The library for GPIO handling

logging.basicConfig(level=logging.INFO)  # Setting up logger
logger = logging.getLogger("detection module")


class Sensor:
    def __init__(self, tm_pir=0.5, tm_rw=0, dr=20):
        self.tm_pir = tm_pir
        self.tm_rw = tm_rw
        self.duration = dr
        self.event = threading.Event()
        self.event.set()
        self.pir_gpio = {'signal_pin': 'P8_15', 'LED_pin': 'P8_13'}
        self.rw_gpio = {'signal_pin': 'P8_12', 'LED_pin': 'P8_18'}

        self.pir_queue = Queue.Queue()
        self.rw_queue = Queue.Queue()
        self.rw_queue_res = Queue.Queue()
        self.start_time = time.time()
        self.event = threading.Event()


    def polling(self, queue, gpio, tm):  # Function for PIR sensor polling
        logger.info(threading.currentThread().getName() + "has started")
        while self.event.isSet():
            sample = []
            sample.append(time.time())
            sample.append(GPIO.input(gpio['signal_pin']))
            queue.put(sample)
#            queue.put(str(GPIO.input(gpio['signal_pin'])) + threading.currentThread().getName())  # Check GPIO and put to the queue
#            queue.put(str(time.time()) + threading.currentThread().getName())
            time.sleep(tm)  # Set sleeping time
        logger.info(threading.currentThread().getName() + "has finished")

    def rw_processing(self):
        logger.info(threading.currentThread().getName() + "has started")
        f_buffer_time = []
        f_buffer_data = []
        s_buffer = []

        result_buffer_fr = []
        result_buffer_time = []

        while self.event.isSet():
            try:
                check = self.rw_queue.get(timeout=0.05)
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

            except Queue.Empty: logger.info(threading.currentThread().getName() + "RW queue timeout")



        logger.info(threading.currentThread().getName() + "has finished")

class Module(Sensor):
    def control(self):  # Function for human detection
        logger.info(threading.currentThread().getName() + "has started")
        while self.event.isSet():

            try:
                status_pir = self.pir_queue.get(timeout=1)
                logger.info(threading.currentThread().getName() + "PIR status = " + str(status_pir))
            except Queue.Empty: logger.info(threading.currentThread().getName() + "PIR queue timeout")

            try:
                status_rw = self.rw_queue_res.get(timeout=0.5)
                logger.info(threading.currentThread().getName() + "RW mean_val = " + str(status_rw))
            except Queue.Empty:
                logger.info(threading.currentThread().getName() + "RW queue timeout")

            if status_rw > 0 and status_pir > 0:
                GPIO.output('P8_18', GPIO.HIGH)
            else:
                GPIO.output('P8_18', GPIO.LOW)

        logger.info(threading.currentThread().getName() + "has finished")

    def run(self):
        GPIO.setup(self.rw_gpio['signal_pin'], GPIO.IN)
        GPIO.setup(self.pir_gpio['signal_pin'], GPIO.IN)
        GPIO.setup('P8_18', GPIO.OUT)
        #       GPIO.setup(self.pir1Pins['signal_pin'], GPIO.IN)
        self.event.set()
        controlTread = threading.Thread(name=' controlTread ', target=self.control)
#        pirThread = threading.Thread(name=' Polling PIR ', target=self.polling, args=(self.pir_queue, self.pir_gpio, self.tm_pir))
        rwThread = threading.Thread(name=' Polling RW ', target=self.polling, args=(self.rw_queue, self.rw_gpio, self.tm_rw))
        rw_proc = threading.Thread(name=' Rw processing ', target=self.rw_processing)

        controlTread.start()

        rwThread.start()
        rw_proc.start()
#        pirThread.start()

        self.starttime = time.time()

        try:
            while (time.time() - self.starttime) < self.duration and self.event.is_set(): pass
            self.event.clear()
#            pirThread.join()
            rwThread.join()
            controlTread.join()
            rw_proc.join()
            logger.info("Time is over, all threads have finished")
        except KeyboardInterrupt:
            self.event.clear()
#            pirThread.join()
            rwThread.join()
            controlTread.join()
            rw_proc.join()
            logger.info("Keyboard Interrupt, all threads have finished")

    def statistic(self):
        conn = lite.connect('sen_info.db')
        cur = conn.cursor()
        cur.execute("CREATE TABLE PIR(Time REAL, Value INT)")

if __name__ == '__main__':
    mod = Module(dr=100)
    mod.run()

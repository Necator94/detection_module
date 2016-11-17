#   statistic_log.py
#
#   The class provides data collection functionality for multi threading usage. All data stored in <filename>.db file
#   (by default - sen_info_0.db)
#   A frequency of sensors' polling does not influence on the class performance.
#
#   Input arguments:
#   args - array of names and queues for writing
#   stop - event for stop of the class
#   Optional: base_name = 'sen_info_0'
#
#   Important:
#   incoming array should be formatted as multidimensional array even if array has

#   Author: Ivan Matveev
#   E-mail: i.matveev@emw.hs-anhalt.de
#   Date: 17.11.2016


import threading
import Queue
import sqlite3 as lite
import os
import logging

logging.basicConfig(level=logging.INFO)  # Setting up logger
logger = logging.getLogger("detection module")

class statistic(threading.Thread):
    def __init__(self, args, stop, base_name='sen_info_0'):
        threading.Thread.__init__(self)
        self.names = args[0]
        self.in_queues = args[1]
        self.stop_event = stop
        self.base_name = base_name
        self.out_queues = [Queue.Queue() for i in range(len(self.in_queues))]
        self.internal_stop = threading.Event()
        self.internal_stop.set()

    def check_on_args(self):
        if not isinstance(self.names[0], str):
            self.names, self.in_queues = self.in_queues, self.names

    def writer(self):
        logger.info(threading.currentThread().getName() + "started")
        conn = lite.connect(self.base_name)
        cur = conn.cursor()
        for i in range(len(self.out_queues)):
            cur.execute("CREATE TABLE %s (Time INT PRIMARY KEY, Value REAL)" % (self.names[i]))
            logger.debug(threading.currentThread().getName() + self.names[i] + "table created")
        while self.internal_stop.isSet():
            for i in range(len(self.out_queues)):
                try:
                    packet = self.out_queues[i].get(timeout=0.4)
                    for s in range(len(packet[0])):
                        cur.execute("INSERT INTO %s VALUES(?, ?)" % (self.names[i]), (packet[0][s], packet[1][s]))
                except Queue.Empty:
                    logger.warning(threading.currentThread().getName() + self.names[i] + "queue timeout")
            qs_counter = 0
            for k in range(len(self.out_queues)):
                qs_counter += self.out_queues[k].qsize()
            if not self.internal_stop.isSet() and qs_counter == 0:
                break
        conn.commit()
        conn.close()
        logger.info(threading.currentThread().getName() + "finished")

    def wraper(self, in_q):
        try:
            sample = in_q.get(timeout=0.1)
            temp = [[sample[x]] for x in range(len(sample))]
        except Queue.Empty:
            logger.debug("wraper in_q queue timeout")
            return temp, False
        while len(temp[0]) < 11:
            try:
                sample = in_q.get(timeout=0.1)
                for x in range(len(temp)):
                    temp[x].append(sample[x])
            except Queue.Empty:
                logger.debug("wraper in_q queue timeout")
                return temp, False
        return temp, True

    def buffering(self, in_q, out_q):
        logger.info(threading.currentThread().getName() + "started")
        while True:
            packet, flag = self.wraper(in_q)
            if not flag:
                logger.warning(threading.currentThread().getName() + "packet wraper timeout")
            out_q.put(packet)
            if not self.stop_event.isSet() and in_q.qsize() == 0:
                break
        logger.debug(threading.currentThread().getName() + "rest items in queue " + str(in_q.qsize()))
        logger.info(threading.currentThread().getName() + "finished")

    def check_on_file(self):
        logger.debug("check file on existence")
        nm_b = 0
        while nm_b < 1000:
            self.base_name = 'sen_info_%s.db' % nm_b
            if os.path.exists(self.base_name):
                nm_b += 1
                logger.debug("file exists, number is incremented: <filename>_%s" % nm_b)
            else:
                logger.info("database filname: %s" % self.base_name)
                break

    def run(self):
        logger.info(self.__class__.__name__ + " START")
        self.check_on_args()
        self.check_on_file()

        if len(self.names) != len(self.in_queues):
            logger.error("incoming args array has different lengths of columns: len(arg[0]) = %s len(arg[0]) = %s" % (
            len(self.names), len(self.in_queues)))
            return 1

        logger.debug("input queues number - %s" % len(self.in_queues))
        buf_threads = []
        for i in range(len(self.in_queues)):
            thr = threading.Thread(name='buffering %s' % self.names[i], target=self.buffering,
                                   args=(self.in_queues[i], self.out_queues[i]))
            thr.start()
            buf_threads.append(thr)
        wr = threading.Thread(name='writer', target=self.writer)
        wr.start()
        for i in range(len(self.in_queues)):
            buf_threads[i].join()
        self.internal_stop.clear()
        logger.info("internal event is cleared")
        wr.join()
        logger.warning(self.__class__.__name__ + " END")

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
#   incoming array should be formatted as multidimensional array with 3 columns: table name, queue with data, names
#   of columns, split by "|" symbol.

#   Example:
#   in_ar = [["<sensor_1>", <queue_1>, "column_1|column_2"],
#           ["<sensor_2>", <queue_2>, "column_1|column_2"]]

#   Sample of the queue item has to contain such amount of elements as table's columns amount


#   Author: Ivan Matveev
#   E-mail: i.matveev@emw.hs-anhalt.de
#   Date: 17.11.2016


import threading
import Queue
import sqlite3 as lite
import os
import logging
import time


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

str_h = logging.StreamHandler()
str_h.setLevel(logging.INFO)

formatter = logging.Formatter('%(relativeCreated)6d - %(name)s - %(threadName)s - %(levelname)s - %(message)s')

str_h.setFormatter(formatter)
logger.addHandler(str_h)


class Statistic(threading.Thread):
    def __init__(self, stop, args, base_name='sen_info_0', buf_size=10000, commit_interval=60):
        threading.Thread.__init__(self, name="Main thread")
        temp = zip(*args)
        self.names = temp[0]
        self.in_queues = temp[1]
        self.col_names = temp[2]
        del temp
        self.commit_interval = commit_interval
        self.buf_size = buf_size

        self.stop_event = stop
        self.base_name = base_name
        self.out_queues = [Queue.Queue() for i in range(len(self.in_queues))]
        self.internal_stop = threading.Event()
        self.internal_stop.set()

    def writer(self):
        logger.info("Started")
        conn = lite.connect(self.base_name)
        cur = conn.cursor()
        temp = []
        sym_ar = []
        for i in range(len(self.col_names)):
            temp.append(self.col_names[i].split("|"))
            sym_ar.append(("?, " * len(temp[i]))[:-2])
        for i in range(len(self.out_queues)):
            cur.execute("CREATE TABLE %s (%s REAL)" % (self.names[i], temp[i][0]))
            logger.debug(self.names[i] + "table created")
            for x in range(len(temp[i])):
                if x != 0:
                    cur.execute("ALTER TABLE %s ADD COLUMN %s REAL" % (self.names[i], temp[i][x]))
        st_time = time.time()
        while self.internal_stop.isSet():
            try:
                for i in range(len(self.out_queues)):
                    packet = self.out_queues[i].get(timeout=3)          # In case of memory lick - correct timeout value
                    packet = zip(*packet)
                    cur.executemany("INSERT INTO %s VALUES(%s)" % (self.names[i], sym_ar[i]), packet)
            except Queue.Empty:
                logger.debug(self.names[i] + " queue timeout")

            qs_counter = 0
            for k in range(len(self.out_queues)):
                qs_counter += self.out_queues[k].qsize()

            if (time.time() - st_time) > self.commit_interval:
                st_time = time.time()
                conn.commit()
                logger.info("Commit performed")

            if not self.internal_stop.isSet() and qs_counter == 0:
                break
        conn.commit()
        conn.close()
        logger.info("Finished")

    def wrapper(self, in_q):
        temp = []
        try:
            sample = in_q.get(timeout=3)
            temp = [[sample[x]] for x in range(len(sample))]
        except Queue.Empty:
            logger.info("Wrapper in_q queue_1 timeout")
            return temp, False
        while len(temp[0]) < self.buf_size:
            try:
                sample = in_q.get(timeout=3)
                for x in range(len(temp)):
                    temp[x].append(sample[x])
            except Queue.Empty:
                logger.info("Wrapper in_q_2 queue timeout")
                return temp, False
        return temp, True

    def buffering(self, in_q, out_q):
        logger.info("Started")
        while True:
            packet, flag = self.wrapper(in_q)
            if not flag:
                logger.warning("Packet wraper timeout")
            out_q.put(packet)
            if not self.stop_event.isSet() and in_q.qsize() == 0:
                break
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Rest items in queue " + str(in_q.qsize()))
        logger.info("Finished")

    def check_on_file(self):
        logger.debug("Check file on existence")
        nm_b = 0
        while nm_b < 1000:
            self.base_name = 'sen_info_%s.db' % nm_b
            if os.path.exists(self.base_name):
                nm_b += 1
                logger.debug("File exists, number is incremented: <filename>_%s" % nm_b)
            else:
                logger.info("Database filename: %s" % self.base_name)
                break

    def run(self):
        logger.info("START")
        self.check_on_file()

        if len(self.names) != len(self.in_queues):
            logger.error("Incoming args array has different lengths of columns: len(arg[0]) = %s len(arg[0]) = %s" % (
            len(self.names), len(self.in_queues)))
            return 1

        logger.debug("Input queues number - %s" % len(self.in_queues))
        buf_threads = []
        for i in range(len(self.in_queues)):
            thr = threading.Thread(name='%s buffering thread' % self.names[i], target=self.buffering,
                                   args=(self.in_queues[i], self.out_queues[i]))
            thr.start()
            buf_threads.append(thr)
        wr = threading.Thread(name='Writer thread', target=self.writer)
        wr.start()

        while self.stop_event.is_set():
            time.sleep(1)
        logger.info("Stop event received")
        for i in range(len(self.in_queues)):
            buf_threads[i].join()
        self.internal_stop.clear()
        logger.info("Internal event is cleared")
        wr.join()
        logger.warning("END")

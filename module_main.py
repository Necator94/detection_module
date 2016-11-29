#!/usr/bin/env python

from module_lib import Module
import threading
import time
import logging.config


logging.config.fileConfig('logging.conf')
logger = logging.getLogger(__name__)

stop_ev = threading.Event()
stop_ev.set()

module = Module(stop_ev, full=True)
module.set_statistic_lvl(full=True)

st_time = time.time()
logger.info("Detection module started")
module.start()

try:
    while time.time() - st_time < 20:
        time.sleep(1)
except KeyboardInterrupt:
    logger.warning("Keyboard Interrupt, threads are going to stop")
stop_ev.clear()

module.join()
logger.info("Detection module finished")

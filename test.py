from statistic_lib import Statistic
import time
import threading
import Queue

a = Queue.Queue()
b = Queue.Queue()
c = Queue.Queue()
d = Queue.Queue()


in_ar = {"PIR": {"col_name": ["Time", "Value"], "queue": a}}

event = threading.Event()
event.set()

stat = Statistic( event, in_ar, commit_interval=40)

stat.start()

i = 0
try:
    while True:
        a.put(time.time(), i)
        time.sleep(0.01)
        i += 1
except KeyboardInterrupt:
    event.clear()
event.clear()

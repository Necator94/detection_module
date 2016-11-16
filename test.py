from statistic_log import statistic
import time
import threading
import Queue

a = Queue.Queue()
b = Queue.Queue()

in_ar = [[]for x in range(2)]
in_ar[0].append("PIR")
in_ar[0].append("RW")
in_ar[1].append(a)
in_ar[1].append(b)

event = threading.Event()
event.set()


stat = statistic(in_ar, event)

stat.start()


i = 0
while i < 106:
    sample = []
    sample.append(i)
    sample.append(time.time())

    sample1 = []
    sample1.append(i)
    sample1.append(1)

    a.put(sample)
    b.put(sample1)
    i += 1

event.clear()

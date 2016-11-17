from statistic_log import statistic
import time
import threading
import Queue

a = Queue.Queue()
b = Queue.Queue()
c = Queue.Queue()
d = Queue.Queue()

in_1 = ["PIR", "RW", "Ultrasonic", "kek"]

in_2 = [a, b, c, d]

in_3 = ["Time|Value", "Time|Value", "Time|Value", "Time|Value"]
in_ar = [[]for i in range(3)]
in_ar[0] = in_1
in_ar[1] = in_2
in_ar[2] = in_3


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

    sample2 = []
    sample2.append(i)
    sample2.append(2)

    sample3 = []
    sample3.append(i)
    sample3.append(3)

    a.put(sample)
    b.put(sample1)
    c.put(sample2)
    d.put(sample3)
    i += 1

event.clear()

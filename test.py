from statistic_log import statistic
import time
import threading
import Queue

a = Queue.Queue()
b = Queue.Queue()
c = Queue.Queue()
d = Queue.Queue()

in_ar = [["PIR", a, "Time|Value"],
        ["RW", b, "Time|Value"],
        ["Ultrasonic", c, "Time|Value"],
        ["Kek", d, "Time"]]





event = threading.Event()
event.set()


stat = statistic(in_ar, event, commit_interval=40)

stat.start()


i = 0
try:
    while True:
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


        a.put(sample)
        b.put(sample1)
        c.put(sample2)
        d.put(sample3)
        time.sleep(0.01)
        i += 1
except KeyboardInterrupt:
    event.clear()
event.clear()

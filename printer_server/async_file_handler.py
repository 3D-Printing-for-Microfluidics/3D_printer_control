import time
import queue
import threading


class AsyncFileHandler:
    def __init__(self):
        self.queues = {}
        self.thread_stopped = threading.Event()
        self.thread = None
        self.enabled = True

    def set_enabled(self, enabled):
        self.enabled = enabled

    def start(self):
        if self.enabled and self.thread is None:
            self.thread_stopped.clear()
            self.thread = threading.Thread(target=self.loop)
            self.thread.start()

    def write(self, filename, msg):
        if self.enabled:
            if filename not in self.queues:
                open(filename, "w").close()
                self.queues[filename] = queue.Queue()
            self.queues[filename].put(msg)

    def finish(self):
        if self.enabled and self.thread is not None:
            for key in self.queues:
                q = self.queues[key]
                q.join()
            self.thread_stopped.set()
            self.thread.join()
            self.thread = None
            for key in self.queues:
                q = self.queues[key]
                del q
            self.queues = {}

    def loop(self):
        while True:
            if self.thread_stopped.is_set():
                break
            for key in self.queues:
                q = self.queues[key]
                if not q.empty():
                    with open(key, "a") as f:
                        while not q.empty():
                            msg = q.get()
                            f.write(msg)
                            q.task_done()
            time.sleep(0.01)


async_file_hander = AsyncFileHandler()

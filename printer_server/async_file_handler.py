import time
import queue
import logging
import threading
from printer_server.threading_wrapper import Thread


class AsyncFileHandler:
    def __init__(self):
        self.queues = {}
        self.thread_stopped = threading.Event()
        self.thread = None
        self.enabled = True

        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.INFO)

    def set_enabled(self, enabled):
        self.enabled = enabled

    def start(self):
        if self.enabled and self.thread is None:
            self.thread_stopped.clear()
            self.thread = Thread(self.log, name="async_file_handler_thread", target=self.loop)
            self.thread.start()

    def write(self, filename, msg):
        if self.enabled:
            if filename not in self.queues:
                open(filename, "w").close()
                self.queues[filename] = queue.Queue()
            self.queues[filename].put(msg)

    def finish(self):
        if self.enabled and self.thread is not None:
            for _, q in self.queues.items():
                q.join()
            self.thread_stopped.set()
            self.thread.join()
            self.thread = None
            for _, q in self.queues.items():
                del q
            self.queues = {}

    def loop(self):
        while True:
            if self.thread_stopped.is_set():
                break
            for key in list(self.queues.keys()):
                q = self.queues[key]
                if not q.empty():
                    with open(key, "a") as f:
                        while not q.empty():
                            msg = q.get()
                            f.write(msg)
                            q.task_done()
            time.sleep(0.01)


async_file_hander = AsyncFileHandler()

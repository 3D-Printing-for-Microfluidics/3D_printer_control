import threading
import logging

# Wrapper of Thread class that logs exception using logging class
class Thread(threading.Thread):
    def __init__(self, log, group=None, target=None, name=None, args=(), kwargs=None, daemon=None):
        super().__init__(group=group, target=target, name=name, args=args, kwargs=kwargs, daemon=daemon)
        self.log = log
        self.name = name
        
    def run(self):
        # Variable that stores the exception, if raised by someFunction
        # self.exc = None        
        try:
            if self._target is not None:
                self._target(*self._args, **self._kwargs)
        except BaseException as e:
            self.log.error("Error thrown in thread: %s", self.name)
            self.log.exception(e)
            # self.exc = e
            raise e
        finally:
            # Avoid a refcycle if the thread is running a function with
            # an argument that has a member that points to the thread.
            del self._target, self._args, self._kwargs
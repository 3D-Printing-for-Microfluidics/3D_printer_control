import logging
import cProfile
import threading
from pathlib import Path
from printer_server.settings import Config

# Wrapper of Thread class that logs exception using logging class (could also add profiling...)
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
                if Config.LOG_THREADING:
                    self.log.info("Starting Thread: %s", self.name)
                if Config.PROFILE_CODE:
                    # Create profiles directory if it doesn't exist
                    profiles_dir = Path(Config.PROFILES_FOLDER)
                    profiles_dir.mkdir(exist_ok=True)

                    # Generate a unique profile filename
                    index = 0
                    while (profiles_dir / f"{self.name}_{index}").is_file():
                        index += 1

                    profile_filename = profiles_dir / f"{self.name}_{index}"

                    # Set up globals and locals dictionaries
                    globals_dict = globals().copy()
                    locals_dict = locals().copy()
                    # locals_dict['self'] = None  # Set self to None to avoid reference issues in the string

                    # Run code with cProfile
                    cProfile.runctx("self._target(*self._args, **self._kwargs)", globals_dict, locals_dict, filename=str(profile_filename))
                else:
                    self._target(*self._args, **self._kwargs)
        except BaseException as e:
            self.log.error("Error thrown in thread: %s", self.name)
            self.log.exception(e)
            # self.exc = e
            raise e
        finally:
            # Avoid a refcycle if the thread is running a function with
            # an argument that has a member that points to the thread.
            if Config.LOG_THREADING:
                self.log.info("Stopping Thread: %s", self.name)
            del self._target, self._args, self._kwargs
import time
import atexit
import logging

class EthernetSerial():
    pass
    # def __init__(
    #     self,
    #     config_dict=None,
    #     log_level=logging.DEBUG,
    # ):
    #     self.log = logging.getLogger(__name__)
    #     self.log.setLevel(log_level)

    #     self.config_dict = config_dict
    #     self.sendLock = threading.Lock()
    #     self.connected = None
    #     self.initialized = None
    #     self.socket = None

    # def connect(self, shutdown):
    #     """Find the first ACS controller and connect to it."""
    #     if self.connected is None:
    #         attempts=10
    #         timeout=1
            
    #         self.connected = False
    #         self.address = self.config_dict["address"]
    #         self.port = self.config_dict["port"]
    #         self.log.info("Connecting to ACS (%s), this may take up to 1 minute...", self.address)
    #         i = 0
    #         while i < attempts:  # try up to attempts number of times to create a connection
    #             i += 1
    #             try:
    #                 self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #                 self.socket.settimeout(10)
    #                 self.socket.connect((self.address, self.port))
    #                 self.connected = True
    #                 self.shutdown = shutdown
    #             except (OSError, socket.timeout) as e:
    #                 if "timed out" in e:
    #                     i = attempts
    #                 self.log.info("%s. Retrying in %s second(s)", e, timeout)
    #                 self.socket = None  # get rid of handle to bad socket
    #                 time.sleep(timeout)  # wait to try again
    #         if not self.connected:
    #             msg = f"ACS controller not found!"
    #             self.log.critical(msg)
    #             return False
            
    #         self.thread_running = True
    #         self.thread.start()
    #         atexit.register(self.disconnect)
    #         self.log.info("Connected to ACS controller")
    #         return True
    #     else:
    #         while self.connected is False:
    #             time.sleep(0.1)

    # def disconnect(self):
    #     """Disconnect form the ACS controller."""
    #     if self.connected is not None and self.connected is not False:
    #         for axis in self.axes:
    #             self.motorOff(axis)

    #         self.thread_running = False
    #         try:
    #             self.thread.join()
    #         except RuntimeError:
    #             pass
    #         self.thread = Thread(self.log, name="acs_loop_thread", target=self.loop)
    #         self.thread.daemon = True

    #         self.connected = None
    #         self.initialized = None
    #         try:
    #             if self.socket is not None:
    #                 with self.sendLock:
    #                     self.socket.close()
    #                 self.socket = None
    #             self.log.info("Disconnected from ACS controller")
    #         except:
    #             self.log.error("Unexpected error on disconnect")

    # def send(self, command, notify=True):
    #     """Send a command to the controller.

    #     If an error is returned, request and also return more
    #     information about the error.
    #     """
    #     with self.sendLock:
    #         if notify:
    #             self.log.debug("Sent : '%s'", command)
    #         response = self._send(command)
    #         response = "".join(response)
    #         self.log.debug("Reply: '%s'", response)
    #         if response != "":
    #             if notify:
    #                 self.log.debug("Reply: '%s'", response)
    #             if response[0] == '?':
    #                 self.log.error("Last command '%s' returned error '%s (%s)'", command, response, self.send(f"?{response}"))
    #         return response
                
    # def _send(self, msg):
    #     msg += "\r"
    #     encoded_message = msg.encode()
    #     try:
    #         self.socket.sendall(encoded_message)
    #     except socket.timeout:
    #         msg = "ACS controller send timed out!"
    #         self.log.critical(msg)
    #         self.shutdown(is_critical = True)
    #         sys.exit(msg)
    #     except Exception as ex:
    #         self.log.error("Failed to send packet: %s", ex)

    #     try:
    #         msg = self.socket.recv(1024).decode()
    #         return msg.strip()[:-1].strip()
    #     except socket.timeout:
    #         msg = "ACS controller recieve timed out!"
    #         self.log.critical(msg)
    #         self.shutdown(is_critical = True)
    #         sys.exit(msg)
    #     except Exception as e:
    #         self.log.error("Failed to receive packet: %s", e)
    #     return None
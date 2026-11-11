"""Resilient Bluetooth reconnection coordinator for PiRadio 7.

Uses the existing AudioOutputManager/BlueZ methods; never scans, pairs,
changes device preferences, restarts Bluetooth, or blocks the render loop.
Only attempts connection to a device the user already paired and selected.
"""
import threading
import time

HEALTH_INTERVAL = 40
BACKOFF = (25, 50, 100, 180, 300)


class BluetoothReconnectSupervisor:
    def __init__(self, manager, *, clock=time.monotonic, thread_factory=threading.Thread):
        self.manager = manager
        self.clock = clock
        self.thread_factory = thread_factory
        self._lock = threading.Lock()
        self._running = False
        self._next = 0.0
        self._failures = 0
        self._message = "No preferred Bluetooth speaker"

    def snapshot(self):
        with self._lock:
            return {"busy": self._running, "message": self._message,
                    "attempts": self._failures,
                    "preferred": self.manager.default_bluetooth_address or ""}

    def tick(self, now=None):
        address = self.manager.default_bluetooth_address
        if not address:
            with self._lock:
                self._message = "No preferred Bluetooth speaker"
                self._failures = 0
            return
        now = self.clock() if now is None else now
        with self._lock:
            if self._running or now < self._next:
                return
            if self.manager.bluetooth_lock.locked():
                self._next = now + 8
                return
            self._running = True
            self._next = now + HEALTH_INTERVAL
            self._message = "Checking preferred speaker"
        self.thread_factory(
            target=self._worker, args=(address,),
            daemon=True,
        ).start()

    def _worker(self, address):
        try:
            if self.manager.default_bluetooth_address != address:
                return
            devices, paired, connected = self.manager._bluetooth_device_sets()
            if address not in paired:
                with self._lock:
                    self._message = "Pair preferred speaker in Bluetooth settings"
                    self._next = self.clock() + 120
                return
            if address in connected:
                # BlueZ can report connected before an A2DP sink is ready.
                if self.manager.current_output != "bluetooth":
                    self.manager.connect_bluetooth(address)
                with self._lock:
                    self._failures = 0
                    self._next = self.clock() + HEALTH_INTERVAL
                    self._message = "Preferred Bluetooth speaker connected"
                return
            # Only the user's chosen paired device can reconnect; no scanning
            # or automatic pairing with nearby unknown speakers.
            self.manager.connect_bluetooth(address)
            with self._lock:
                self._failures = 0
                self._next = self.clock() + HEALTH_INTERVAL
                self._message = "Bluetooth reconnected"
        except (OSError, RuntimeError, ValueError) as error:
            with self._lock:
                self._failures += 1
                delay = BACKOFF[min(self._failures - 1, len(BACKOFF) - 1)]
                self._next = self.clock() + delay
                self._message = "Reconnect retry in %d seconds" % delay
        finally:
            with self._lock:
                self._running = False

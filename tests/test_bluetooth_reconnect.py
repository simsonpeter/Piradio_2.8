"""PiRadio Bluetooth auto reconnect regression tests. No live BlueZ needed."""
import threading
import unittest
from pathlib import Path
from bluetooth_reconnect import BluetoothReconnectSupervisor, BACKOFF, HEALTH_INTERVAL


class DeferredThread:
    calls=[]
    def __init__(self, *, target, args=(), daemon=False):
        self.target=target
        self.args=args
        self.daemon=daemon
        DeferredThread.calls.append(self)
    def start(self):
        pass
    def run(self):
        self.target(*self.args)


class FakeBluetoothManager:
    def __init__(self):
        self.default_bluetooth_address="AA:BB:CC:DD:EE:FF"
        self.bluetooth_lock=threading.Lock()
        self.current_output="auto"
        self.paired={self.default_bluetooth_address}
        self.connected=set()
        self.fail=False
        self.calls=[]
        self.checks=0
    def _bluetooth_device_sets(self):
        self.checks+=1
        return ({},self.paired,self.connected)
    def connect_bluetooth(self,address):
        self.calls.append(address)
        if self.fail:
            raise RuntimeError("Device switched off")
        self.current_output="bluetooth"
        self.connected.add(address)


class Tests(unittest.TestCase):
    def setUp(self):
        DeferredThread.calls.clear()
        self.manager=FakeBluetoothManager()
        self.now=[500.0]
        self.supervisor=BluetoothReconnectSupervisor(self.manager,
                          clock=lambda:self.now[0],thread_factory=DeferredThread)
    def run_once(self):
        self.supervisor.tick()
        self.assertEqual(len(DeferredThread.calls),1)
        DeferredThread.calls.pop().run()

    def test_no_preference_never_triggers_pairing(self):
        self.manager.default_bluetooth_address=None
        self.supervisor.tick()
        self.assertEqual(DeferredThread.calls,[])
        self.assertIn("No preferred",self.supervisor.snapshot()["message"])
    def test_auto_connects_only_explicit_preferred_paired_address(self):
        self.run_once()
        self.assertEqual(self.manager.calls,["AA:BB:CC:DD:EE:FF"])
        self.assertIn("reconnected",self.supervisor.snapshot()["message"])
        self.assertFalse(self.supervisor.snapshot()["busy"])
        self.supervisor.tick()
        self.assertEqual(DeferredThread.calls,[])
        self.now[0]+=HEALTH_INTERVAL+1
        self.run_once()
        self.assertEqual(len(self.manager.calls),1)
    def test_avoids_connecting_unpaired_or_scanning(self):
        self.manager.paired=set()
        self.run_once()
        self.assertEqual(self.manager.calls,[])
        self.assertIn("Pair preferred",self.supervisor.snapshot()["message"])
    def test_exponential_backoff_does_not_repeat_fast(self):
        self.manager.fail=True
        self.run_once()
        self.assertEqual(self.supervisor.snapshot()["attempts"],1)
        self.assertIn(str(BACKOFF[0]),self.supervisor.snapshot()["message"])
        self.supervisor.tick()
        self.assertEqual(DeferredThread.calls,[])
        self.now[0]+=BACKOFF[0]+1
        self.run_once()
        self.assertEqual(self.supervisor.snapshot()["attempts"],2)
        self.assertIn(str(BACKOFF[1]),self.supervisor.snapshot()["message"])
    def test_manual_connection_lock_defers_worker(self):
        self.manager.bluetooth_lock.acquire()
        try:
            self.supervisor.tick()
            self.assertEqual(DeferredThread.calls,[])
        finally:
            self.manager.bluetooth_lock.release()
        self.now[0]+=9
        self.run_once()
    def test_no_competing_boot_reconnect_thread(self):
        text=Path("touch_radio.py").read_text()
        self.assertIn("bluetooth_reconnect.tick()",text)
        self.assertIn("BluetoothReconnectSupervisor(audio_manager)",text)
        self.assertNotIn("target=self._restore_bluetooth_default",text)


if __name__=="__main__":
    unittest.main()

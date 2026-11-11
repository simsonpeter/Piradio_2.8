"""Non-invasive PiRadio 7 Audio Visualizer Pro tests."""
import unittest
import math
import struct
from pathlib import Path
from unittest.mock import Mock, patch
import pygame
from audio_visualizer import (AudioSpectrumMonitor, BANDS,
                              monitor_command, spectrum_from_pcm, np)
from landscape_audio_visualizer import BACK, draw, hit
from landscape_smart_home import VISUALIZER_BUTTON, hit as home_hit


class SpectrumTests(unittest.TestCase):
    def test_monitor_only_listens_to_output_not_microphone(self):
        self.assertEqual(monitor_command("alsa_output.usb-test"),
                         ["parec", "--raw", "--format=s16le",
                          "--rate=16000", "--channels=1",
                          "--device=alsa_output.usb-test.monitor"])
        with self.assertRaises(ValueError):
            monitor_command("bad sink")
        with self.assertRaises(ValueError):
            monitor_command("")
    def test_missing_monitor_is_explicit_and_zero_not_fake(self):
        monitor=AudioSpectrumMonitor(executable=lambda _:None)
        self.assertEqual(monitor.snapshot()["levels"],tuple([0.0]*BANDS))
        monitor._worker(monitor._generation)
        self.assertFalse(monitor.snapshot()["active"])
        self.assertIn("unavailable" if np is not None else "numpy",
                      monitor.snapshot()["message"].lower())
    @unittest.skipIf(np is None,"Optional python3-numpy not installed in runner")
    def test_silence_is_not_fake_signal(self):
        self.assertEqual(spectrum_from_pcm(bytes(2048*2)),tuple([0.0]*BANDS))

    @unittest.skipIf(np is None,"Optional python3-numpy not installed in runner")
    def test_real_tone_drives_matching_low_frequency_bands(self):
        sine=[int(14000*math.sin(2*math.pi*100*i/16000))
              for i in range(2048)]
        pcm=struct.pack("<2048h",*sine)
        bars=spectrum_from_pcm(pcm)
        self.assertEqual(len(bars),24)
        self.assertGreater(max(bars[:7]),0.4)
        self.assertLess(max(bars[13:]),0.08)
        self.assertTrue(all(0 <= v <= 1 for v in bars))
    def test_unavailable_monitor_does_not_spawn_workers_every_frame(self):
        clock=[100.0]
        monitor=AudioSpectrumMonitor(clock=lambda:clock[0])
        with patch("audio_visualizer.threading.Thread") as thread:
            monitor.start()
            self.assertEqual(thread.call_count,1)
            generation=monitor._generation
            monitor._failure(generation,"Missing monitor")
            for _ in range(100):
                monitor.start()
            self.assertEqual(thread.call_count,1)
            clock[0]+=21
            monitor.start()
            self.assertEqual(thread.call_count,2)
            monitor.stop()
            monitor.start()
            self.assertEqual(thread.call_count,3)

    def test_stale_audio_worker_failure_does_not_override_stop(self):
        monitor=AudioSpectrumMonitor()
        monitor.start()
        old_generation=monitor._generation
        monitor.stop()
        monitor._failure(old_generation,"Old sink disconnected")
        self.assertFalse(monitor.snapshot()["active"])
        self.assertEqual(monitor.snapshot()["message"],"Visualizer stopped")

    def test_real_capture_is_not_run_on_pygame_thread(self):
        code=Path("touch_radio.py").read_text()
        self.assertIn("audio_spectrum_monitor.start()",code)
        self.assertIn("audio_spectrum_monitor.stop()",code)
        self.assertIn("audio_spectrum_monitor.snapshot()",code)
        self.assertIn('if active_page == "visualizer":',code)


class ScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()
    @classmethod
    def tearDownClass(cls):
        pygame.quit()
    def test_home_has_visualizer_action_without_overwriting_media(self):
        self.assertEqual(home_hit(VISUALIZER_BUTTON.center),
                         ("page","visualizer"))
    def test_visualizer_draws_24_real_bars_and_has_home(self):
        s=pygame.Surface((800,480))
        fonts=[pygame.font.Font(None,i) for i in (30,22,17)]
        data={"levels":tuple([0.0]*BANDS),"message":"No sink",
              "active":False}
        media={"source":"radio","playing":True,"title":"TC Radios"}
        self.assertTrue(draw(s,*fonts,data,media))
        self.assertEqual(hit(BACK.center),("page","menu"))
        self.assertIsNone(hit((395,330)))
        self.assertNotEqual(tuple(s.get_at((100,380))[:3]),(0,0,0))
        bright={"levels":tuple([0.7]*BANDS),"message":"Real-time",
                "active":True}
        draw(s,*fonts,bright,media)
        self.assertNotEqual(tuple(s.get_at((100,380))[:3]),(40,48,52))
        draw(s,*fonts,bright,{"source":"radio","playing":False})
        self.assertEqual(tuple(s.get_at((100,380))[:3]),(40,48,52))
    def test_visualizer_keeps_existing_sound_players_independent(self):
        code=Path("audio_visualizer.py").read_text()
        self.assertNotIn("player.stop(",code)
        self.assertNotIn("player.pause(",code)
        self.assertNotIn("set-default-sink",code)
        self.assertNotIn("amixer",code)


if __name__=="__main__":
    unittest.main()

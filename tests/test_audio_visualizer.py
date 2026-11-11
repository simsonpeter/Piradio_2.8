"""Non-invasive PiRadio 7 Audio Visualizer Pro tests."""
import unittest
from pathlib import Path
from unittest.mock import Mock
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

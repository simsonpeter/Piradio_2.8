"""Headless tests for PiRadio 7 premium Home Dashboard (800x480)."""
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import unittest

import pygame

from landscape_smart_home import (
    CLOCK, WEATHER, MEDIA, MEDIA_PAUSE, SHORTCUT_RECTS, draw, hit,
    _temperature, _weather_label,
)


class SmartHomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.surface = pygame.Surface((800, 480))
        self.fonts = (
            pygame.font.Font(None, 31),
            pygame.font.Font(None, 23),
            pygame.font.Font(None, 18),
        )
        self.stamp = datetime(2026, 11, 11, 14, 30)
        self.media = dict(
            source="radio", title="TC Radio", playing=True,
            paused=False, minimized=False, volume=46,
        )

    def test_dashboard_renders_800x480_without_sidebar(self):
        self.assertTrue(draw(
            self.surface, *self.fonts, self.media,
            temperature=13, weather_type="partly_cloudy",
            weather_available=True, city="Antwerpen", now=self.stamp,
        ))
        self.assertNotEqual(self.surface.get_at(CLOCK.center)[:3], (0, 0, 0))
        self.assertNotEqual(self.surface.get_at(WEATHER.center)[:3], (0, 0, 0))
        self.assertNotEqual(self.surface.get_at(MEDIA.center)[:3], (0, 0, 0))
        self.assertTrue(CLOCK.collidepoint((250, 160)))
        self.assertTrue(MEDIA.contains(MEDIA_PAUSE))
        for rect in SHORTCUT_RECTS.values():
            self.assertTrue(0 <= rect.left < rect.right <= 800)
            self.assertTrue(65 < rect.top < rect.bottom <= 465)

    def test_clock_and_weather_are_cached_read_only_widgets(self):
        with patch("landscape_smart_home._text") as render:
            draw(self.surface, *self.fonts, self.media,
                 temperature=13, weather_type="partly_cloudy",
                 weather_available=True, city="Antwerpen",
                 now=self.stamp)
        labels = [str(call.args[2]) for call in render.call_args_list]
        for token in ("14:30", "Wednesday, 11 November 2026",
                      "13°", "Partly Cloudy", "Antwerpen", "TC Radio"):
            self.assertIn(token, labels)

    def test_offline_weather_never_invents_temperature(self):
        self.assertEqual(_temperature(19, False), "--°")
        self.assertEqual(_temperature(float("nan"), True), "--°")
        self.assertEqual(_temperature(None, True), "--°")
        self.assertEqual(_weather_label("sunny", False), "WEATHER UNAVAILABLE")
        with patch("landscape_smart_home._text") as render:
            draw(self.surface, *self.fonts, self.media, city="Ghent",
                 weather_available=False, now=self.stamp)
        labels = [str(call.args[2]) for call in render.call_args_list]
        self.assertIn("--°", labels)
        self.assertIn("WEATHER UNAVAILABLE", labels)

    def test_now_playing_uses_real_cast_source_and_not_previous_radio(self):
        state = dict(source="guest_video", title="Phone sent video",
                     playing=False, paused=True, minimized=True)
        old_radio_logo = pygame.Surface((100, 100))
        old_radio_logo.fill((228, 2, 189))
        with patch("landscape_smart_home._text") as render:
            draw(self.surface, *self.fonts, state, artwork=old_radio_logo,
                 now=self.stamp)
        labels = [str(call.args[2]) for call in render.call_args_list]
        self.assertIn("PHONE VIDEO", labels)
        self.assertIn("Phone sent video", labels)
        self.assertIn("PAUSED  ·  TAP FOR PLAYER", labels)
        self.assertNotIn("TC Radio", labels)
        self.assertNotEqual(self.surface.get_at((76, 318))[:3], (228, 2, 189))

    def test_media_controls_and_quick_tiles(self):
        self.assertEqual(hit(MEDIA_PAUSE.center), ("toggle", None))
        self.assertEqual(hit((150, 310)), ("now_playing", None))
        self.assertEqual(hit(CLOCK.center), ("clock", None))
        self.assertEqual(hit(WEATHER.center), ("forecast", None))
        destinations = {
            "RADIO": "radio", "BIBLE": "bible", "YOUTUBE": "youtube",
            "PHOTOS": "photo_frame", "FAVOURITES": "favorites",
        }
        for label, destination in destinations.items():
            self.assertEqual(hit(SHORTCUT_RECTS[label].center),
                             ("page", destination))
        self.assertIsNone(hit((8, 8)))

    def test_station_logo_only_for_radio_or_youtube_audio(self):
        cover = pygame.Surface((100, 100))
        cover.fill((40, 88, 129))
        draw(self.surface, *self.fonts, self.media, artwork=cover,
             now=self.stamp)
        self.assertEqual(self.surface.get_at((76, 318))[:3], (40, 88, 129))
        state = dict(source="bible", title="Tamil Bible", playing=True)
        draw(self.surface, *self.fonts, state, artwork=cover, now=self.stamp)
        self.assertNotEqual(self.surface.get_at((76, 318))[:3], (40, 88, 129))

    def test_source_code_routes_native_touches_without_scaling(self):
        source = Path("touch_radio.py").read_text(encoding="utf-8")
        self.assertIn('if active_page == "menu":', source)
        self.assertIn("smart_home_hit(actual_pos)", source)
        self.assertIn("draw_smart_home(", source)
        self.assertIn("photo_frame_renderer.activate(now)", source)
        self.assertIn('active_page = "now_playing"', source)


if __name__ == "__main__":
    unittest.main()

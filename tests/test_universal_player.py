"""Device-independent 800x480 visual and hit-target regression tests."""
from pathlib import Path
import unittest
from unittest.mock import patch

import pygame

from landscape_universal_player import (
    PANEL, ART, BACK, FULL_VIDEO, PREV, TOGGLE, NEXT, STOP,
    TRACK, VOLUME, draw, hit, _duration, _can_seek,
)
from landscape_dashboard import video_mini_hit
from media_session import resolve_media_snapshot


class UniversalPlayerTests(unittest.TestCase):
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
            pygame.font.Font(None, 30),
            pygame.font.Font(None, 22),
            pygame.font.Font(None, 18),
        )

    def state(self, **overrides):
        obj = resolve_media_snapshot(
            vlc_state="playing", vlc_title="Original station",
            volume=45, station=3,
        ).as_dict()
        obj.update(overrides)
        return obj

    def test_panel_draws_inside_800x480_screen(self):
        state = self.state()
        self.assertTrue(draw(self.surface, *self.fonts, state))
        self.assertNotEqual(self.surface.get_at(PANEL.center)[:3], (0, 0, 0))
        self.assertTrue(PANEL.contains(ART))
        self.assertTrue(PANEL.contains(TOGGLE))
        self.assertTrue(PANEL.contains(VOLUME))
        self.assertFalse(TOGGLE.colliderect(TRACK))

    def test_current_cast_title_replaces_radio_and_old_station_artwork(self):
        state = self.state(
            source="guest_video", title="Phone movie",
            playing=True, minimized=True, paused=False,
            duration=180, position=72, seekable=True,
        )
        old_logo = pygame.Surface((200, 200))
        old_logo.fill((250, 0, 200))
        with patch("landscape_universal_player._text") as labels:
            self.assertTrue(draw(self.surface, *self.fonts, state, old_logo))
        drawn = [str(call.args[2]) for call in labels.call_args_list]
        self.assertIn("Phone movie", drawn)
        self.assertNotIn("Original station", drawn)
        # MPV sources must never reuse a previous VLC radio station cover.
        self.assertNotEqual(self.surface.get_at(ART.center)[:3], (250, 0, 200))

    def test_radio_artwork_is_allowed_for_current_radio(self):
        logo = pygame.Surface((200, 200))
        logo.fill((170, 80, 35))
        draw(self.surface, *self.fonts, self.state(), logo)
        self.assertEqual(self.surface.get_at(ART.center)[:3], (170, 80, 35))

    def test_volume_and_seeking_target_absolute_point(self):
        state = self.state(
            source="youtube_audio", title="Worship song",
            position=50, duration=200, seekable=True,
        )
        self.assertEqual(hit(TOGGLE.center, state), ("toggle", None))
        self.assertEqual(hit(PREV.center, state), ("prev", None))
        self.assertEqual(hit(NEXT.center, state), ("next", None))
        self.assertEqual(hit(STOP.center, state), ("stop", None))
        self.assertEqual(hit(BACK.center, state), ("back", None))
        kind, seconds = hit(TRACK.center, state)
        self.assertEqual(kind, "seek")
        self.assertAlmostEqual(seconds, 100, delta=1)
        self.assertEqual(hit((VOLUME.x, VOLUME.centery), state), ("volume", 0))
        self.assertEqual(hit((VOLUME.right, VOLUME.centery), state), ("volume", 100))

    def test_streams_without_timeline_never_seek(self):
        for source in ("radio", "bible", "guest_photos", "screen_mirror"):
            with self.subTest(source=source):
                state = self.state(
                    source=source, duration=120, position=20, seekable=True
                )
                self.assertFalse(_can_seek(state))
                self.assertEqual(hit(TRACK.center, state)[0], "consume")
                self.assertTrue(draw(self.surface, *self.fonts, state))

    def test_live_screen_mirror_hides_seek_buttons(self):
        state = self.state(source="screen_mirror")
        self.assertEqual(hit(PREV.center, state)[0], "consume")
        self.assertEqual(hit(NEXT.center, state)[0], "consume")

    def test_explicit_video_restores_and_back_is_separate(self):
        state = self.state(source="guest_video", minimized=True)
        self.assertEqual(hit(FULL_VIDEO.center, state), ("restore", None))
        self.assertEqual(hit(BACK.center, state), ("back", None))
        radio = self.state(source="radio")
        self.assertNotEqual(hit(FULL_VIDEO.center, radio), ("restore", None))

    def test_minimized_mpv_title_opens_player_and_full_button_restores(self):
        state = {
            "playing": True, "minimized": True, "title": "Guest video",
            "source": "guest_video", "duration": 180
        }
        self.assertEqual(video_mini_hit((300, 418), state),
                         ("open_player", None))
        self.assertEqual(video_mini_hit((690, 428), state),
                         ("restore", None))

    def test_safe_timing_and_no_hit_outside_panel(self):
        self.assertEqual(_duration(3665), "1:01:05")
        self.assertEqual(_duration(-1), "--:--")
        self.assertEqual(_duration(float("nan")), "--:--")
        self.assertIsNone(hit((14, 8), self.state()))

    def test_existing_touchscreen_has_dedicated_universal_page(self):
        source = Path("touch_radio.py").read_text(encoding="utf-8")
        self.assertIn('active_page == "now_playing"', source)
        self.assertIn("draw_universal_player(", source)
        self.assertIn("universal_player_hit(", source)
        self.assertIn('control_active_media("restore", mpv_only=True)', source)
        self.assertIn("now_playing_return_page = active_page", source)


if __name__ == "__main__":
    unittest.main()

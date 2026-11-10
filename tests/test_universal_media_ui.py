"""Headless 800x480 rendering checks for the shared PiRadio media session."""
import unittest
from unittest.mock import patch

import pygame

from landscape_dashboard import (
    draw_dashboard, draw_shell, media_display_info,
)
from media_session import resolve_media_snapshot


class UniversalMediaScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.surface = pygame.Surface((800, 480))
        self.fonts = tuple(pygame.font.Font(None, n) for n in (30, 22, 17))

    def cast(self, **extra):
        status = dict(
            playing=True, source="guest_video", title="Phone uploaded movie",
            paused=False, position=50, duration=160, minimized=True,
        )
        status.update(extra)
        snapshot = resolve_media_snapshot(
            video_status=status,
            vlc_state="playing",
            vlc_title="Old radio metadata",
        ).as_dict()
        return status, snapshot

    def test_session_labels_phone_media_not_old_radio(self):
        status, snapshot = self.cast()
        info = media_display_info(
            snapshot, "Old radio station", "Old radio metadata",
            False, "Tamil Bible", False,
        )
        self.assertEqual(info["title"], "Phone uploaded movie")
        self.assertEqual(info["icon"], "film")
        self.assertEqual(info["subtitle"], "Audio playing in background")
        self.assertFalse(info["use_station_logo"])
        self.assertTrue(info["playing"])

    def test_paused_cast_still_owns_the_mini_player(self):
        _status, snapshot = self.cast(paused=True)
        info = media_display_info(
            snapshot, "Old radio station", "", True, "Tamil Bible", False,
        )
        self.assertEqual(info["title"], "Phone uploaded movie")
        self.assertEqual(info["subtitle"], "Paused")
        self.assertFalse(info["playing"])

    def test_bible_and_youtube_audio_use_correct_icons(self):
        bible = resolve_media_snapshot(
            bible_active=True, bible_title="Tamil Bible chapter 1"
        ).as_dict()
        youtube = resolve_media_snapshot(
            vlc_state="playing", vlc_source="youtube_audio",
            vlc_title="Worship song"
        ).as_dict()
        b = media_display_info(bible, "Old radio", "", True, "", False)
        y = media_display_info(youtube, "Old radio", "", False, "", True)
        self.assertEqual(b["icon"], "bible")
        self.assertEqual(b["title"], "Tamil Bible chapter 1")
        self.assertEqual(y["icon"], "youtube")
        self.assertEqual(y["title"], "Worship song")

    def test_home_widget_renders_current_cast_metadata(self):
        status, snapshot = self.cast()
        with patch("landscape_dashboard._text") as render:
            draw_dashboard(
                self.surface, *self.fonts, "menu", "Old radio station",
                "Old radio metadata", True, False, False, "Tamil Bible", 55,
                video_status=status, media_snapshot=snapshot,
            )
        labels = [call.args[2] for call in render.call_args_list]
        self.assertIn("Phone uploaded movie", labels)
        self.assertNotIn("Old radio station", labels)
        self.assertNotIn("Old radio metadata", labels)

    def test_secondary_page_mini_renders_cast_not_radio(self):
        status, snapshot = self.cast()
        with patch("landscape_dashboard._text") as render:
            draw_shell(
                self.surface, *self.fonts, "settings", "Old radio station",
                "Old radio metadata", True, False, "Tamil Bible",
                video_status=status, media_snapshot=snapshot,
            )
        labels = [call.args[2] for call in render.call_args_list]
        self.assertIn("Phone uploaded movie", labels)
        self.assertNotIn("Old radio station", labels)


if __name__ == "__main__":
    unittest.main()

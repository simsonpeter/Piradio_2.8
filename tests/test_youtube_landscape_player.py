"""Headless regression checks for the native 7-inch YouTube player.

Keeps the real radio and YouTube audio engines isolated: UI rendering and
hitboxes are validated without starting a VLC/MPV process on a CI machine.
"""
import ast
import os
from pathlib import Path
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

from landscape_pages import draw, hit, YOUTUBE_SEEK, YOUTUBE_ART


class YouTubeNativePlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.surface = pygame.Surface((800, 480))
        cls.font = pygame.font.Font(None, 28)
        cls.small = pygame.font.Font(None, 23)
        cls.tiny = pygame.font.Font(None, 19)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def render_player(self, *, active=True, paused=False, video=False,
                      artwork=None):
        self.surface.fill((0, 0, 0))
        draw(self.surface, "youtube", self.font, self.small, self.tiny,
             youtube_player_view=True,
             youtube_status={
                 "active": active,
                 "video": video,
                 "paused": paused,
                 "title": "Tamil Christian Song - New Tamil Praise Audio",
                 "uploader": "Tamil Christian Music",
                 "position_ms": 81000,
                 "length_ms": 224000,
             },
             video_available=True,
             youtube_artwork=artwork,
             youtube_results=[{"title": "Result 1", "id": "abcdefghijk"}],
        )

    def test_now_playing_has_live_control_targets(self):
        self.render_player()
        self.assertEqual(hit((685, 94)), ("yt", "search"))
        self.assertEqual(hit((210, 349)), ("yt", "video"))
        self.assertEqual(hit(YOUTUBE_ART.center), ("yt", "video"))
        self.assertEqual(hit((422, 347)), ("yt", "previous"))
        self.assertEqual(hit((490, 347)), ("yt", "back10"))
        self.assertEqual(hit((560, 347)), ("yt", "toggle"))
        self.assertEqual(hit((650, 347)), ("yt", "forward10"))
        self.assertEqual(hit((719, 347)), ("yt", "next"))
        self.assertEqual(hit(YOUTUBE_SEEK.center), ("yt", "seek"))

    def test_search_results_remain_reachable(self):
        self.surface.fill((0, 0, 0))
        draw(self.surface, "youtube", self.font, self.small, self.tiny,
             youtube_player_view=False,
             youtube_results=[{"title": "Results stay available", "id": "abcdefghijk"}],
             youtube_offset=0,
             youtube_status={"title": "Current YouTube track"},
             video_available=True)
        self.assertEqual(hit((690, 94)), ("yt", "player"))
        self.assertEqual(hit((215, 192)), (160, 266))

    def test_real_artwork_renders(self):
        picture = pygame.Surface((320, 180))
        picture.fill((219, 64, 38))
        self.render_player(artwork=picture)
        self.assertEqual(tuple(self.surface.get_at((210, 154))[:3]),
                         (219, 64, 38))

    def test_audio_and_video_and_paused_modes(self):
        for video, paused, active in [
            (False, False, True),
            (False, True, True),
            (True, False, True),
            (True, True, True),
            (False, False, False),
        ]:
            with self.subTest(video=video, paused=paused, active=active):
                self.render_player(video=video, paused=paused, active=active)
                self.assertEqual(hit((557, 346)), ("yt", "toggle"))

    def test_main_application_integration_and_radio_isolation(self):
        source = (Path(__file__).resolve().parents[1] /
                  "touch_radio.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = {n.name: n for n in tree.body
                     if isinstance(n, ast.FunctionDef)}
        for method in ("youtube_player_touch", "youtube_status_for_screen",
                       "queue_youtube_artwork", "play_youtube_station",
                       "switch_landscape_page", "stop_youtube_audio"):
            self.assertIn(method, functions)
        player_source = ast.get_source_segment(
            source, functions["play_youtube_station"])
        self.assertIn("youtube_player_view = True", player_source)
        self.assertNotIn("stations.append", player_source)
        self.assertIn("youtube_audio_player.play()", player_source)
        self.assertIn('target[0] == "yt"', source)
        self.assertIn('youtube_player_touch(target[1], event.pos)', source)
        self.assertIn("youtube_status=youtube_status_for_screen()", source)
        self.assertIn("youtube_artwork=youtube_artwork_surfaces.get(", source)
        self.assertIn('youtube_player_view = False', source)


if __name__ == "__main__":
    unittest.main()

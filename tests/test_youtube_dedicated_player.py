"""Headless native 800x480 YouTube Now Playing screen checks."""
import unittest
import pygame

from landscape_youtube_player import (
    draw, hit, PANEL, ART, BODY, BACK_TO_SEARCH, VIDEO_BUTTON,
    PREVIOUS, PAUSE, NEXT, STOP, TRACK, _time,
)


class DedicatedYouTubeScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def make_fonts(self):
        return (
            pygame.font.Font(None, 32),
            pygame.font.Font(None, 23),
            pygame.font.Font(None, 18),
        )

    def state(self, **kwargs):
        value = {
            "mode": "audio",
            "title": "Bayapadathey - Tamil Christian Song",
            "channel": "Tamil worship music",
            "playing": True,
            "paused": False,
            "position": 43,
            "duration": 215,
            "seekable": True,
            "video_available": True,
            "queue_total": 12,
            "queue_position": 3,
        }
        value.update(kwargs)
        return value

    def test_native_player_renders_800x480_without_covering_sidebar_or_mini(self):
        surface = pygame.Surface((800, 480))
        surface.fill((0, 0, 0))
        artwork = pygame.Surface((110, 110))
        artwork.fill((200, 200, 200))
        self.assertTrue(draw(surface, *self.make_fonts(), self.state(), artwork))
        self.assertEqual(tuple(surface.get_at((10, 90))[:3]), (0, 0, 0))
        self.assertEqual(tuple(surface.get_at((700, 430))[:3]), (0, 0, 0))
        self.assertNotEqual(tuple(surface.get_at(PANEL.center)[:3]), (0, 0, 0))

    def test_all_dedicated_buttons(self):
        state = self.state()
        buttons = (
            (BACK_TO_SEARCH, "search"),
            (VIDEO_BUTTON, "video"),
            (PREVIOUS, "prev"),
            (PAUSE, "pause"),
            (NEXT, "next"),
            (STOP, "stop"),
        )
        for rect, expected in buttons:
            with self.subTest(expected=expected):
                self.assertEqual(hit(rect.center, state)[0], expected)

    def test_timeline_absolute_seek(self):
        state = self.state()
        action = hit(TRACK.center, state)
        self.assertEqual(action[0], "seek")
        self.assertAlmostEqual(action[1], 107.5, delta=1)
        self.assertEqual(hit(TRACK.center, self.state(seekable=False))[0], "consume")

    def test_live_stream_without_duration_draws_and_does_not_seek(self):
        surface = pygame.Surface((800, 480))
        state = self.state(duration=0, position=0, seekable=False)
        self.assertTrue(draw(surface, *self.make_fonts(), state))
        self.assertNotEqual(hit(TRACK.center, state)[0], "seek")

    def test_video_mode_draws_and_uses_same_buttons(self):
        surface = pygame.Surface((800, 480))
        state = self.state(mode="video", paused=True, title="A full screen video")
        self.assertTrue(draw(surface, *self.make_fonts(), state))
        self.assertEqual(hit(VIDEO_BUTTON.center, state)[0], "video")
        self.assertEqual(hit(PAUSE.center, state)[0], "pause")

    def test_outside_panel_never_intercepts_sidebar_or_mini(self):
        self.assertIsNone(hit((75, 130), self.state()))
        self.assertIsNone(hit((500, 420), self.state()))
        self.assertEqual(_time(125), "2:05")
        self.assertEqual(_time(3601), "1:00:01")
        self.assertEqual(_time(-1), "--:--")


if __name__ == "__main__":
    unittest.main()

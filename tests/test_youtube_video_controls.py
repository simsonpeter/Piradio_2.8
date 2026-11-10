"""Headless checks for minimized YouTube/mpv controls and transport UI."""
import json
import unittest
from unittest.mock import patch

import pygame

from youtube_video_backend import YouTubeVideoBackend
from landscape_dashboard import (
    VIDEO_MINI, VIDEO_SEEK, VIDEO_BUTTONS, draw_video_mini, video_mini_hit,
)


class DummyProcess:
    def poll(self):
        return None


class FakeSocket:
    def __init__(self, response):
        self.response = response
        self.sent = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def settimeout(self, timeout):
        pass
    def connect(self, path):
        assert path == "/tmp/piradio-test-mpv.sock"
    def sendall(self, payload):
        self.sent.append(payload)
    def recv(self, maximum):
        chunk, self.response = self.response, b""
        return chunk


class VideoBackendTests(unittest.TestCase):
    def setUp(self):
        self.backend = YouTubeVideoBackend()
        self.backend.process = DummyProcess()
        self.backend.socket_path = "/tmp/piradio-test-mpv.sock"
        self.backend.title = "Phone-sent YouTube video"
        self.backend.video_id = "abcdefghijk"

    def _query(self, props):
        # Deliver out-of-order replies with an unrelated event between them.
        responses = [json.dumps({"event": "file-loaded"})]
        for id_, value in props.items():
            responses.append(json.dumps({
                "request_id": id_, "error": "success", "data": value,
            }))
        fake = FakeSocket(("\n".join(responses) + "\n").encode())
        with patch("youtube_video_backend.socket.socket", return_value=fake):
            status = self.backend.playback_status()
        self.assertEqual(len(fake.sent), 1)
        self.assertIn(b'"request_id": 4', fake.sent[0])
        return status

    def test_lua_minimize_is_detected(self):
        status = self._query({4: "no", 3: False, 1: 24, 2: 180, 5: True})
        self.assertTrue(status["playing"])
        self.assertTrue(status["minimized"])
        self.assertEqual(status["position"], 24)
        self.assertEqual(status["duration"], 180)
        self.assertEqual(status["title"], "Phone-sent YouTube video")
        self.assertTrue(self.backend.minimized)

    def test_restore_is_detected(self):
        self.backend.minimized = True
        status = self._query({4: 1, 5: False, 3: False, 2: 180, 1: 26})
        self.assertFalse(status["minimized"])
        self.assertFalse(self.backend.minimized)

    def test_paused_minimized_status(self):
        status = self._query({4: "no", 5: True, 3: True})
        self.assertTrue(status["paused"])
        self.assertTrue(status["minimized"])

    def test_video_metadata_is_cleared_on_stop(self):
        backend = YouTubeVideoBackend()
        backend.title = "Test"
        backend.video_id = "abcdefghijk"
        backend.stop()
        self.assertEqual(backend.title, "")
        self.assertIsNone(backend.video_id)


class VideoMiniTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def make_status(self):
        return {
            "playing": True,
            "minimized": True,
            "paused": False,
            "title": "Phone-sent mpv video",
            "position": 25,
            "duration": 150,
        }

    def test_minimized_video_draws_and_handles_all_controls(self):
        surface = pygame.Surface((800, 480))
        surface.fill((0, 0, 0))
        fonts = [
            pygame.font.Font(None, n) for n in (26, 21, 18)
        ]
        status = self.make_status()
        self.assertTrue(draw_video_mini(surface, *fonts, status))
        self.assertNotEqual(tuple(surface.get_at(VIDEO_MINI.center)[:3]), (0, 0, 0))
        for action, value, rect, label in VIDEO_BUTTONS:
            self.assertEqual(video_mini_hit(rect.center, status), (action, value))
        mid = (VIDEO_SEEK.centerx, VIDEO_SEEK.centery)
        target = video_mini_hit(mid, status)
        self.assertEqual(target[0], "seek")
        self.assertAlmostEqual(target[1], 75, delta=1)

    def test_tcradios_player_remains_dedicated_during_youtube_video(self):
        from landscape_dashboard import draw_dashboard
        surface = pygame.Surface((800, 480))
        font, small, tiny = (
            pygame.font.Font(None, 28),
            pygame.font.Font(None, 21),
            pygame.font.Font(None, 16),
        )
        status = self.make_status()
        # Even if a YouTube video is active elsewhere, the RADIO screen
        # must always render the last selected TCRADIOS station and artwork.
        with patch("landscape_dashboard._station_art") as station_art:
            self.assertTrue(draw_dashboard(
                surface, font, small, tiny,
                "radio", "TC Tamil Live", "Radio streaming",
                True, False, False, "Bible", 50,
                station_data={"name": "TC Tamil Live"},
                video_status=status,
            ))
            station_art.assert_called_once()

    def test_youtube_video_has_its_own_minimized_controls(self):
        from landscape_dashboard import VIDEO_MINI, VIDEO_SEEK
        status = self.make_status()
        action = video_mini_hit(VIDEO_SEEK.center, status)
        self.assertEqual(action[0], "seek")
        self.assertAlmostEqual(action[1], 75, delta=1)
        status["minimized"] = False
        self.assertIsNone(video_mini_hit(VIDEO_MINI.center, status))

    def test_home_page_and_secondary_shell_accept_video_source(self):
        from landscape_dashboard import draw_dashboard, draw_shell
        surface = pygame.Surface((800, 480))
        font, small, tiny = (
            pygame.font.Font(None, 28),
            pygame.font.Font(None, 21),
            pygame.font.Font(None, 16),
        )
        status = self.make_status()
        self.assertTrue(draw_dashboard(
            surface, font, small, tiny,
            "menu", "OLD RADIO", "Old metadata",
            False, False, False, "Bible", 50,
            video_status=status,
        ))
        draw_shell(
            surface, font, small, tiny,
            "youtube", "OLD RADIO", "Old metadata",
            False, False, "Bible", video_status=status,
        )

    def test_no_overlay_when_video_not_minimized(self):
        status = self.make_status()
        status["minimized"] = False
        surface = pygame.Surface((800, 480))
        self.assertFalse(draw_video_mini(surface,
            pygame.font.Font(None, 26),
            pygame.font.Font(None, 21),
            pygame.font.Font(None, 18), status))
        self.assertIsNone(video_mini_hit((520, 430), status))


if __name__ == "__main__":
    unittest.main()

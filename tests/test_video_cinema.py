"""Regression checks for PiRadio Cinema controls and phone remote."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from video_cinema import cinema_remote_state, validate_cinema_seek, validate_cinema_volume
from youtube_video_backend import YouTubeVideoBackend


class MockProcess:
    def poll(self):
        return None


class SocketReplies:
    def __init__(self, props):
        self.payload = (
            "\n".join(json.dumps({"request_id": key, "error": "success",
                                   "data": value}) for key, value in props.items())
            + "\n"
        ).encode()
        self.sent = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def settimeout(self, timeout):
        pass
    def connect(self, path):
        self.connected_to = path
    def sendall(self, data):
        self.sent.append(data)
    def recv(self, limit):
        payload, self.payload = self.payload, b""
        return payload


class CinemaControlsTests(unittest.TestCase):
    def state(self, **changes):
        result = {
            "playing": True, "source": "youtube_video",
            "position": 40, "duration": 200, "seekable": True,
            "title": "Video from phone", "paused": False,
        }
        result.update(changes)
        return result

    def test_absolute_seek_clamped_away_from_end(self):
        state = self.state()
        self.assertEqual(validate_cinema_seek("seek", -20, state), 0)
        self.assertAlmostEqual(
            validate_cinema_seek("seek", 5000, state), 199.75
        )
        self.assertEqual(validate_cinema_seek("seek", 96.5, state), 96.5)

    def test_relative_seek_is_bounded_to_media(self):
        state = self.state(position=193)
        self.assertAlmostEqual(validate_cinema_seek("seek_relative", 50, state), 6.75)
        self.assertEqual(validate_cinema_seek("seek_relative", -500, state), -193)
        self.assertEqual(validate_cinema_seek("seek_relative", 10, self.state()), 10)

    def test_never_seek_live_mirror_photo_or_unseekable_streams(self):
        for source in ("guest_photos", "screen_mirror"):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    validate_cinema_seek("seek", 20, self.state(source=source))
        for options in (
            {"duration": 0}, {"seekable": False}, {"playing": False},
            {"duration": float("nan")}, {"source": "unknown"},
        ):
            with self.subTest(options=options):
                with self.assertRaises(ValueError):
                    validate_cinema_seek("seek_relative", 10, self.state(**options))

    def test_seek_rejects_malformed_and_infinite_values(self):
        for bad in (float("nan"), float("inf"), "-Infinity", "bad", True, None):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    validate_cinema_seek("seek", bad, self.state())
        with self.assertRaises(ValueError):
            validate_cinema_seek("delete", 1, self.state())

    def test_remote_state_preserves_title_and_paused_video(self):
        remote = cinema_remote_state(self.state(
            paused=True, minimized=True, buffering=False,
            source="guest_video",
        ))
        self.assertEqual(remote["title"], "Video from phone")
        self.assertTrue(remote["seekable"])
        self.assertTrue(remote["paused"])
        self.assertTrue(remote["minimized"])

    def test_remote_state_does_not_invent_stream_duration(self):
        remote = cinema_remote_state(self.state(
            source="screen_mirror", duration=0, position=15,
            seekable=True, buffering=True,
        ))
        self.assertFalse(remote["seekable"])
        self.assertTrue(remote["buffering"])
        self.assertEqual(remote["position"], 15)
        stopped = cinema_remote_state(self.state(playing=False, buffering=True))
        self.assertFalse(stopped["seekable"])
        self.assertFalse(stopped["buffering"])

    def test_mpv_ipc_reports_seekable_and_buffering(self):
        backend = YouTubeVideoBackend()
        backend.process = MockProcess()
        backend.socket_path = "/tmp/piradio-cinema-test.sock"
        backend.title = "PiRadio video"
        fake = SocketReplies({
            1: 31, 2: 240, 3: False, 4: 1, 5: False,
            6: True, 7: True,
        })
        with patch("youtube_video_backend.socket.socket", return_value=fake):
            state = backend.playback_status()
        self.assertTrue(state["seekable"])
        self.assertTrue(state["buffering"])
        self.assertEqual(state["duration"], 240)
        self.assertIn(b'"request_id": 6', fake.sent[0])
        self.assertIn(b'"request_id": 7', fake.sent[0])

    def test_mpv_status_conservatively_disables_unconfirmed_seek(self):
        backend = YouTubeVideoBackend()
        backend.process = MockProcess()
        backend.socket_path = "/tmp/piradio-cinema-test.sock"
        fake = SocketReplies({1: 12, 2: 180, 3: False, 4: 1, 5: False})
        with patch("youtube_video_backend.socket.socket", return_value=fake):
            state = backend.playback_status()
        self.assertFalse(state["seekable"])
        self.assertFalse(state["buffering"])

    def test_mpv_does_not_allow_photo_timeline(self):
        backend = YouTubeVideoBackend()
        backend.process = MockProcess()
        backend.socket_path = "/tmp/piradio-cinema-test.sock"
        backend.source_type = "guest_photos"
        fake = SocketReplies({1: 12, 2: 180, 6: True})
        with patch("youtube_video_backend.socket.socket", return_value=fake):
            state = backend.playback_status()
        self.assertFalse(state["seekable"])

    def test_phone_remote_has_real_title_and_source_specific_controls(self):
        app = Path("touch_radio.py").read_text(encoding="utf-8")
        for marker in (
            'id="pi-video-title"', 'id="pi-video-source"',
            'id="pi-video-seek"', 'id="pi-video-state"',
            "piVideoSkip(seconds)", "piVideoSeekCommit(value)",
            "piVideoSeekable=!!data.seekable",
            "piVideoSource==='guest_photos'",
            "cinema_remote_state(youtube_video.playback_status())",
            "validate_cinema_seek(",
            "@app.route('/api/youtube/video/status')",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, app)

    def test_cinema_volume_accepts_only_integer_percent(self):
        for level in (0, 1, 5, 50, 99, 100):
            with self.subTest(level=level):
                self.assertEqual(validate_cinema_volume(level), level)
        for invalid in (None, True, False, "50", -1, 101, 10.5,
                        float("nan"), float("inf"), {}, []):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_cinema_volume(invalid)

    def test_legacy_cinema_has_volume_slider_and_increment_buttons(self):
        source = Path("touch_radio.py").read_text(encoding="utf-8")
        for marker in (
            'id="pi-video-volume"',
            'id="pi-video-volume-label"',
            'id="pi-video-volume-up"',
            'id="pi-video-volume-down"',
            'piVideoSetVolume(value)',
            'piVideoVolumeCommit(value)',
            'piVideoAdjustVolume(delta)',
            "validate_cinema_volume(data.get('level'))",
            '"volume": vol_level',
            'apply_live_volume(new_volume)',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_remote_keeps_previous_browser_endpoints(self):
        app = Path("touch_radio.py").read_text(encoding="utf-8")
        self.assertIn("@app.route('/api/youtube/video', methods=['POST'])", app)
        self.assertIn("@app.route('/api/nowplaying')", app)
        self.assertIn("@app.route('/api/status')", app)
        self.assertIn('control_active_media(transport_action, seek_time, mpv_only=True)', app)


if __name__ == "__main__":
    unittest.main()

"""Unit checks for cross-source PiRadio 7 playback command routing."""
import unittest

from media_transport import TransportPlan, plan_media_command


class MediaTransportTests(unittest.TestCase):
    def plan(self, source, action, seconds=None, *, seekable=False):
        return plan_media_command(source, action, seconds, seekable=seekable)

    def test_mpv_pause_and_controls(self):
        self.assertEqual(self.plan("youtube_video", "toggle"),
                         TransportPlan("mpv", "pause"))
        self.assertEqual(self.plan("guest_video", "next"),
                         TransportPlan("mpv", "seek_relative", 10))
        self.assertEqual(self.plan("guest_audio", "prev"),
                         TransportPlan("mpv", "seek_relative", -10))
        self.assertEqual(self.plan("youtube_video", "stop"),
                         TransportPlan("mpv", "stop"))
        self.assertEqual(self.plan("youtube_video", "minimize"),
                         TransportPlan("mpv", "minimize"))
        self.assertEqual(self.plan("youtube_video", "restore"),
                         TransportPlan("mpv", "restore"))

    def test_photo_playlist_navigation_not_timestamp_seek(self):
        self.assertEqual(self.plan("guest_photos", "next"),
                         TransportPlan("mpv", "playlist_next"))
        self.assertEqual(self.plan("guest_photos", "prev"),
                         TransportPlan("mpv", "playlist_prev"))
        self.assertIsNone(self.plan("guest_photos", "seek", 30, seekable=True))

    def test_no_fake_seek_for_screen_mirror(self):
        for action in ("next", "prev", "seek", "seek_relative"):
            with self.subTest(action=action):
                self.assertIsNone(self.plan("screen_mirror", action, 15,
                                            seekable=True))
        self.assertEqual(self.plan("screen_mirror", "toggle"),
                         TransportPlan("mpv", "pause"))

    def test_bible_shift_and_pause(self):
        self.assertEqual(self.plan("bible", "next"),
                         TransportPlan("bible", "chapter_shift", 1))
        self.assertEqual(self.plan("bible", "prev"),
                         TransportPlan("bible", "chapter_shift", -1))
        self.assertEqual(self.plan("bible", "toggle"),
                         TransportPlan("bible", "toggle"))
        self.assertEqual(self.plan("bible", "stop"),
                         TransportPlan("bible", "stop"))

    def test_radio_station_switching(self):
        self.assertEqual(self.plan("radio", "next"),
                         TransportPlan("vlc", "next", 1))
        self.assertEqual(self.plan("radio", "prev"),
                         TransportPlan("vlc", "next", -1))
        self.assertEqual(self.plan("radio", "toggle"),
                         TransportPlan("vlc", "toggle"))
        self.assertIsNone(self.plan("radio", "seek", 34, seekable=True))

    def test_youtube_audio_timeline_when_seekable(self):
        self.assertIsNone(self.plan("youtube_audio", "seek", 15))
        self.assertEqual(self.plan("youtube_audio", "seek", 15, seekable=True),
                         TransportPlan("vlc", "seek", 15))
        self.assertEqual(self.plan("youtube_audio", "next"),
                         TransportPlan("vlc", "next", 1))

    def test_mpv_seek_validation(self):
        self.assertIsNone(self.plan("youtube_video", "seek", 15,
                                    seekable=False))
        self.assertEqual(self.plan("youtube_video", "seek", 15,
                                   seekable=True),
                         TransportPlan("mpv", "seek", 15))
        self.assertEqual(self.plan("youtube_video", "seek_relative", -10),
                         TransportPlan("mpv", "seek_relative", -10))
        for bad in (float("nan"), float("inf"), "n/a", True):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    self.plan("youtube_video", "seek", bad, seekable=True)
        with self.assertRaises(ValueError):
            self.plan("youtube_video", "seek", -1, seekable=True)

    def test_unsupported_controls_are_ignored(self):
        self.assertIsNone(self.plan("bible", "minimize"))
        self.assertIsNone(self.plan("radio", "restore"))
        self.assertIsNone(self.plan("unknown", "toggle"))
        self.assertIsNone(self.plan("youtube_video", "reboot"))
        self.assertIsNone(self.plan("guest_photos", "seek_relative", 20))


if __name__ == "__main__":
    unittest.main()

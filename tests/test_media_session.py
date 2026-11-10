"""Device-independent regression tests for PiRadio's universal media state."""
import unittest

from media_session import resolve_media_snapshot


class MediaSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.radio = {
            "vlc_state": "playing",
            "vlc_source": "radio",
            "vlc_title": "Old radio station",
            "volume": 65,
            "station": 3,
        }

    def test_radio_legacy_status_is_preserved(self):
        info = resolve_media_snapshot(**self.radio).as_dict()
        self.assertEqual(info["source"], "radio")
        self.assertEqual(info["title"], "Old radio station")
        self.assertTrue(info["playing"])
        self.assertFalse(info["paused"])
        self.assertEqual(info["volume"], 65)
        self.assertEqual(info["station"], 3)

    def test_cast_media_preempts_stale_radio_metadata(self):
        info = resolve_media_snapshot(
            **self.radio,
            video_status={
                "playing": True,
                "source": "guest_video",
                "title": "Phone uploaded video",
                "position": 48,
                "duration": 180,
                "paused": False,
                "minimized": True,
            },
        ).as_dict()
        self.assertEqual(info["source"], "guest_video")
        self.assertEqual(info["title"], "Phone uploaded video")
        self.assertEqual(info["position"], 48)
        self.assertEqual(info["duration"], 180)
        self.assertTrue(info["minimized"])
        self.assertTrue(info["seekable"])

    def test_paused_mpv_still_owns_the_session(self):
        info = resolve_media_snapshot(
            **self.radio,
            bible_active=True,
            bible_title="Tamil Bible",
            video_status={"playing": True, "paused": True, "source": "youtube_video",
                          "title": "Paused video"},
        )
        self.assertEqual(info.source, "youtube_video")
        self.assertFalse(info.playing)
        self.assertTrue(info.paused)

    def test_stopped_mpv_falls_back_to_bible(self):
        info = resolve_media_snapshot(
            **self.radio,
            bible_active=True,
            bible_paused=True,
            bible_title="Tamil Bible - Chapter 2",
            video_status={"playing": False, "title": "Stale video"},
        )
        self.assertEqual(info.source, "bible")
        self.assertEqual(info.title, "Tamil Bible - Chapter 2")
        self.assertTrue(info.paused)

    def test_bible_playing_preempts_old_radio(self):
        info = resolve_media_snapshot(
            **self.radio, bible_active=True, bible_title="Genesis chapter 1",
        )
        self.assertEqual(info.source, "bible")
        self.assertTrue(info.playing)

    def test_youtube_audio_uses_vlc_without_becoming_video(self):
        info = resolve_media_snapshot(
            vlc_state="paused", vlc_source="youtube_audio",
            vlc_title="Tamil song", vlc_position=55, vlc_duration=240,
            vlc_seekable=True,
        )
        self.assertEqual(info.source, "youtube_audio")
        self.assertFalse(info.playing)
        self.assertTrue(info.paused)
        self.assertEqual(info.duration, 240)
        self.assertTrue(info.seekable)

    def test_live_stream_has_no_fake_seekbar(self):
        info = resolve_media_snapshot(
            video_status={"playing": True, "source": "screen_mirror",
                          "duration": None, "position": None},
        )
        self.assertEqual(info.source, "screen_mirror")
        self.assertFalse(info.seekable)
        self.assertEqual(info.duration, 0)

    def test_invalid_time_and_volume_are_sanitized(self):
        info = resolve_media_snapshot(
            vlc_state="playing", vlc_position=float("nan"),
            vlc_duration=float("inf"), vlc_seekable=True,
            volume=130, station=-9,
        )
        self.assertEqual(info.position, 0)
        self.assertEqual(info.duration, 0)
        self.assertFalse(info.seekable)
        self.assertEqual(info.volume, 100)
        self.assertEqual(info.station, 0)

    def test_bible_does_not_consume_stale_video_without_process(self):
        info = resolve_media_snapshot(
            **self.radio,
            video_status={"playing": False, "source": "guest_audio"},
        )
        self.assertEqual(info.source, "radio")


if __name__ == "__main__":
    unittest.main()

"""PIN-protected guest casting tests; no Raspberry Pi hardware needed."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from flask import Flask
from piradio_guest_cast import (
    GuestCastSession, media_kind, youtube_id_from_url, validate_rtsp,
    photo_signature, register_cast_routes,
)


class GuestCastTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.clock = [1000.0]
        self.session = GuestCastSession(
            Path(self.temp.name), time_fn=lambda: self.clock[0],
        )
        self.backend = MagicMock()
        self.backend.is_playing.return_value = True
        self.backend.start_local.return_value = True
        self.backend.pause.return_value = True
        self.backend.seek.return_value = True
        self.backend.seek_absolute.return_value = True
        self.backend.volume.return_value = True
        self.backend.playback_status.return_value = {
            "playing": True, "position": 22.0, "duration": 120.0,
            "paused": False, "source": "guest_video", "title": "Holiday movie",
            "minimized": False,
        }
        self.backend.source_type = "guest_video"
        self.backend.title = "Guest media"
        self.app = Flask(__name__)
        self.vol = [50]
        self.stop_audio = MagicMock()
        register_cast_routes(
            self.app, self.session, lambda: self.backend, self.stop_audio,
            lambda: "192.168.1.25", lambda: self.vol[0],
            lambda v: self.vol.__setitem__(0, v),
        )
        self.client = self.app.test_client()
        self.token = None

    def tearDown(self):
        self.temp.cleanup()

    def auth(self):
        return {"Authorization": "Bearer " + (self.token or "")}

    def pair(self):
        pin = self.session.open()["pin"]
        resp = self.client.post("/api/cast/pair", json={"pin": pin})
        self.assertEqual(resp.status_code, 200)
        self.token = resp.json["token"]
        return self.token

    def test_pairing_is_off_until_opened_on_pi(self):
        self.assertFalse(self.client.get("/api/cast/public").json["pairing_open"])
        res = self.client.post("/api/cast/pair", json={"pin": "123456"})
        self.assertEqual(res.status_code, 403)
        self.assertEqual(self.client.post("/api/cast/control",
            json={"action": "pause"}).status_code, 401)
        self.assertEqual(self.client.post("/api/cast/upload").status_code, 401)
        self.assertEqual(self.client.post("/api/cast/youtube").status_code, 401)
        self.assertEqual(self.client.post("/api/cast/mirror").status_code, 401)

    def test_pin_rate_limit_expiry_and_session_revocation(self):
        pin = self.session.open()["pin"]
        for _ in range(8):
            self.assertEqual(self.client.post("/api/cast/pair",
                json={"pin": "ABCDEF"}).status_code, 403)
        self.assertIn("Too many", self.client.post("/api/cast/pair",
            json={"pin": pin}).json["error"])
        self.clock[0] += 301
        self.pair()
        self.assertEqual(self.client.get("/api/cast/status",
            headers=self.auth()).status_code, 200)
        self.clock[0] += 3601
        self.assertEqual(self.client.get("/api/cast/status",
            headers=self.auth()).status_code, 401)
        self.pair()
        self.session.close()
        self.assertEqual(self.client.get("/api/cast/status",
            headers=self.auth()).status_code, 401)

    def test_media_type_validations(self):
        self.assertEqual(media_kind("holiday.MP4"), "video")
        self.assertEqual(media_kind("music.mp3"), "audio")
        self.assertEqual(media_kind("portrait.jpeg"), "photos")
        self.assertIsNone(media_kind("notes.exe"))
        self.assertTrue(photo_signature("holiday.jpg", b"\xff\xd8\xffJPEG"))
        self.assertFalse(photo_signature("holiday.jpg", b"malware"))
        self.assertTrue(photo_signature("photo.webp", b"RIFF1234WEBPdata"))

    def test_youtube_host_restrictions(self):
        self.assertEqual(youtube_id_from_url(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(youtube_id_from_url(
            "https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(youtube_id_from_url(
            "https://m.youtube.com/shorts/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        for url in ("http://youtu.be/dQw4w9WgXcQ",
                    "https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ",
                    "file:///etc/passwd",
                    "https://youtu.be/invalid"):
            self.assertIsNone(youtube_id_from_url(url), url)

    def test_rtsp_is_lan_only(self):
        self.assertEqual(validate_rtsp(
            "rtsp://192.168.1.50:8554/live", "192.168.1.25"),
            "rtsp://192.168.1.50:8554/live")
        for url in ("rtsp://127.0.0.1:8554/stream",
                    "rtsp://8.8.8.8:8554/live",
                    "rtsp://192.168.2.50:8554/live",
                    "rtsp://192.168.1.50:22/live",
                    "rtsp://user:pass@192.168.1.50:8554/live",
                    "rtsp://pi.local:8554/live"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_rtsp(url, "192.168.1.25")

    def test_upload_photo_and_gallery(self):
        self.pair()
        form = {
            "files": [
                (io.BytesIO(b"\xff\xd8\xff" + b"a"*16), "first.jpg"),
                (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"a"*16), "second.png"),
            ],
        }
        response = self.client.post("/api/cast/upload", data=form,
            headers=self.auth(), content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json["kind"], "photos")
        self.assertEqual(response.json["count"], 2)
        self.assertEqual(self.backend.start_local.call_args.args[1], "photos")
        self.assertEqual(len(self.session.current_files), 2)
        self.assertTrue(all(Path(p).exists() for p in self.session.current_files))
        self.assertTrue(self.stop_audio.called)

    def test_reject_upload_of_disallowed_type(self):
        self.pair()
        response = self.client.post("/api/cast/upload",
            data={"files": (io.BytesIO(b"not media"), "app.exe")},
            headers=self.auth(), content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)
        self.backend.start_local.assert_not_called()

    def test_video_audio_and_mirror_controls(self):
        self.pair()
        self.assertEqual(self.client.post("/api/cast/youtube",
            json={"url": "https://youtu.be/dQw4w9WgXcQ"},
            headers=self.auth()).status_code, 200)
        self.backend.start_youtube.assert_called_once()
        self.assertEqual(self.client.post("/api/cast/mirror",
            json={"url": "rtsp://192.168.1.77:8554/live"},
            headers=self.auth()).status_code, 200)
        self.backend.start_network_stream.assert_called_once()
        for action in ("pause", "restore", "seek_relative", "seek", "volume"):
            payload = {"action": action, "seconds": 10, "value": 65}
            response = self.client.post("/api/cast/control", json=payload,
                headers=self.auth())
            self.assertEqual(response.status_code, 200, (action, response.json))
        self.assertEqual(self.vol[0], 65)
        response = self.client.post("/api/cast/control",
            json={"action": "seek", "seconds": "NaN"}, headers=self.auth())
        self.assertEqual(response.status_code, 400)
        self.client.post("/api/cast/control", json={"action": "stop"},
            headers=self.auth())
        self.backend.stop.assert_called_once()

    def test_portal_is_independent_of_piradio_remote(self):
        response = self.client.get("/cast")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"PiRadio Cast", response.data)
        self.assertIn(b'Send selected files', response.data)
        self.assertIn(b'Android screen mirror', response.data)
        self.assertEqual(response.headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()

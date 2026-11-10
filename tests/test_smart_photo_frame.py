"""Smart Photo Frame backend/UI regression tests for Raspberry Pi 7-inch."""
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from flask import Flask
from PIL import Image
import pygame

from smart_photo_frame import (
    PhotoFrameLibrary, PhotoFrameRenderer, register_frame_routes,
    PHOTO_CLOSE, PHOTO_NEXT, PHOTO_PAUSE, PHOTO_ADD, _image_header,
)


def png_bytes(color=(72, 182, 218), size=(40, 25)):
    image = Image.new("RGB", size, color)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class FrameTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.timestamp = [1000]
        self.library = PhotoFrameLibrary(
            root=Path(self.temp.name)/"gallery",
            settings_path=Path(self.temp.name)/"options.json",
            clock=lambda: self.timestamp[0],
        )
        self.app = Flask(__name__)
        register_frame_routes(self.app, self.library)
        self.client = self.app.test_client()
        self.token = ""

    def tearDown(self):
        self.temp.cleanup()

    def authorize(self):
        return {"Authorization": "Bearer " + self.token}

    def pair(self):
        pin = self.library.start_pairing()["pin"]
        resp = self.client.post("/api/frame/pair", json={"pin": pin})
        self.assertEqual(resp.status_code, 200)
        self.token = resp.json["token"]

    def test_photo_upload_rejects_unauthenticated_requests(self):
        resp = self.client.post(
            "/api/frame/upload",
            data={"photos": (BytesIO(png_bytes()), "family.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 401)
        self.assertFalse(self.library.list_photos())
        self.assertFalse(self.client.post("/api/frame/options",
            json={"auto_idle": True}).status_code == 200)

    def test_pairing_requires_physical_screen_pin_and_token_expires(self):
        self.assertEqual(self.client.post("/api/frame/pair",json={"pin":"000000"}).status_code,403)
        self.pair()
        self.assertEqual(self.client.get("/api/frame/status",headers=self.authorize()).status_code,200)
        self.timestamp[0] += 3601
        self.assertEqual(self.client.get("/api/frame/status",headers=self.authorize()).status_code,401)
        self.library.start_pairing()
        self.assertEqual(self.client.get("/api/frame/status",headers=self.authorize()).status_code,401)

    def test_safe_png_upload_and_settings(self):
        self.pair()
        request_data={
            "photos": [
                (BytesIO(png_bytes()), "family.png"),
                (BytesIO(png_bytes(color=(40, 40, 40))), "holiday.png"),
            ]
        }
        response=self.client.post("/api/frame/upload",data=request_data,
            headers=self.authorize(),content_type="multipart/form-data")
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(response.json["total"],2)
        self.assertEqual(len(self.library.list_photos()),2)
        self.assertEqual(self.library.consume_commands(),["refresh"])
        settings={"interval":12,"shuffle":False,"fit":"contain",
                  "clock":True,"weather":False,"auto_idle":True}
        response=self.client.post("/api/frame/options",json=settings,headers=self.authorize())
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(response.json["settings"],settings)
        reloaded=PhotoFrameLibrary(root=self.library.root,
            settings_path=self.library.settings_path)
        self.assertEqual(reloaded.options,settings)

    def test_reject_fake_image_file_and_unsafe_extensions(self):
        self.pair()
        for name,payload in (
            ("attack.png",b"not a valid image"),
            ("program.exe",b"garbage"),
            ("broken.jpg",b"\xff\xd8\xffjunk"),
        ):
            response=self.client.post("/api/frame/upload",data={
                "photos":(BytesIO(payload),name),
            },headers=self.authorize(),content_type="multipart/form-data")
            self.assertEqual(response.status_code,400,(name,response.json))
        self.assertEqual(self.library.list_photos(),[])

    def test_invalid_settings_and_controls_are_rejected(self):
        self.pair()
        for settings in ({"fit":"../../etc/"},{"interval":1},
                         {"interval":"5"},{"auto_idle":"true"},
                         {"unknown":True}):
            response=self.client.post("/api/frame/options",json=settings,headers=self.authorize())
            self.assertEqual(response.status_code,400,(settings,response.json))
        response=self.client.post("/api/frame/control",
            json={"action":"delete_everything"},headers=self.authorize())
        self.assertEqual(response.status_code,400)
        response=self.client.post("/api/frame/control",
            json={"action":"next"},headers=self.authorize())
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.library.consume_commands(),["next"])

    def test_rate_limit_and_close(self):
        self.library.start_pairing()
        for _ in range(8):
            self.assertEqual(self.client.post("/api/frame/pair",
                json={"pin":"abcdef"}).status_code,403)
        self.assertIn("Too many",self.client.post("/api/frame/pair",
            json={"pin":"999999"}).json["error"])
        self.timestamp[0] += 301
        self.pair()
        self.library.close_pairing()
        self.assertEqual(self.client.get("/api/frame/status",
            headers=self.authorize()).status_code,401)

    def test_phone_html_has_upload_and_settings(self):
        response=self.client.get("/frame")
        self.assertEqual(response.status_code,200)
        self.assertIn(b"Add photos to frame",response.data)
        self.assertIn(b"Use as idle screensaver",response.data)
        self.assertEqual(response.headers["Cache-Control"],"no-store")


class FrameRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.library=PhotoFrameLibrary(
            root=Path(self.temp.name)/"gallery",
            settings_path=Path(self.temp.name)/"settings.json",
        )
        self.renderer=PhotoFrameRenderer(self.library)
        self.photo=self.library.root/"landscape.png"
        self.photo.write_bytes(png_bytes(size=(600,400)))
        self.renderer.refresh(now=2000)
        self.renderer.activate(now=2000)
        self.fonts=tuple(pygame.font.Font(None,n) for n in (32,24,18))
        self.screen=pygame.Surface((800,480))

    def tearDown(self):
        self.temp.cleanup()

    def test_800x480_photo_and_pairing_screen(self):
        self.assertEqual(self.screen.get_size(),(800,480))
        self.renderer.show_pairing=True
        self.renderer.draw(self.screen,*self.fonts,
            now=2000.1,city="Antwerp",temperature=18,
            playing="Radio",url="http://192.168.1.25:8080/frame")
        self.assertNotEqual(self.screen.get_at((158,160))[:3],(0,0,0))
        self.assertEqual(self.renderer.hit(PHOTO_CLOSE.center,2000.1),"close")

    def test_pause_next_and_fit_tap_handling(self):
        self.renderer.show_pairing=False
        self.renderer.controls_until=2009
        self.assertEqual(self.renderer.hit(PHOTO_NEXT.center,2000),"consume")
        self.assertEqual(self.renderer.hit(PHOTO_PAUSE.center,2000),"consume")
        self.assertTrue(self.renderer.paused)
        self.assertEqual(self.renderer.hit(PHOTO_ADD.center,2000),"consume")
        self.assertTrue(self.renderer.show_pairing)

    def test_idle_does_not_show_controls(self):
        self.renderer.show_pairing=False
        # Render with a test-loaded photo, never depend on thread timing.
        self.renderer.path=self.photo
        self.renderer.image=pygame.Surface((800,480))
        self.renderer.image.fill((72,182,218))
        self.renderer.controls_until=2009
        self.renderer.draw(self.screen,*self.fonts,
                           now=2000,city="Antwerp",temperature=18,
                           ambient=True)
        self.assertEqual(self.screen.get_at((430,427))[:3],(72,182,218))

    def test_existing_audio_is_not_controlled_by_frame_renderer(self):
        self.renderer.draw(self.screen,*self.fonts,now=2000)
        # PhotoFrameRenderer has no VLC/MPV ownership.
        self.assertFalse(hasattr(self.renderer,"player"))
        self.assertFalse(hasattr(self.renderer,"stop_audio"))


if __name__=="__main__":
    unittest.main()

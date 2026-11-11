"""Photo Frame Pro: albums, privacy and crossfade regression tests."""
from io import BytesIO
from pathlib import Path
import tempfile
import unittest

from flask import Flask
from PIL import Image
from smart_photo_frame import PhotoFrameLibrary, register_frame_routes, TRANSITIONS


def picture(color=(90, 150, 100)):
    with BytesIO() as temp:
        Image.new("RGB", (30, 20), color).save(temp, format="PNG")
        return temp.getvalue()


class AlbumsTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        base=Path(self.folder.name)
        self.library=PhotoFrameLibrary(root=base/"gallery",settings_path=base/"options.json")
        app=Flask(__name__)
        register_frame_routes(app,self.library)
        self.client=app.test_client()
        self.token=None

    def auth(self):
        return {"Authorization": "Bearer "+self.token}

    def pair(self):
        pin=self.library.start_pairing()["pin"]
        self.token=self.client.post("/api/frame/pair",json={"pin":pin}).json["token"]

    def upload(self,name,color=(90,150,100)):
        return self.client.post(
            "/api/frame/upload",
            data={"photos":(BytesIO(picture(color)),name)},
            headers=self.auth(),content_type="multipart/form-data",
        )

    def test_old_gallery_stays_intact_during_album_changes(self):
        self.pair()
        self.assertEqual(self.upload("old.png").status_code,200)
        old=self.library.list_photos()[0]
        self.assertEqual(old.parent,self.library.root)
        result=self.client.post("/api/frame/albums",headers=self.auth(),
            json={"action":"create","name":"Christmas 2026"})
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(result.json["album"],"Christmas 2026")
        self.assertEqual(self.upload("new.png",(12,38,56)).status_code,200)
        selected=self.library.list_photos()
        self.assertEqual(len(selected),1)
        self.assertEqual(selected[0].parent.name,"Christmas 2026")
        self.assertEqual(len(self.library.all_photos()),2)
        self.assertTrue(old.is_file())
        r=self.client.post("/api/frame/albums",headers=self.auth(),
            json={"action":"select","album":"All Photos"})
        self.assertEqual(r.json["photos"],2)
        self.assertEqual(len(self.library.list_photos()),2)
        restored=PhotoFrameLibrary(root=self.library.root,
                                   settings_path=self.library.settings_path)
        self.assertEqual(restored.active_album,"All Photos")

    def test_album_creation_and_transition_are_pin_protected(self):
        self.assertEqual(self.client.post("/api/frame/albums",
            json={"action":"create","name":"Family"}).status_code,401)
        self.pair()
        result=self.client.post("/api/frame/albums",headers=self.auth(),
            json={"action":"create","name":"Family"})
        self.assertEqual(result.json["album"],"Family")
        self.assertEqual(self.library.consume_commands(),["refresh"])
        t=self.client.post("/api/frame/albums",headers=self.auth(),
            json={"action":"transition","style":"slow_fade"})
        self.assertEqual(t.status_code,200)
        self.assertEqual(self.library.transition,"slow_fade")
        self.assertEqual(TRANSITIONS["slow_fade"],1.5)
        persisted=PhotoFrameLibrary(root=self.library.root,
                                    settings_path=self.library.settings_path)
        self.assertEqual(persisted.transition,"slow_fade")
        self.assertEqual(persisted.active_album,"Family")
        status=self.client.get("/api/frame/status",headers=self.auth()).json
        self.assertEqual(status["transition"],"slow_fade")
        self.assertIn("Family",status["albums"])

    def test_reject_path_traversal_symlinks_and_unsupported_transitions(self):
        self.pair()
        for name in ("../outside","something/else",".hidden","X"*26,"All Photos","école"):
            result=self.client.post("/api/frame/albums",headers=self.auth(),
                json={"action":"create","name":name})
            self.assertEqual(result.status_code,400,(name,result.json))
        for bad in ("unsupported",None,False,"../../outside"):
            result=self.client.post("/api/frame/albums",headers=self.auth(),
                json={"action":"transition","style":bad})
            self.assertEqual(result.status_code,400)
        outside=Path(self.folder.name)/"outside"
        outside.mkdir()
        (self.library.root/"Danger").symlink_to(outside,target_is_directory=True)
        result=self.client.post("/api/frame/albums",headers=self.auth(),
            json={"action":"create","name":"Danger"})
        self.assertEqual(result.status_code,400)
        self.assertEqual(self.library.list_albums(),["All Photos"])
        result=self.client.post("/api/frame/albums",headers=self.auth(),
            json={"action":"select","album":"Danger"})
        self.assertEqual(result.status_code,400)

    def test_existing_options_and_media_engine_unchanged(self):
        self.pair()
        settings={"interval":12,"shuffle":False,"fit":"contain",
                  "clock":True,"weather":False,"auto_idle":True}
        result=self.client.post("/api/frame/options",
            json=settings,headers=self.auth())
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json["settings"],settings)
        code=Path("smart_photo_frame.py").read_text()
        self.assertIn("/api/frame/albums",code)
        self.assertNotIn("player.stop(",code)
        self.assertNotIn("youtube_video.stop(",code)

    def test_new_phone_ui_exposes_safe_album_form_and_transitions(self):
        response=self.client.get("/frame")
        self.assertEqual(response.status_code,200)
        for marker in (b'id="album-select"',b'id="album-create"',
                       b'id="album-new"',b'id="transition"',
                       b'async function albumCommand(',b"/api/frame/albums"):
            self.assertIn(marker,response.data)


if __name__ == "__main__":
    unittest.main()

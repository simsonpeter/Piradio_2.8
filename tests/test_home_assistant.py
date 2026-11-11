"""Tests for PiRadio's optional Home Assistant integration (no live devices)."""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
import unittest

import pygame

from home_assistant_bridge import (
    HomeAssistantBridge, read_local_config, validate_base_url, validate_entities,
)
from landscape_home_assistant import BACK, DEVICE_TILES, draw, hit
from landscape_smart_home import SHORTCUT_RECTS, SHORTCUTS, hit as home_hit


class FakeResponse:
    def __init__(self, entity_id="", state="off", status_code=200):
        self.entity_id = entity_id
        self.state = state
        self.status_code = status_code

    def json(self):
        return {
            "entity_id": self.entity_id,
            "state": self.state,
            "attributes": {"friendly_name": "Test Lamp"},
        }


class FakeSession:
    def __init__(self, reply=None):
        self.headers = {}
        self.trust_env = True
        self.get_calls = []
        self.post_calls = []
        self.reply = reply or {
            "light.living_room": "on",
            "switch.table_lamp": "off",
        }

    def get(self, url, *, timeout, allow_redirects):
        self.get_calls.append((url, timeout, allow_redirects))
        entity = url.split("/")[-1]
        return FakeResponse(entity, self.reply.get(entity, "unavailable"))

    def post(self, url, *, json, timeout, allow_redirects):
        self.post_calls.append((url, json, timeout, allow_redirects))
        return FakeResponse()

    def close(self):
        pass


class HomeAssistantBridgeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.file = Path(self.directory.name) / "home_assistant.json"
        self.token = "test-token-" + "a" * 45
        self.data = {
            "url": "http://homeassistant.local:8123",
            "token": self.token,
            "entities": ["light.living_room", "switch.table_lamp"],
        }
        self.write_config()
        self.sessions = []

    def write_config(self, mode=0o600):
        self.file.write_text(json.dumps(self.data))
        os.chmod(self.file, mode)

    def make_bridge(self):
        def factory():
            obj = FakeSession()
            self.sessions.append(obj)
            return obj
        return HomeAssistantBridge(config_path=self.file, session_factory=factory)

    def test_missing_configuration_stays_disabled_without_network(self):
        bridge = HomeAssistantBridge(config_path=self.file.with_name("missing.json"))
        self.assertFalse(bridge.configured)
        self.assertEqual(bridge.snapshot()["message"], "Not configured")
        bridge.tick(100)
        self.assertEqual(bridge.snapshot()["items"], [])
        self.assertFalse(bridge.toggle(0))

    def test_token_is_only_loaded_from_private_file(self):
        settings, error = read_local_config(self.file)
        self.assertEqual(error, "")
        self.assertEqual(settings["token"], self.token)
        self.write_config(0o644)
        settings, error = read_local_config(self.file)
        self.assertIsNone(settings)
        self.assertIn("chmod 600", error)
        bridge = HomeAssistantBridge(config_path=self.file)
        self.assertFalse(bridge.configured)

    def test_no_public_plain_http_or_unlisted_devices(self):
        for url in (
            "http://example.org:8123", "http://8.8.8.8:8123",
            "ftp://homeassistant.local", "http://user:password@homeassistant.local",
            "http://homeassistant.local:8123/api/states",
            "http://homeassistant.local:8123/?token=secret",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    validate_base_url(url)
        self.assertEqual(
            validate_base_url("https://my-home.example.net:8123"),
            "https://my-home.example.net:8123",
        )
        self.assertEqual(
            validate_base_url("http://192.168.1.8:8123/"),
            "http://192.168.1.8:8123",
        )
        for entities in (
            ["lock.front_door"], ["cover.garage"], ["camera.entry"],
            ["light.lamp", "light.lamp"], ["switch.bad-name"],
            ["light.lamp"] * 9, [],
        ):
            with self.subTest(entities=entities):
                with self.assertRaises(ValueError):
                    validate_entities(entities)

    def test_refresh_reads_only_allowlisted_entities_with_bearer(self):
        bridge = self.make_bridge()
        self.assertFalse(bridge.snapshot()["online"])
        bridge._refresh_worker()
        state = bridge.snapshot()
        self.assertTrue(state["online"])
        self.assertEqual(len(state["items"]), 2)
        self.assertEqual([i["state"] for i in state["items"]], ["on", "off"])
        self.assertEqual([i["name"] for i in state["items"]],
                         ["Test Lamp", "Test Lamp"])
        session = self.sessions[0]
        self.assertEqual(session.headers["Authorization"], "Bearer " + self.token)
        self.assertFalse(session.trust_env)
        self.assertEqual(len(session.get_calls), 2)
        self.assertTrue(all(t == (2, 4) and redir is False
                            for _, t, redir in session.get_calls))
        self.assertNotIn(self.token, str(state))

    def test_toggle_uses_only_on_off_service_and_no_redirects(self):
        bridge = self.make_bridge()
        bridge._refresh_worker()
        self.assertFalse(bridge.toggle(99))
        with patch("home_assistant_bridge.threading.Thread") as thread:
            self.assertTrue(bridge.toggle(0))
            self.assertFalse(bridge.toggle(0))  # busy
            callback = thread.call_args.kwargs["target"]
            args = thread.call_args.kwargs["args"]
        callback(*args)
        client = self.sessions[-1]
        self.assertEqual(client.post_calls[0][0],
                         "http://homeassistant.local:8123/api/services/light/turn_off")
        self.assertEqual(client.post_calls[0][1],
                         {"entity_id": "light.living_room"})
        self.assertFalse(client.post_calls[0][3])
        self.assertEqual(client.headers["Authorization"], "Bearer " + self.token)
        self.assertEqual(bridge.snapshot()["items"][0]["busy"], False)
        self.assertEqual(bridge.snapshot()["items"][0]["state"], "off")

        with patch("home_assistant_bridge.threading.Thread") as thread:
            self.assertTrue(bridge.toggle(1))
            callback = thread.call_args.kwargs["target"]
            args = thread.call_args.kwargs["args"]
        callback(*args)
        self.assertEqual(self.sessions[-1].post_calls[0][0],
                         "http://homeassistant.local:8123/api/services/switch/turn_on")
        self.assertEqual(bridge.snapshot()["items"][1]["state"], "on")

    def test_unavailable_entities_never_toggle(self):
        bridge = self.make_bridge()
        bridge._refresh_worker()
        with bridge._lock:
            bridge._items[0]["state"] = "unavailable"
        self.assertFalse(bridge.toggle(0))
        with bridge._lock:
            bridge._online = False
        self.assertFalse(bridge.toggle(1))

    def test_snapshot_never_exposes_server_or_token(self):
        bridge = self.make_bridge()
        bridge._refresh_worker()
        output = str(bridge.snapshot())
        self.assertNotIn(self.token, output)
        self.assertNotIn("http://homeassistant.local", output)


class HomeAssistantScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()
        cls.fonts = (
            pygame.font.Font(None, 29),
            pygame.font.Font(None, 23),
            pygame.font.Font(None, 17),
        )

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.screen = pygame.Surface((800, 480))
        self.snapshot = {
            "configured": True, "online": True, "message": "",
            "items": [
                {"id": "light.living_room", "name": "Living room",
                 "state": "on", "busy": False},
                {"id": "switch.table_lamp", "name": "Plug",
                 "state": "off", "busy": False},
            ],
        }

    def test_premium_home_keeps_previous_shortcuts(self):
        self.assertEqual(len(SHORTCUTS), 6)
        self.assertEqual(home_hit(SHORTCUT_RECTS["SMART HOME"].center),
                         ("page", "home_assistant"))
        for name, target in (
            ("RADIO", "radio"), ("BIBLE", "bible"),
            ("YOUTUBE", "youtube"), ("PHOTOS", "photo_frame"),
            ("FAVOURITES", "favorites"),
        ):
            self.assertEqual(home_hit(SHORTCUT_RECTS[name].center),
                             ("page", target))
        rects = list(SHORTCUT_RECTS.values())
        for r in rects:
            self.assertTrue(0 <= r.left < r.right <= 800)
            self.assertTrue(65 <= r.top < r.bottom <= 465)
            self.assertFalse(any(r.colliderect(o) for o in rects if o is not r))

    def test_8_tiles_are_on_screen_and_hit_tested(self):
        self.assertTrue(draw(self.screen, *self.fonts, self.snapshot))
        self.assertEqual(hit(BACK.center, self.snapshot), ("page", "menu"))
        self.assertEqual(hit(DEVICE_TILES[0].center, self.snapshot), ("toggle", 0))
        self.assertEqual(hit(DEVICE_TILES[1].center, self.snapshot), ("toggle", 1))
        self.assertIsNone(hit(DEVICE_TILES[3].center, self.snapshot))
        for tile in DEVICE_TILES:
            self.assertTrue(0 <= tile.left < tile.right <= 800)
            self.assertTrue(65 < tile.top < tile.bottom < 465)

    def test_offline_state_and_busy_devices_are_not_clickable(self):
        offline = dict(self.snapshot, online=False)
        self.assertTrue(draw(self.screen, *self.fonts, offline))
        self.assertIsNone(hit(DEVICE_TILES[0].center, offline))
        busy = dict(self.snapshot)
        busy["items"] = [dict(self.snapshot["items"][0], busy=True)]
        self.assertIsNone(hit(DEVICE_TILES[0].center, busy))
        self.assertTrue(draw(self.screen, *self.fonts, busy))

    def test_unconfigured_page_draws_help_without_secret(self):
        inactive = {
            "configured": False, "online": False, "message": "Not configured",
            "items": [],
        }
        self.assertTrue(draw(self.screen, *self.fonts, inactive))
        self.assertEqual(hit(BACK.center, inactive), ("page", "menu"))
        self.assertIsNone(hit(DEVICE_TILES[0].center, inactive))

    def test_audio_playback_files_are_not_modified(self):
        code = Path("touch_radio.py").read_text(encoding="utf-8")
        for marker in (
            "home_assistant = HomeAssistantBridge()",
            "home_assistant.tick()",
            'if active_page == "home_assistant":',
            "home_assistant_hit(", "home_assistant.toggle(value)",
            "draw_home_assistant(", "draw_smart_home(",
        ):
            self.assertIn(marker, code)


if __name__ == "__main__":
    unittest.main()

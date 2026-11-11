"""Headless tests for optional PiRadio Smart Remote 2.0."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

from remote_v2_actions import validate_bible_command, validate_favorite_command
from smart_remote_v2 import REMOTE_V2_HTML
from media_session import resolve_media_snapshot


class RemoteHtmlParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = set()
        self.nav = set()
        self.scripts = []
        self.current_script = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            if attrs["id"] in self.ids:
                raise AssertionError("Duplicate HTML id: " + attrs["id"])
            self.ids.add(attrs["id"])
        if tag == "a":
            self.links.add(attrs.get("href"))
        if tag == "button" and "data-tab" in attrs:
            self.nav.add(attrs["data-tab"])
        if tag == "script":
            self.current_script = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.current_script = False

    def handle_data(self, data):
        if self.current_script:
            self.scripts.append(data)


class SmartRemoteV2Tests(unittest.TestCase):
    def test_all_five_navigation_tabs_and_shared_transport_exist(self):
        parser = RemoteHtmlParser()
        parser.feed(REMOTE_V2_HTML)
        self.assertEqual(parser.nav, {"home", "radio", "bible", "video", "more"})
        for name in (
            "home-title", "home-source", "media-toggle", "media-prev",
            "media-next", "volume-slider", "home-seek",
            "station-filter", "station-list", "favourite-list",
            "bible-book", "bible-chapter", "bible-play", "bible-bookmarks",
            "youtube-query", "youtube-results", "video-controls",
            "video-seek", "video-minimize", "video-restore",
            "weather-forecast", "online-dot", "toast",
        ):
            with self.subTest(id=name):
                self.assertIn(name, parser.ids)

    def test_old_photo_and_cast_portals_are_preserved(self):
        parser = RemoteHtmlParser()
        parser.feed(REMOTE_V2_HTML)
        self.assertIn("/", parser.links)
        self.assertIn("/frame", parser.links)
        self.assertIn("/cast", parser.links)
        self.assertEqual(len(parser.scripts), 1)

    def test_remote_does_not_create_second_player_or_inject_station_html(self):
        source = REMOTE_V2_HTML
        self.assertNotIn("<audio", source)
        self.assertNotIn("<video", source)
        self.assertNotIn("new Audio(", source)
        self.assertNotIn("eval(", source)
        self.assertIn("replaceChildren()", source)
        self.assertIn("textContent=", source)
        self.assertNotIn("innerHTML=", source)
        self.assertIn('api("/api/media/session")', source)
        self.assertIn('post("/api/remote-v2/transport"', source)

    def test_bible_select_validates_chapter_boundaries(self):
        counts = [50, 40, 27]
        self.assertEqual(
            validate_bible_command(
                {"action": "select", "book": 0, "chapter": 50, "autoplay": True},
                counts,
            ),
            {"action": "select", "book": 0, "chapter": 50, "autoplay": True},
        )
        self.assertEqual(validate_bible_command(
            {"action": "select", "book": 1, "chapter": 1}, counts,
        )["autoplay"], False)
        for invalid in (
            {"action": "select", "book": 0, "chapter": 51},
            {"action": "select", "book": 3, "chapter": 1},
            {"action": "select", "book": -1, "chapter": 1},
            {"action": "select", "book": True, "chapter": 2},
            {"action": "select", "book": 0, "chapter": True},
            {"action": "select", "book": 0, "chapter": 1, "autoplay": "yes"},
            {"action": "select", "book": "0", "chapter": 1},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_bible_command(invalid, counts)

    def test_other_bible_controls_reject_unexpected_actions(self):
        for action in ("play", "pause", "next", "prev", "stop", "bookmark"):
            self.assertEqual(validate_bible_command({"action": action}, [50]),
                             {"action": action})
        for invalid in ({}, [], None, {"action": "restart"},
                        {"action": True}, {"action": "seek"}):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_bible_command(invalid, [50])

    def test_favourites_never_wrap_station_indices(self):
        self.assertEqual(
            validate_favorite_command({"action": "toggle", "index": 2}, 3),
            {"action": "toggle", "index": 2},
        )
        for invalid in (
            {"action": "toggle", "index": 3},
            {"action": "toggle", "index": -1},
            {"action": "play", "index": True},
            {"action": "play", "index": "1"},
            {"action": "delete", "index": 0},
            {},
            [],
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_favorite_command(invalid, 3)

    def test_live_mpv_seekability_is_not_invented(self):
        s = resolve_media_snapshot(
            video_status={
                "playing": True, "source": "screen_mirror",
                "duration": 360, "seekable": False,
            }
        )
        self.assertFalse(s.seekable)
        s = resolve_media_snapshot(
            video_status={
                "playing": True, "source": "guest_video",
                "duration": 360, "seekable": True,
            }
        )
        self.assertTrue(s.seekable)

    def test_routes_are_additive_and_bible_stays_on_main_thread(self):
        code = Path("touch_radio.py").read_text(encoding="utf-8")
        for item in (
            "@app.route('/remote-v2')",
            "@app.route('/api/remote-v2/bible', methods=['GET', 'POST'])",
            "@app.route('/api/remote-v2/favorites', methods=['GET', 'POST'])",
            "@app.route('/api/remote-v2/transport', methods=['POST'])",
            "remote_v2_commands.put_nowait(",
            "remote_v2_commands.get_nowait()",
            "for _remote_v2_attempt in range(12):",
            "bible_player.play(player.stop)",
            "favorite_indices.insert(0, station_index)",
            'href="/remote-v2"',
            "@app.route('/')",
            "@app.route('/api/youtube/video', methods=['POST'])",
        ):
            with self.subTest(marker=item):
                self.assertIn(item, code)


if __name__ == "__main__":
    unittest.main()

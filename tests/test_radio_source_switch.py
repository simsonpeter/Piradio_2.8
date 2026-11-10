"""Regression tests for returning to TC RADIOS from YouTube audio or MPV.

The full PiRadio module initializes hardware on import, so compile and run
only its source-routing helpers with stand-in media backends.
"""
import ast
from pathlib import Path
import unittest
from unittest.mock import MagicMock

import pygame

from landscape_immersive import (
    STATIONS_PER_PAGE, RADIO_STATIONS, RADIO_PLAY, STATION_CLOSE,
    STATION_NEXT, STATION_PREV, STATION_ROWS,
    radio_station_indices, draw_radio, radio_hit,
    draw_station_picker, station_picker_hit,
)


def load_audio_handover_helpers():
    source = Path("touch_radio.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    selected = ("regular_radio_choices", "preferred_radio_index",
                "select_live_radio", "skip_live_radio", "open_live_radio_page")
    body = [node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in selected]
    assert len(body) == len(selected), "Missing source-switching functions"
    compiled = compile(ast.Module(body=body, type_ignores=[]),
                       "touch_radio.py", "exec")
    runtime = {"radio_station_indices": radio_station_indices}
    exec(compiled, runtime)
    return runtime


class RadioSourceSelectionTests(unittest.TestCase):
    def setUp(self):
        self.runtime = load_audio_handover_helpers()
        self.stations = [
            {"name": "TC RADIOS", "url": "https://radio.example/tc", "genre": "Tamil"},
            {"name": "Tamil Gospel", "url": "https://radio.example/gospel", "genre": "Gospel"},
            {"name": "YT: Previous song", "url": "https://yt.example/audio",
             "youtube_id": "123456789AB"},
            {"name": "Guest file", "url": "file:///x", "direct_link_id": 2},
        ]
        self.runtime.update(
            stations=self.stations,
            base_stations=self.stations[:2],
            current_idx=2,
            last_radio_station_url="https://radio.example/tc",
            youtube_audio_generation=3,
            youtube_touch_pending=("play", "123456789AB", "Video", "url", False),
            youtube_touch_busy=True,
            youtube_player_open_requested=True,
            _youtube_was_playing=True,
            _youtube_ended_handled=False,
            active_page="youtube_player",
            radio_station_picker_open=True,
        )
        self.play = MagicMock(return_value=True)
        self.runtime["play"] = self.play
        self.runtime["youtube_video"] = MagicMock()
        self.runtime["youtube_video"].is_playing.return_value = True
        self.runtime["bible_player"] = MagicMock()
        self.runtime["bible_player"].playing = False

    def test_radio_indices_filter_youtube_and_attachments(self):
        self.assertEqual(radio_station_indices(self.stations, self.stations[:2]),
                         [0, 1])

    def test_return_from_youtube_cancels_pending_and_selects_original_radio(self):
        switch = self.runtime["select_live_radio"]
        self.assertTrue(switch())
        self.play.assert_called_once()
        self.assertEqual(self.runtime["current_idx"], 0)
        self.assertEqual(self.runtime["youtube_audio_generation"], 4)
        self.assertIsNone(self.runtime["youtube_touch_pending"])
        self.assertFalse(self.runtime["youtube_touch_busy"])
        self.assertFalse(self.runtime["youtube_player_open_requested"])
        self.assertTrue(self.runtime["_youtube_ended_handled"])
        self.assertEqual(self.runtime["last_radio_station_url"],
                         "https://radio.example/tc")

    def test_switch_from_radio_tile_changes_page_and_media_source(self):
        self.assertTrue(self.runtime["open_live_radio_page"]())
        self.assertEqual(self.runtime["active_page"], "radio")
        self.assertFalse(self.runtime["radio_station_picker_open"])
        self.play.assert_called_once()

    def test_next_prev_are_radio_only(self):
        self.assertTrue(self.runtime["skip_live_radio"](1))
        self.assertEqual(self.runtime["current_idx"], 1)
        self.assertTrue(self.runtime["skip_live_radio"](-1))
        self.assertEqual(self.runtime["current_idx"], 0)

    def test_bad_station_index_cannot_launch_youtube(self):
        self.assertFalse(self.runtime["select_live_radio"](2))
        self.assertFalse(self.runtime["select_live_radio"](3))
        self.play.assert_not_called()


class RadioStationPickerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_station_picker_has_radio_only_touch_targets(self):
        stations = [
            {"name": f"TC RADIOS {i+1}", "url": f"https://radio.example/{i}",
             "genre": "Tamil"} for i in range(10)
        ]
        stations.append({"name": "YT", "url": "https://yt.test",
                         "youtube_id": "123456789AB"})
        indices = radio_station_indices(stations, stations[:10])
        self.assertEqual(len(indices), 10)
        self.assertEqual(station_picker_hit(STATION_CLOSE.center, indices, 0),
                         ("close", None))
        self.assertEqual(station_picker_hit(STATION_NEXT.center, indices, 0),
                         ("page", 1))
        self.assertEqual(station_picker_hit(STATION_PREV.center, indices, 0),
                         ("page", -1))
        for slot, rect in enumerate(STATION_ROWS):
            self.assertEqual(station_picker_hit(rect.center, indices, 0),
                             ("station", slot))
        self.assertEqual(station_picker_hit(STATION_ROWS[0].center, indices, 1),
                         ("station", 6))
        s = pygame.Surface((800, 480))
        f = (pygame.font.Font(None, 29), pygame.font.Font(None, 21),
             pygame.font.Font(None, 17))
        draw_station_picker(s, *f, stations, indices, 0, selected_index=1)
        self.assertNotEqual(tuple(s.get_at((100, 108))[:3]), (0, 0, 0))

    def test_radio_player_has_explicit_switch_button(self):
        s = pygame.Surface((800, 480))
        f = (pygame.font.Font(None, 29), pygame.font.Font(None, 21),
             pygame.font.Font(None, 17))
        draw_radio(s, *f, "TC RADIOS", "Select a channel",
                   False, 30, video_status=None)
        self.assertEqual(radio_hit(RADIO_STATIONS.center), ("radio_stations", None))
        self.assertEqual(radio_hit(RADIO_PLAY.center), ("radio_play", None))


if __name__ == "__main__":
    unittest.main()

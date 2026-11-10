"""Regression tests for dedicated TCRADIOS + independent YouTube audio sources.

This extracts only plain Python functions from touch_radio.py to avoid
initializing audio/GPIO/pygame and opening PiRadio's Flask server in CI.
"""
import ast
from pathlib import Path
import re
import time
import types
import unittest
from unittest.mock import Mock


class State:
    Playing = "playing"
    Paused = "paused"
    Stopped = "stopped"
    Ended = "ended"
    Error = "error"
    Opening = "opening"
    Buffering = "buffering"


class FakePlayer:
    def __init__(self):
        self.state = State.Stopped
        self.media = None
        self.volume = 0
        self.stop_count = 0

    def get_state(self):
        return self.state

    def is_playing(self):
        return self.state == State.Playing

    def set_media(self, media):
        self.media = media

    def audio_set_volume(self, volume):
        self.volume = volume

    def play(self):
        self.state = State.Playing

    def pause(self):
        self.state = (
            State.Paused if self.state == State.Playing else State.Playing
        )

    def stop(self):
        self.state = State.Stopped
        self.stop_count += 1


class FakeVideo:
    def __init__(self):
        self.playing = False
        self.stop_count = 0

    def is_playing(self):
        return self.playing

    def stop(self):
        self.playing = False
        self.stop_count += 1


EXPORTED = {
    "stop_youtube_audio", "stop_other_audio_for_bible",
    "play_youtube_station", "play", "skip_playback",
    "skip_radio_station", "return_to_tcradios",
    "switch_landscape_page", "current_youtube_id",
    "toggle_active_playback", "get_status", "get_now_playing",
    "activate_tcradios_remote", "play_index",
}


def load_logic(namespace):
    source = Path(__file__).resolve().parents[1] / "touch_radio.py"
    syntax = ast.parse(source.read_text(encoding="utf-8"))
    definitions = []
    for node in syntax.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in EXPORTED:
            node.decorator_list = []
            definitions.append(node)
    names = {node.name for node in definitions}
    if names != EXPORTED:
        raise AssertionError(f"Missing playback functions: {EXPORTED - names}")
    module = ast.Module(body=definitions, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(source), "exec"), namespace)


class DedicatedRadioTests(unittest.TestCase):
    def setUp(self):
        radio = FakePlayer()
        youtube = FakePlayer()
        mpv = FakeVideo()
        bible = types.SimpleNamespace(
            playing=False, paused=False, player=FakePlayer(),
        )
        bible.stop = lambda: setattr(bible, "playing", False)
        audio_manager = Mock()
        self.env = {
            "player": radio,
            "youtube_audio_player": youtube,
            "youtube_video": mpv,
            "instance": types.SimpleNamespace(media_new=lambda url: url),
            "vlc": types.SimpleNamespace(State=State),
            "bible_player": bible,
            "audio_manager": audio_manager,
            "stations": [
                {"name": "TCRADIOS Tamil", "url": "https://example.test/live-1",
                 "logo": "radio-1.png"},
                {"name": "TCRADIOS Europe", "url": "https://example.test/live-2",
                 "logo": "radio-2.png"},
            ],
            "current_idx": 1,
            "youtube_audio_active": False,
            "youtube_current_id": "",
            "youtube_current_title": "",
            "youtube_current_url": "",
            "vol_level": 48,
            "meta_text": "Last radio metadata",
            "scroll_x": 0, "saver_scroll_x": 0,
            "saved_station_url": "", "saved_station_index": 0,
            "youtube_skip_ids": set(),
            "_youtube_play_started_at": 0,
            "_youtube_was_playing": False,
            "_youtube_ended_handled": False,
            "time": time, "re": re,
            "remember_youtube_queue": Mock(),
            # Native 7-inch YouTube artwork fetch is isolated from the VLC
            # ownership tests; it performs no network I/O in CI.
            "queue_youtube_artwork": Mock(),
            "youtube_player_view": False,
            "continue_youtube_queue": Mock(return_value=True),
            "update_logo": Mock(),
            "save_playback_state": Mock(),
            "rebuild_qr_surface": Mock(),
            "jsonify": lambda obj: obj,
            "active_page": "menu",
        }
        load_logic(self.env)

    def test_youtube_audio_never_adds_to_radio_list(self):
        env = self.env
        count = len(env["stations"])
        prior_idx = env["current_idx"]
        env["play_youtube_station"](
            "dQw4w9WgXcQ", "YouTube sample",
            "https://example.test/youtube-audio.m4a",
        )
        self.assertEqual(len(env["stations"]), count)
        self.assertEqual(env["current_idx"], prior_idx)
        self.assertEqual(env["stations"][prior_idx]["name"], "TCRADIOS Europe")
        self.assertTrue(env["youtube_audio_active"])
        self.assertEqual(env["youtube_current_title"], "YouTube sample")
        self.assertEqual(env["current_youtube_id"](), "dQw4w9WgXcQ")
        self.assertEqual(env["player"].get_state(), State.Stopped)
        self.assertEqual(env["youtube_audio_player"].get_state(), State.Playing)
        self.assertEqual(env["youtube_audio_player"].volume, 48)
        status = env["get_status"]()
        self.assertEqual(status["source"], "youtube_audio")
        self.assertEqual(env["get_now_playing"]()["text"], "YouTube sample")

    def test_radio_page_restores_last_radio_and_stops_youtube(self):
        env = self.env
        env["play_youtube_station"](
            "dQw4w9WgXcQ", "YouTube sample",
            "https://example.test/youtube-audio.m4a",
        )
        self.assertEqual(env["switch_landscape_page"]("radio"), "radio")
        self.assertFalse(env["youtube_audio_active"])
        self.assertEqual(env["youtube_audio_player"].get_state(), State.Stopped)
        self.assertEqual(env["player"].get_state(), State.Playing)
        self.assertEqual(env["player"].media, "https://example.test/live-2")
        self.assertEqual(env["current_idx"], 1)
        self.assertEqual(env["get_status"]()["source"], "radio")
        self.assertEqual(len(env["stations"]), 2)

    def test_radio_prev_next_never_traverse_youtube_results(self):
        env = self.env
        env["play_youtube_station"](
            "dQw4w9WgXcQ", "A",
            "https://example.test/audio-a.m4a",
        )
        env["switch_landscape_page"]("radio")
        env["skip_radio_station"](1)
        self.assertEqual(env["current_idx"], 0)
        self.assertEqual(env["player"].media, "https://example.test/live-1")
        env["skip_radio_station"](-1)
        self.assertEqual(env["current_idx"], 1)
        self.assertEqual(env["player"].media, "https://example.test/live-2")
        self.assertEqual(len(env["stations"]), 2)

    def test_remote_radio_activation_resumes_saved_station(self):
        env = self.env
        env["play_youtube_station"](
            "dQw4w9WgXcQ", "YouTube",
            "https://example.test/audio.m4a",
        )
        result = env["activate_tcradios_remote"]()
        self.assertTrue(result["success"])
        self.assertEqual(result["station"], 1)
        self.assertEqual(env["player"].media, "https://example.test/live-2")

    def test_station_selection_rejects_youtube_or_out_of_range(self):
        env = self.env
        self.assertEqual(env["play_index"](19)[1], 400)
        env["stations"].append({
            "name": "YT stale entry", "youtube_id": "abcdefghijk",
            "url": "https://example.test/a",
        })
        self.assertEqual(env["play_index"](2)[1], 400)
        self.assertEqual(env["play_index"](0), "OK")
        self.assertEqual(env["player"].media, "https://example.test/live-1")

    def test_stop_audio_for_bible_also_stops_youtube_and_mpv(self):
        env = self.env
        env["play_youtube_station"](
            "dQw4w9WgXcQ", "YouTube",
            "https://example.test/audio.m4a",
        )
        env["youtube_video"].playing = True
        env["stop_other_audio_for_bible"]()
        self.assertFalse(env["youtube_audio_active"])
        self.assertEqual(env["youtube_audio_player"].get_state(), State.Stopped)
        self.assertFalse(env["youtube_video"].playing)

    def test_audio_remote_pause_targets_youtube_not_radio(self):
        env = self.env
        env["play_youtube_station"](
            "dQw4w9WgXcQ", "YouTube",
            "https://example.test/audio.m4a",
        )
        env["toggle_active_playback"]()
        self.assertEqual(env["youtube_audio_player"].get_state(), State.Paused)
        self.assertEqual(env["player"].get_state(), State.Stopped)
        env["toggle_active_playback"]()
        self.assertEqual(env["youtube_audio_player"].get_state(), State.Playing)


if __name__ == "__main__":
    unittest.main()

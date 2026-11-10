"""Radio/YouTube source separation and native station picker regression checks."""
import unittest

import pygame
from radio_source import radio_indices, radio_resume_index, radio_step_index
from landscape_radio_picker import (
    draw as draw_radio_picker, hit as station_picker_hit,
    BUTTONS, CLOSE, NEXT, PREV, PAGE_SIZE,
)
from landscape_dashboard import hit as dashboard_hit, RADIO_STATIONS_BUTTON


STATIONS = [
    {"name": "TC Tamil Radio", "url": "https://radio.test/tc"},
    {"name": "TC Worship", "url": "https://radio.test/worship"},
    {"name": "YT: Previously played", "url": "https://yt.test/audio", "youtube_id": "abcdefghijk"},
    {"name": "TC Gospel", "url": "https://radio.test/gospel"},
    {"name": "Temporary direct link", "url": "https://other.test", "direct_link_id": 12},
    {"name": "Imported language station", "url": "https://other.test/2", "language": "French"},
    {"name": "YT: Second track", "url": "https://yt.test/2", "youtube_id": "12345678901"},
    {"name": "TC Radio Two", "url": "https://radio.test/two"},
]


class RadioSourceRegressionTests(unittest.TestCase):
    def test_radio_list_contains_only_genuine_stations(self):
        self.assertEqual(radio_indices(STATIONS), [0, 1, 3, 7])

    def test_returning_from_youtube_remembers_last_radio_by_url(self):
        self.assertEqual(radio_resume_index(
            STATIONS, 6, "https://radio.test/worship"
        ), 1)

    def test_after_youtube_with_no_memory_selects_first_real_radio(self):
        self.assertEqual(radio_resume_index(STATIONS, 6, ""), 0)

    def test_radio_next_previous_skip_youtube_and_other_sources(self):
        self.assertEqual(radio_step_index(STATIONS, 1, 1), 3)
        self.assertEqual(radio_step_index(STATIONS, 3, 1), 7)
        self.assertEqual(radio_step_index(STATIONS, 7, 1), 0)
        self.assertEqual(radio_step_index(STATIONS, 0, -1), 7)

    def test_radio_page_does_not_advance_youtube_queue(self):
        self.assertEqual(radio_step_index(STATIONS, 6, 1, "https://radio.test/tc"), 1)
        self.assertEqual(radio_step_index(STATIONS, 6, -1, "https://radio.test/tc"), 7)

    def test_refresh_reorders_radio_and_recovers_url(self):
        reordered = [STATIONS[3], STATIONS[1], STATIONS[6], STATIONS[0]]
        self.assertEqual(radio_resume_index(
            reordered, 0, "https://radio.test/worship"
        ), 1)

    def test_absent_stations_fail_gracefully(self):
        self.assertIsNone(radio_resume_index([STATIONS[2]], 0, ""))
        self.assertIsNone(radio_step_index([STATIONS[2]], 0, 1))


class RadioPickerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_picker_draws_and_only_touches_actual_station_rows(self):
        surface = pygame.Surface((800, 480))
        surface.fill((0, 0, 0))
        fonts = (pygame.font.Font(None, 30),
                 pygame.font.Font(None, 23), pygame.font.Font(None, 17))
        indices = radio_indices(STATIONS)
        draw_radio_picker(surface, *fonts, STATIONS, indices, 0, 1)
        self.assertEqual(station_picker_hit(BUTTONS[0].center, indices, 0),
                         ("station", 0))
        self.assertEqual(station_picker_hit(BUTTONS[1].center, indices, 0),
                         ("station", 1))
        self.assertEqual(station_picker_hit(CLOSE.center, indices, 0),
                         ("close", None))
        self.assertEqual(station_picker_hit(NEXT.center, indices, 0)[0], "next")
        self.assertEqual(station_picker_hit(PREV.center, indices, 0)[0], "prev")
        self.assertIsNone(station_picker_hit((90, 110), indices, 0))
        self.assertEqual(tuple(surface.get_at((8, 84))[:3]), (0, 0, 0))

    def test_radio_stations_button_not_active_on_home(self):
        self.assertEqual(dashboard_hit(RADIO_STATIONS_BUTTON.center, "radio"),
                         ("radio_stations", None))
        self.assertNotEqual(dashboard_hit(RADIO_STATIONS_BUTTON.center, "menu"),
                            ("radio_stations", None))


if __name__ == "__main__":
    unittest.main()

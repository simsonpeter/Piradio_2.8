"""PiRadio 7 immersive shell and floating dock regression tests."""
import unittest

import pygame
from landscape_immersive import (
    MENU_BUTTON, DOCK_RECT, DOCK_TILES, DOCK_ITEMS, NEW_CONTENT, OLD_CONTENT,
    SWIPE_START_Y, SWIPE_MIN_DISTANCE,
    layout, draw_topbar, draw_dock, dock_hit, to_source, from_source,
)
from landscape_dashboard import (
    draw_dashboard, MINI_OPEN, MINI_PAUSE, MAIN, NAV_RECTS, PREV, PAUSE, NEXT,
)
from landscape_youtube_player import BACK_TO_SEARCH, VIDEO_BUTTON, TRACK
from landscape_pages import PANEL
from landscape_cast import CAST_BUTTON
from smart_photo_frame import FRAME_BUTTON


class ImmersiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()
        cls.font = pygame.font.Font(None, 32)
        cls.small = pygame.font.Font(None, 22)
        cls.tiny = pygame.font.Font(None, 17)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_source_touch_inverse_keeps_native_media_controls(self):
        rects = [
            MINI_OPEN, MINI_PAUSE, PREV, PAUSE, NEXT, MAIN,
            BACK_TO_SEARCH, VIDEO_BUTTON, TRACK, PANEL,
        ]
        for rect in rects:
            with self.subTest(control=rect):
                px = from_source(rect.center)
                original = to_source(px)
                self.assertLessEqual(abs(original[0] - rect.centerx), 1)
                self.assertEqual(original[1], rect.centery)
                self.assertTrue(rect.collidepoint(original))

    def test_sidebar_is_not_in_immersive_viewport(self):
        for rect in NAV_RECTS.values():
            self.assertLessEqual(rect.right, OLD_CONTENT.x)
        self.assertGreater(NEW_CONTENT.width, OLD_CONTENT.width)
        self.assertEqual(NEW_CONTENT.width, 768)

    def test_toolbar_buttons_do_not_overlap(self):
        self.assertFalse(MENU_BUTTON.colliderect(FRAME_BUTTON))
        self.assertFalse(MENU_BUTTON.colliderect(CAST_BUTTON))
        self.assertFalse(FRAME_BUTTON.colliderect(CAST_BUTTON))

    def test_floating_dock_navigation(self):
        for name, page, icon in DOCK_ITEMS:
            with self.subTest(name=name):
                self.assertEqual(dock_hit(DOCK_TILES[name].center), page)
                self.assertTrue(DOCK_RECT.contains(DOCK_TILES[name]))
        self.assertEqual(dock_hit((799, 479)), "dismiss")
        self.assertIsNone(dock_hit((200, 180)))
        self.assertEqual(SWIPE_START_Y, 465)
        self.assertGreaterEqual(SWIPE_MIN_DISTANCE, 60)

    def test_render_native_radio_then_fullwidth_crop(self):
        s = pygame.Surface((800, 480))
        draw_dashboard(
            s, self.font, self.small, self.tiny, "radio",
            "Tamil Christian Radio", "Now playing: Worship", True,
            False, False, "", 45,
        )
        original_left = s.get_at((100, 130))[:3]
        layout(s)
        # Area where old side-nav was painted is now rendered media content.
        self.assertNotEqual(tuple(s.get_at((100, 130))[:3]), original_left)
        draw_topbar(s, self.font, self.small, self.tiny, "radio")
        self.assertNotEqual(tuple(s.get_at((28, 28))[:3]), (0, 0, 0))

    def test_overlay_dock_is_optional_and_usable(self):
        s = pygame.Surface((800, 480))
        draw_dashboard(s, self.font, self.small, self.tiny, "menu",
                       "Station One", "", False, False, False, "", 35)
        layout(s)
        draw_topbar(s, self.font, self.small, self.tiny, "menu", False)
        normal = tuple(s.get_at((400, 250))[:3])
        draw_dock(s, self.font, self.small, self.tiny, "menu")
        self.assertNotEqual(tuple(s.get_at((400, 250))[:3]), normal)


if __name__ == "__main__":
    unittest.main()

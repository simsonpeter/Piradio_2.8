"""Immersive PiRadio 7 rendering, hidden menu and old-page hitbox alignment."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

from landscape_immersive import (
    MENU_BUTTON, NAV_HANDLE, DRAWER, CONTENT_DEST, CONTENT_SOURCE,
    MINI_DEST, MINI_SOURCE, RADIO_PREV, RADIO_PAUSE, RADIO_NEXT,
    RADIO_SEEK, RADIO_VOLUME, HOME_TILES, DOCK_TILES,
    draw_radio, draw_home, draw_dock, draw_header, draw_handle,
    radio_hit, home_hit, dock_hit, compose_page, to_legacy,
)


class ImmersiveRendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.surface = pygame.Surface((800, 480))
        self.fonts = tuple(pygame.font.Font(None, sz) for sz in (34, 23, 17))

    def test_radio_is_full_width_without_sidebar(self):
        logo = pygame.Surface((100, 100))
        logo.fill((183, 183, 183))
        draw_radio(self.surface, *self.fonts, "TC RADIOS", "A Tamil song",
                   True, 48, logo, None, False)
        draw_header(self.surface, self.fonts[0], self.fonts[2], "radio")
        draw_handle(self.surface, self.fonts[2])
        # Left part of the physical screen is populated by the radio artwork.
        self.assertNotEqual(tuple(self.surface.get_at((55, 150))[:3]), (0, 0, 0))
        # An unused pixel outside the radio artwork stays pure black.
        self.assertEqual(tuple(self.surface.get_at((5, 120))[:3]), (0, 0, 0))
        self.assertEqual(radio_hit(RADIO_PAUSE.center), ("audio", "pause"))
        self.assertEqual(radio_hit(RADIO_PREV.center), ("audio", "prev"))
        self.assertEqual(radio_hit(RADIO_NEXT.center), ("audio", "next"))
        self.assertEqual(radio_hit(RADIO_VOLUME.center)[0], "volume")

    def test_mpv_radio_seek_and_restore(self):
        status = {"playing": True, "title": "Tamil Bible documentary",
                  "paused": False, "minimized": True, "position": 75,
                  "duration": 300, "source": "youtube_video"}
        draw_radio(self.surface, *self.fonts, "Old station", "old",
                   False, 40, video_status=status)
        action = radio_hit(RADIO_SEEK.center, status)
        self.assertEqual(action[0], "seek")
        self.assertAlmostEqual(action[1], 150, delta=1)
        self.assertEqual(radio_hit((160, 200), status), ("restore", None))

    def test_home_tiles_and_miniplayer(self):
        draw_home(self.surface, *self.fonts,
                  "Bayapadathey - Tamil Christian Music", False, "youtube_audio")
        for rect, (label, _icon, _page) in HOME_TILES:
            self.assertEqual(home_hit(rect.center), ("page", label))
        self.assertEqual(home_hit((90, 423)), ("open_player", None))
        self.assertEqual(home_hit((659, 428)), ("audio", "pause"))

    def test_hidden_dock_targets_are_disjoint_and_return_destinations(self):
        draw_home(self.surface, *self.fonts, "Ready", False)
        draw_dock(self.surface, *self.fonts, "radio")
        for rect, (_label, _icon, destination) in DOCK_TILES:
            self.assertEqual(dock_hit(rect.center), destination)
        self.assertEqual(dock_hit((5, 5)), "dismiss")
        self.assertEqual(dock_hit((22, 207)), "consume")
        self.assertTrue(MENU_BUTTON.collidepoint(39, 27))
        self.assertTrue(NAV_HANDLE.collidepoint(400, 472))

    def test_secondary_compositor_content_and_mini_hit_alignment(self):
        source = pygame.Surface((800, 480))
        source.fill((0, 0, 0))
        target_in_source = pygame.Rect(180, 190, 85, 44)
        pygame.draw.rect(source, (137, 175, 213), target_in_source)
        mini_in_source = pygame.Rect(630, 414, 68, 34)
        pygame.draw.rect(source, (204, 136, 81), mini_in_source)
        compose_page(self.surface, source)
        content_point = (
            CONTENT_DEST.x + round((target_in_source.centerx - CONTENT_SOURCE.x)
                                   * CONTENT_DEST.w / CONTENT_SOURCE.w),
            target_in_source.centery,
        )
        self.assertEqual(tuple(self.surface.get_at(content_point)[:3]),
                         (137, 175, 213))
        self.assertTrue(target_in_source.collidepoint(to_legacy(content_point)))

        mini_point = (
            MINI_DEST.x + round((mini_in_source.centerx - MINI_SOURCE.x)
                                * MINI_DEST.w / MINI_SOURCE.w),
            mini_in_source.centery + MINI_DEST.y - MINI_SOURCE.y,
        )
        self.assertEqual(tuple(self.surface.get_at(mini_point)[:3]),
                         (204, 136, 81))
        self.assertTrue(mini_in_source.collidepoint(to_legacy(mini_point)))


if __name__ == "__main__":
    unittest.main()

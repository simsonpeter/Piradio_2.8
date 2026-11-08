"""Compact iOS-inspired launcher and iPod-style radio framing for 320x480 Pygame.
No audio or navigation state is owned by this module.
"""
from pathlib import Path
import pygame
from fa_icons import draw_icon

PREFERENCE = Path.home() / ".piradio_ios_theme"
THEMES = {
    "dark": {"bg": (12, 17, 30), "card": (29, 39, 58), "ink": (247, 249, 253),
             "muted": (160, 175, 195), "edge": (61, 76, 99)},
    "light": {"bg": (231, 235, 241), "card": (255, 255, 255), "ink": (29, 41, 57),
              "muted": (103, 115, 131), "edge": (195, 205, 219)},
}
ACCENTS = [(64, 104, 176), (179, 92, 119), (56, 139, 132), (119, 98, 164),
           (193, 135, 61), (79, 116, 169), (68, 143, 157), (105, 118, 139),
           (182, 80, 104), (64, 104, 176)]
LABELS = ["RADIO", "FAVORITES", "WEATHER", "CLOCK", "ALARM", "SYSTEM",
          "LANGUAGES", "SETTINGS", "YOUTUBE", "TAMIL BIBLE"]
SUBTITLES = ["Now playing", "Saved stations", "Forecast", "Time",
             "Sleep timer", "Device status", "Stations", "Preferences",
             "Videos", "66 books"]
TOGGLE = pygame.Rect(246, 12, 60, 34)


def raised_card(surface, rect, mode="light", radius=16, elevation=3):
    """Low-cost layered shadows and crisp borders for 320x480 framebuffer."""
    colors = THEMES[mode]
    if mode == "light":
        for offset, shade in ((elevation+2, (208, 215, 225)),
                              (elevation, (216, 223, 232))):
            pygame.draw.rect(surface, shade, rect.move(0, offset),
                             border_radius=radius)
    pygame.draw.rect(surface, colors["card"], rect, border_radius=radius)
    pygame.draw.rect(surface, colors["edge"], rect, 1, border_radius=radius)


def load_mode():
    try:
        mode = PREFERENCE.read_text(encoding="utf-8").strip()
        return mode if mode in THEMES else "light"
    except OSError:
        return "light"


def toggle_mode(mode):
    mode = "light" if mode == "dark" else "dark"
    try:
        PREFERENCE.write_text(mode, encoding="utf-8")
    except OSError:
        pass
    return mode


def _center(surface, font, text, color, rect):
    rendered = font.render(text, True, color)
    surface.blit(rendered, rendered.get_rect(center=rect.center))


def draw_home(surface, small, tiny, card_rects, mode):
    """Paint ten tappable cards using the existing menu hit rectangles."""
    colors = THEMES[mode]
    surface.fill(colors["bg"])
    title = small.render("PiRadio", True, colors["ink"])
    surface.blit(title, (17, 16))
    raised_card(surface, TOGGLE, mode)
    _center(surface, tiny, "LIGHT" if mode == "dark" else "DARK",
            colors["ink"], TOGGLE)
    subtitle = tiny.render("Your music, your Bible.", True, colors["muted"])
    surface.blit(subtitle, (17, 48))
    for index, rect in enumerate(card_rects):
        raised_card(surface, rect, mode)
        # Icon tile is deliberately drawn rather than loading external artwork.
        tile = pygame.Rect(rect.x + 10, rect.y + 8, 32, 32)
        pygame.draw.rect(surface, ACCENTS[index], tile, border_radius=9)
        icons = ["radio", "favorites", "weather", "clock", "alarm",
                 "system", "languages", "settings", "youtube", "bible"]
        draw_icon(surface, icons[index], tile.center, 19, (255,255,255))
        text = tiny.render(LABELS[index], True, colors["ink"])
        surface.blit(text, (rect.x + 48, rect.y + 13))
        detail = tiny.render(SUBTITLES[index], True, colors["muted"])
        surface.blit(detail, (rect.x + 48, rect.y + 33))
    # Mini-player occupies y=438..476; no overlapping footer.


def draw_player_frame(surface, mode):
    """Subtle album-art card; original artwork and touch controls draw above it."""
    colors = THEMES[mode]
    pygame.draw.rect(surface, colors["card"], (10, 67, 300, 178),
                     border_radius=22)
    pygame.draw.rect(surface, colors["edge"], (10, 67, 300, 178), 1,
                     border_radius=22)


MINI_BAR = pygame.Rect(8, 438, 304, 38)
MINI_ACTION = pygame.Rect(262, 438, 50, 38)


def draw_mini_player(surface, font, mode, title, playing, bible=False, youtube=False):
    """Compact playback bar on the launcher, with a separate play/pause target."""
    colors = THEMES[mode]
    raised_card(surface, MINI_BAR, mode, 13, 1)
    tile = pygame.Rect(15, 443, 28, 28)
    pygame.draw.rect(surface, ACCENTS[8 if youtube else 9 if bible else 0], tile, border_radius=8)
    draw_icon(surface, "youtube" if youtube else "bible" if bible else "radio",
              tile.center, 17, (255,255,255))
    label = title[:26]
    rendered = font.render(label, True, colors["ink"])
    surface.blit(rendered, (49, 448))
    draw_icon(surface, "pause" if playing else "play", MINI_ACTION.center, 19, colors["ink"])


def draw_youtube_skin(surface, font, tiny, mode, title, playing):
    """Noninteractive visual header above the existing YouTube search/results UI."""
    colors = THEMES[mode]
    banner = pygame.Rect(8, 7, 304, 52)
    raised_card(surface, banner, mode, 17)
    pygame.draw.rect(surface, (222, 70, 85), (18, 15, 37, 36), border_radius=10)
    draw_icon(surface, "youtube", (36,33), 22, (255,255,255))
    heading = font.render("YouTube Player", True, colors["ink"])
    surface.blit(heading, (64, 12))
    subtitle = tiny.render((title or "Search and play")[:29], True, colors["muted"])
    surface.blit(subtitle, (64, 35))

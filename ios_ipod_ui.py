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
    "light": {"bg": (239, 243, 249), "card": (255, 255, 255), "ink": (24, 36, 56),
              "muted": (93, 108, 128), "edge": (211, 221, 235)},
}
ACCENTS = [(57, 133, 244), (234, 71, 104), (73, 174, 150), (143, 104, 221),
           (247, 160, 62), (91, 141, 228), (56, 175, 202), (109, 128, 153),
           (222, 101, 139), (63, 153, 208)]
LABELS = ["RADIO", "FAVORITES", "WEATHER", "CLOCK", "ALARM", "SYSTEM",
          "LANGUAGES", "SETTINGS", "YOUTUBE", "TAMIL BIBLE"]
SUBTITLES = ["Now playing", "Saved stations", "Forecast", "Time",
             "Sleep timer", "Device status", "Stations", "Preferences",
             "Videos", "66 books"]
TOGGLE = pygame.Rect(246, 12, 60, 34)


def load_mode():
    try:
        mode = PREFERENCE.read_text(encoding="utf-8").strip()
        return mode if mode in THEMES else "dark"
    except OSError:
        return "dark"


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
    pygame.draw.rect(surface, colors["card"], TOGGLE, border_radius=16)
    pygame.draw.rect(surface, colors["edge"], TOGGLE, 1, border_radius=16)
    _center(surface, tiny, "LIGHT" if mode == "dark" else "DARK",
            colors["ink"], TOGGLE)
    subtitle = tiny.render("Your music, your Bible.", True, colors["muted"])
    surface.blit(subtitle, (17, 48))
    for index, rect in enumerate(card_rects):
        pygame.draw.rect(surface, colors["card"], rect, border_radius=16)
        pygame.draw.rect(surface, colors["edge"], rect, 1, border_radius=16)
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
    _center(surface, tiny, "iPod player  |  iOS library", colors["muted"],
            pygame.Rect(12, 449, 296, 24))


def draw_player_frame(surface, mode):
    """Subtle album-art card; original artwork and touch controls draw above it."""
    colors = THEMES[mode]
    pygame.draw.rect(surface, colors["card"], (10, 67, 300, 178),
                     border_radius=22)
    pygame.draw.rect(surface, colors["edge"], (10, 67, 300, 178), 1,
                     border_radius=22)


MINI_BAR = pygame.Rect(8, 438, 304, 38)
MINI_ACTION = pygame.Rect(262, 438, 50, 38)


def draw_mini_player(surface, font, mode, title, playing, bible=False):
    """Compact playback bar on the launcher, with a separate play/pause target."""
    colors = THEMES[mode]
    pygame.draw.rect(surface, colors["card"], MINI_BAR, border_radius=13)
    pygame.draw.rect(surface, colors["edge"], MINI_BAR, 1, border_radius=13)
    tile = pygame.Rect(15, 443, 28, 28)
    pygame.draw.rect(surface, (57, 133, 244), tile, border_radius=8)
    draw_icon(surface, "bible" if bible else "radio", tile.center, 17, (255,255,255))
    label = title[:26]
    rendered = font.render(label, True, colors["ink"])
    surface.blit(rendered, (49, 448))
    draw_icon(surface, "pause" if playing else "play", MINI_ACTION.center, 19, colors["ink"])


def draw_youtube_skin(surface, font, tiny, mode, title, playing):
    """Noninteractive visual header above the existing YouTube search/results UI."""
    colors = THEMES[mode]
    banner = pygame.Rect(8, 7, 304, 52)
    pygame.draw.rect(surface, colors["card"], banner, border_radius=17)
    pygame.draw.rect(surface, colors["edge"], banner, 1, border_radius=17)
    pygame.draw.rect(surface, (222, 70, 85), (18, 15, 37, 36), border_radius=10)
    draw_icon(surface, "youtube", (36,33), 22, (255,255,255))
    heading = font.render("YouTube Player", True, colors["ink"])
    surface.blit(heading, (64, 12))
    subtitle = tiny.render((title or "Search and play")[:29], True, colors["muted"])
    surface.blit(subtitle, (64, 35))

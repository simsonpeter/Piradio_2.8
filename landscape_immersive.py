"""PiRadio 7: immersive 800x480 shell with an on-demand floating navigation dock.

The existing 640px-wide native media panels are presented edge-to-edge without
their old permanent 145px sidebar. Touches are mapped back to their original
native coordinates, preserving Bible, YouTube, Radio, Weather, Guest Cast and
the shared media controls. A full redesign can later migrate each panel to
edge-to-edge native geometry without changing the current navigation contract.
"""
from datetime import datetime
import pygame

BG = (0, 0, 0)
INK = (249, 249, 249)
MUTED = (168, 168, 168)
EDGE = (75, 75, 75)
ACCENT = (72, 220, 232)

# Native source panel: everything to the right of the obsolete sidebar.
OLD_CONTENT = pygame.Rect(150, 65, 640, 400)
# Full-width usable view under a custom minimalist 65px toolbar.
NEW_CONTENT = pygame.Rect(16, 65, 768, 400)
MENU_BUTTON = pygame.Rect(13, 8, 47, 44)
SWIPE_START_Y = 465
SWIPE_MIN_DISTANCE = 65

DOCK_RECT = pygame.Rect(29, 120, 742, 314)
DOCK_CLOSE = pygame.Rect(717, 136, 39, 38)
DOCK_ITEMS = (
    ("HOME", "menu", "home"),
    ("RADIO", "radio", "radio"),
    ("BIBLE", "bible", "bible"),
    ("YOUTUBE", "youtube", "youtube"),
    ("FAVORITES", "favorites", "favorites"),
    ("CLOCK", "clock", "clock"),
    ("WEATHER", "forecast", "weather"),
    ("SETTINGS", "settings", "settings"),
)
DOCK_TILES = {
    name: pygame.Rect(51 + (i % 4) * 182, 193 + (i // 4) * 94, 151, 78)
    for i, (name, _, _) in enumerate(DOCK_ITEMS)
}


def _text(screen, font, value, x, y, color=INK, width=None):
    value = str(value or "")
    if width:
        text = value
        while text and font.render(text, True, color).get_width() > width:
            text = text[:-1]
        if len(text) < len(value):
            value = text.rstrip() + "…" if text else ""
    if value:
        screen.blit(font.render(value, True, color), (x, y))


def to_source(pos):
    """Map a visible touch to native coordinates used by existing page handlers."""
    x, y = pos
    if NEW_CONTENT.collidepoint(x, y):
        return (
            OLD_CONTENT.x + round((x - NEW_CONTENT.x) * OLD_CONTENT.w / NEW_CONTENT.w),
            OLD_CONTENT.y + round((y - NEW_CONTENT.y) * OLD_CONTENT.h / NEW_CONTENT.h),
        )
    return pos


def from_source(pos):
    x, y = pos
    return (
        NEW_CONTENT.x + round((x - OLD_CONTENT.x) * NEW_CONTENT.w / OLD_CONTENT.w),
        NEW_CONTENT.y + round((y - OLD_CONTENT.y) * NEW_CONTENT.h / OLD_CONTENT.h),
    )


def layout(screen):
    """Crop the stale sidebar and expand the existing native content to 768px."""
    content = pygame.Surface(OLD_CONTENT.size)
    content.blit(screen, (0, 0), OLD_CONTENT)
    expanded = pygame.transform.smoothscale(content, NEW_CONTENT.size)
    screen.fill(BG)
    screen.blit(expanded, NEW_CONTENT.topleft)
    pygame.draw.line(screen, (35, 35, 35), (0, 64), (800, 64), 1)


def draw_topbar(screen, font, small, tiny, active_page, dock_open=False):
    """Minimal header; CAST and PHOTO buttons are drawn separately at fixed slots."""
    pygame.draw.rect(screen, BG, pygame.Rect(0, 0, 800, 65))
    pygame.draw.line(screen, (42, 42, 42), (0, 64), (799, 64), 1)
    pygame.draw.rect(
        screen, (47, 47, 47) if dock_open else (19, 19, 19),
        MENU_BUTTON, border_radius=12,
    )
    pygame.draw.rect(screen, ACCENT if dock_open else EDGE,
                     MENU_BUTTON, 1, border_radius=12)
    for y in (21, 28, 35):
        pygame.draw.line(screen, INK, (25, y), (47, y), 2)
    _text(screen, font, "PiRadio 7", 74, 13, INK, 205)

    label = {
        "menu": "HOME", "radio": "RADIO", "youtube": "YOUTUBE",
        "youtube_player": "NOW PLAYING", "bible": "BIBLE",
        "favorites": "FAVORITES", "clock": "CLOCK", "forecast": "WEATHER",
        "cast": "GUEST CAST", "settings": "SETTINGS",
    }.get(active_page, active_page.upper())
    _text(screen, tiny, label, 319, 23, ACCENT, 154)
    _text(screen, small, datetime.now().strftime("%H:%M"),
          506, 16, INK, 65)

    # The tiny bottom-edge handle is touch-enabled through a swipe gesture.
    pygame.draw.rect(screen, (100, 100, 100), pygame.Rect(357, 469, 86, 5),
                     border_radius=3)


def dock_hit(pos):
    """Return a page identifier, 'dismiss' or None."""
    if DOCK_CLOSE.collidepoint(pos):
        return "dismiss"
    for name, page, _icon in DOCK_ITEMS:
        if DOCK_TILES[name].collidepoint(pos):
            return page
    if not DOCK_RECT.collidepoint(pos):
        return "dismiss"
    return None


def draw_dock(screen, font, small, tiny, active_page):
    """Floating 4×2 navigation grid, visible only when invited."""
    from fa_icons import draw_icon

    veil = pygame.Surface((800, 480), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 194))
    screen.blit(veil, (0, 0))
    pygame.draw.rect(screen, (15, 15, 15), DOCK_RECT, border_radius=23)
    pygame.draw.rect(screen, (101, 101, 101), DOCK_RECT, 1, border_radius=23)

    _text(screen, font, "Navigate", 52, 139, INK, 335)
    _text(screen, tiny, "Tap a destination • tap outside to close",
          190, 149, MUTED, 432)
    pygame.draw.rect(screen, (36, 36, 36), DOCK_CLOSE, border_radius=10)
    pygame.draw.line(screen, INK,
                     (DOCK_CLOSE.x + 12, DOCK_CLOSE.y + 12),
                     (DOCK_CLOSE.right - 12, DOCK_CLOSE.bottom - 12), 2)
    pygame.draw.line(screen, INK,
                     (DOCK_CLOSE.right - 12, DOCK_CLOSE.y + 12),
                     (DOCK_CLOSE.x + 12, DOCK_CLOSE.bottom - 12), 2)

    for name, target, icon in DOCK_ITEMS:
        rect = DOCK_TILES[name]
        selected = active_page == target or (
            target == "youtube" and active_page == "youtube_player"
        )
        pygame.draw.rect(screen,
                         (32, 67, 72) if selected else (31, 31, 31),
                         rect, border_radius=17)
        pygame.draw.rect(screen,
                         ACCENT if selected else (80, 80, 80),
                         rect, 1, border_radius=17)
        try:
            draw_icon(screen, icon, (rect.centerx, rect.y + 28),
                      23, INK)
        except (pygame.error, OSError):
            pass
        label = tiny.render(name, True, INK)
        screen.blit(label,
                    label.get_rect(center=(rect.centerx, rect.y + 59)))
    return True

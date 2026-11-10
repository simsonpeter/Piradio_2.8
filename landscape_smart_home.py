"""PiRadio 7 — Midnight Home dashboard (physical 800x480 coordinates).

Pygame-only renderer: no media engine, network requests, or remote calls.
The caller supplies existing cached weather and unified playback metadata.
The floating menu and global top bar remain owned by landscape_immersive.
"""
from datetime import datetime
import math
import pygame

from fa_icons import draw_icon

BG = (0, 0, 0)
CARD = (16, 19, 22)
BORDER = (55, 63, 68)
WHITE = (246, 248, 249)
MUTED = (163, 172, 179)
CYAN = (71, 216, 228)
SOFT_BLUE = (108, 160, 201)
CLOCK = pygame.Rect(18, 76, 451, 176)
WEATHER = pygame.Rect(481, 76, 301, 176)
MEDIA = pygame.Rect(18, 263, 764, 112)
MEDIA_ART = pygame.Rect(35, 278, 83, 82)
MEDIA_PAUSE = pygame.Rect(695, 294, 68, 52)
SHORTCUTS = (
    ("RADIO", "radio", "radio"),
    ("BIBLE", "bible", "bible"),
    ("YOUTUBE", "youtube", "youtube"),
    ("PHOTOS", "photo_frame", "image"),
    ("FAVOURITES", "favorites", "favorites"),
)
SHORTCUT_RECTS = {
    name: pygame.Rect(18 + index * 155, 385, 144, 73)
    for index, (name, _, _) in enumerate(SHORTCUTS)
}


def _card(surface, rect, radius=20):
    pygame.draw.rect(surface, CARD, rect, border_radius=radius)
    pygame.draw.rect(surface, BORDER, rect, 1, border_radius=radius)


def _text(surface, font, value, x, y, color=WHITE, width=None):
    value = str(value or "")
    original = value
    if width:
        while value and font.render(value, True, color).get_width() > width:
            value = value[:-1]
        if value != original:
            while value and font.render(value + "…", True, color).get_width() > width:
                value = value[:-1]
            value = value.rstrip() + "…" if value else ""
    if value:
        surface.blit(font.render(value, True, color), (x, y))


def _icon(surface, name, center, size, color=WHITE):
    try:
        draw_icon(surface, name, center, size, color)
    except (ValueError, pygame.error, AttributeError):
        pygame.draw.circle(surface, color, center, max(4, size // 4), 2)


def _time_of_day(now):
    hour = now.hour
    if hour < 12:
        return "GOOD MORNING"
    if hour < 17:
        return "GOOD AFTERNOON"
    return "GOOD EVENING"


def _weather_label(weather_type, available):
    if not available:
        return "WEATHER UNAVAILABLE"
    label = str(weather_type or "Current conditions").replace("_", " ").strip()
    return label.title() if label else "Current conditions"


def _temperature(value, available):
    if not available or value is None:
        return "--°"
    try:
        number = float(value)
        if not math.isfinite(number):
            return "--°"
        return f"{round(number):d}°"
    except (ValueError, TypeError, OverflowError):
        return "--°"


def _source_label(source):
    return {
        "radio": "INTERNET RADIO", "youtube_audio": "YOUTUBE AUDIO",
        "youtube_video": "YOUTUBE VIDEO", "bible": "TAMIL BIBLE",
        "guest_audio": "PHONE AUDIO", "guest_video": "PHONE VIDEO",
        "guest_photos": "PHONE PHOTOS", "screen_mirror": "SCREEN MIRROR",
    }.get(source, "NOW PLAYING")


def draw(surface, font, small, tiny, media=None, *, temperature=None,
         weather_type=None, weather_available=False, city="",
         updated_at=None, now=None, artwork=None):
    """Draw under the existing 65px top bar, without altering audio state."""
    media = media or {}
    now = now or datetime.now()
    surface.fill(BG, pygame.Rect(0, 65, 800, 415))

    # Focus clock: use clean grayscale instead of the washed-out blue panels.
    _card(surface, CLOCK)
    _text(surface, tiny, _time_of_day(now), 39, 93, CYAN, 240)
    clock_font = pygame.font.Font(None, 100)
    _text(surface, clock_font, now.strftime("%H:%M"), 37, 112, WHITE, 392)
    _text(surface, small, now.strftime("%A, %d %B %Y"), 41, 213, MUTED, 400)

    _card(surface, WEATHER)
    _text(surface, tiny, "LOCAL WEATHER", 499, 95, CYAN, 250)
    temp_font = pygame.font.Font(None, 79)
    _text(surface, temp_font, _temperature(temperature, weather_available),
          497, 123, WHITE, 160)
    _text(surface, small, _weather_label(weather_type, weather_available),
          626, 146, MUTED, 140)
    _text(surface, small, city or "Set your city", 499, 205, WHITE, 260)
    if not weather_available:
        _text(surface, tiny, "Tap to check weather", 628, 183, MUTED, 145)

    # One media source only, from media_session; never show stale station art.
    _card(surface, MEDIA, 18)
    source = str(media.get("source") or "radio")
    playing, paused = bool(media.get("playing")), bool(media.get("paused"))
    title = str(media.get("title") or "Choose a station")
    pygame.draw.rect(surface, (33, 38, 42), MEDIA_ART, border_radius=14)
    use_art = source in ("radio", "youtube_audio") and artwork is not None
    if use_art:
        try:
            w, h = artwork.get_size()
            scale = min(74 / w, 74 / h)
            image = pygame.transform.smoothscale(
                artwork, (max(1, round(w * scale)), max(1, round(h * scale))))
            surface.blit(image, image.get_rect(center=MEDIA_ART.center))
        except (ZeroDivisionError, ValueError, AttributeError, pygame.error):
            use_art = False
    if not use_art:
        icon = {
            "radio": "radio", "youtube_audio": "youtube",
            "youtube_video": "youtube", "bible": "bible",
            "guest_video": "film", "guest_audio": "music",
            "guest_photos": "image", "screen_mirror": "monitor",
        }.get(source, "music")
        _icon(surface, icon, MEDIA_ART.center, 43)
    _text(surface, tiny, _source_label(source), 134, 278, CYAN, 525)
    _text(surface, font, title, 134, 302, WHITE, 540)
    status = "PAUSED" if paused else ("PLAYING" if playing else "READY")
    if media.get("minimized") and playing:
        status = "PLAYING IN BACKGROUND"
    _text(surface, tiny, status + "  ·  TAP FOR PLAYER",
          136, 346, MUTED, 490)
    pygame.draw.rect(surface, WHITE, MEDIA_PAUSE, border_radius=16)
    _icon(surface, "pause" if playing else "play",
          MEDIA_PAUSE.center, 30, (20, 22, 24))

    # Five deliberate, spacious touch targets instead of the permanent sidebar.
    for name, target, icon in SHORTCUTS:
        rect = SHORTCUT_RECTS[name]
        _card(surface, rect, 15)
        _icon(surface, icon, (rect.x + 36, rect.y + 34), 27, CYAN)
        _text(surface, tiny, name, rect.x + 60, rect.y + 29, WHITE, 82)
    return True


def hit(pos):
    """Return one action per actual 800x480 touch; no old coordinate scaling."""
    if MEDIA_PAUSE.collidepoint(pos):
        return ("toggle", None)
    if MEDIA.collidepoint(pos):
        return ("now_playing", None)
    if CLOCK.collidepoint(pos):
        return ("clock", None)
    if WEATHER.collidepoint(pos):
        return ("forecast", None)
    for name, target, _icon_name in SHORTCUTS:
        if SHORTCUT_RECTS[name].collidepoint(pos):
            return ("page", target)
    return None

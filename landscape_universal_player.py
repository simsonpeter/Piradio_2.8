"""PiRadio 7 - immersive 800x480 Universal Now Playing screen.

This draws in *physical screen coordinates* after the legacy content has been
expanded by landscape_immersive.layout(). It must not handle media itself.
State comes from media_session; commands go to control_active_media().
"""
import math

import pygame

from fa_icons import draw_icon

WHITE = (247, 247, 247)
SOFT = (174, 178, 181)
DIM = (114, 120, 125)
CYAN = (65, 218, 230)
DARK = (13, 15, 17)
PANEL = pygame.Rect(18, 71, 764, 390)
ART = pygame.Rect(37, 94, 289, 282)
ART_IMAGE = pygame.Rect(51, 108, 261, 254)
SOURCE = pygame.Rect(356, 96, 203, 31)
BACK = pygame.Rect(718, 91, 42, 42)
FULL_VIDEO = pygame.Rect(563, 95, 145, 40)
TRACK = pygame.Rect(355, 248, 397, 10)
TRACK_TOUCH = TRACK.inflate(0, 26)
PREV = pygame.Rect(359, 308, 78, 55)
TOGGLE = pygame.Rect(447, 297, 101, 72)
NEXT = pygame.Rect(558, 308, 78, 55)
STOP = pygame.Rect(658, 308, 91, 55)
VOLUME = pygame.Rect(461, 415, 283, 11)
VOLUME_TOUCH = VOLUME.inflate(0, 29)
BACK_BG = (30, 34, 38)

SOURCES = {
    "radio": ("INTERNET RADIO", "radio"),
    "youtube_audio": ("YOUTUBE AUDIO", "youtube"),
    "youtube_video": ("YOUTUBE VIDEO", "youtube"),
    "bible": ("TAMIL BIBLE", "bible"),
    "guest_audio": ("GUEST AUDIO", "music"),
    "guest_video": ("GUEST VIDEO", "film"),
    "guest_photos": ("PHOTO SLIDESHOW", "image"),
    "screen_mirror": ("PHONE SCREEN", "monitor"),
}
MPV_VIDEO = ("youtube_video", "guest_video")
NO_SEEK = ("radio", "bible", "guest_photos", "screen_mirror")


def _text(surface, font, text, x, y, color=WHITE, width=0):
    message = str(text or "")
    if width:
        original = message
        while message and font.render(message, True, color).get_width() > width:
            message = message[:-1]
        if message != original:
            while message and font.render(message + "…", True, color).get_width() > width:
                message = message[:-1]
            message = message.rstrip() + "…" if message else ""
    if message:
        surface.blit(font.render(message, True, color), (x, y))


def _wrap_two_lines(font, text, max_width):
    """Fit metadata into two stable lines, including Tamil script."""
    text = str(text or "PiRadio")
    if font.render(text, True, WHITE).get_width() <= max_width:
        return text, ""
    words = text.split()
    first = ""
    if len(words) > 1:
        for word in words:
            trial = (first + " " + word).strip()
            if first and font.render(trial, True, WHITE).get_width() > max_width:
                break
            first = trial
    if not first or first == text:
        first = ""
        for character in text:
            trial = first + character
            if first and font.render(trial, True, WHITE).get_width() > max_width:
                break
            first = trial
    return first, text[len(first):].strip()


def _duration(seconds):
    try:
        value = float(seconds)
    except (ValueError, TypeError, OverflowError):
        return "--:--"
    if not math.isfinite(value) or value < 0:
        return "--:--"
    value = int(value)
    hours, remainder = divmod(value, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def _can_seek(state):
    source = str(state.get("source") or "radio")
    try:
        duration = float(state.get("duration") or 0)
        return (source not in NO_SEEK and bool(state.get("seekable"))
                and math.isfinite(duration) and duration > 0)
    except (ValueError, TypeError, OverflowError):
        return False


def _icon(surface, name, rect, size=30, color=WHITE):
    draw_icon(surface, name, rect.center, size, color)


def _button(surface, rect, label, font, *, primary=False, danger=False):
    bg = WHITE if primary else ((65, 30, 32) if danger else (34, 37, 40))
    fg = DARK if primary else WHITE
    pygame.draw.rect(surface, bg, rect, border_radius=16)
    pygame.draw.rect(surface, (108, 112, 115) if not primary else WHITE,
                     rect, 1, border_radius=16)
    glyph = font.render(label, True, fg)
    surface.blit(glyph, glyph.get_rect(center=rect.center))


def _artwork(surface, artwork, source, font):
    pygame.draw.rect(surface, (22, 25, 28), ART, border_radius=25)
    pygame.draw.rect(surface, (69, 75, 79), ART, 1, border_radius=25)
    if source in ("radio", "youtube_audio") and artwork is not None:
        try:
            width, height = artwork.get_size()
            if width > 0 and height > 0:
                factor = min(ART_IMAGE.width / width, ART_IMAGE.height / height)
                image = pygame.transform.smoothscale(
                    artwork, (max(1, round(width * factor)),
                              max(1, round(height * factor))))
                surface.blit(image, image.get_rect(center=ART_IMAGE.center))
                return
        except (AttributeError, ValueError, pygame.error):
            pass
    source_name, icon_name = SOURCES.get(source, ("PI RADIO MEDIA", "music"))
    pygame.draw.circle(surface, (35, 40, 43), ART.center, 93)
    pygame.draw.circle(surface, (68, 77, 81), ART.center, 92, 2)
    pygame.draw.circle(surface, (65, 218, 230), ART.center, 68, 1)
    _icon(surface, icon_name, pygame.Rect(ART.centerx-37, ART.centery-37, 74, 74),
          size=64, color=WHITE)
    _text(surface, font, source_name, 68, 342, CYAN, 233)


def draw(surface, font, small, tiny, state, artwork=None):
    """Render current source; callers must draw the top bar separately."""
    state = state or {}
    source = str(state.get("source") or "radio")
    source_name, _ = SOURCES.get(source, ("PI RADIO MEDIA", "music"))
    playing = bool(state.get("playing"))
    paused = bool(state.get("paused"))
    minimized = bool(state.get("minimized"))
    available = playing or paused
    surface.fill((0, 0, 0), rect=PANEL)
    pygame.draw.rect(surface, DARK, PANEL, border_radius=24)
    pygame.draw.rect(surface, (55, 62, 66), PANEL, 1, border_radius=24)
    pygame.draw.rect(surface, (27, 41, 46), SOURCE, border_radius=13)
    _text(surface, tiny, source_name, SOURCE.x + 14, SOURCE.y + 9, CYAN, SOURCE.w-24)
    _button(surface, BACK, "X", small)

    if source in MPV_VIDEO and available:
        _button(surface, FULL_VIDEO, "FULL VIDEO", tiny)

    _artwork(surface, artwork, source, tiny)
    title = state.get("title") or ("Choose a station" if source == "radio" else "PiRadio")
    line1, line2 = _wrap_two_lines(font, title, 385)
    _text(surface, font, line1, 354, 147, WHITE, 385)
    if line2:
        _text(surface, small, line2, 354, 180, WHITE, 385)
    status = "PAUSED" if paused else ("PLAYING" if playing else "READY")
    if minimized and playing:
        status = "AUDIO IN BACKGROUND"
    _text(surface, small, status, 355, 213, SOFT, 380)

    seek = _can_seek(state)
    pygame.draw.rect(surface, (64, 68, 71), TRACK, border_radius=5)
    if seek:
        position = max(0.0, float(state.get("position") or 0))
        duration = float(state.get("duration"))
        progress = max(0.0, min(1.0, position / duration))
        if progress:
            pygame.draw.rect(
                surface, CYAN,
                pygame.Rect(TRACK.x, TRACK.y,
                            max(2, round(TRACK.w * progress)), TRACK.h),
                border_radius=5,
            )
        pygame.draw.circle(surface, WHITE,
                           (TRACK.x + round(TRACK.w * progress), TRACK.centery), 6)
        _text(surface, tiny, _duration(position), TRACK.x, 267, SOFT, 105)
        end_text = _duration(duration)
        _text(surface, tiny, end_text, 683, 267, SOFT, 65)
    else:
        _text(surface, tiny, "LIVE" if source == "radio" else "TIMELINE UNAVAILABLE",
              357, 270, CYAN if source == "radio" else DIM, 355)

    can_skip = source != "screen_mirror"
    if can_skip:
        label_prev = "-10s" if source in MPV_VIDEO + ("guest_audio",) else "PREV"
        label_next = "+10s" if source in MPV_VIDEO + ("guest_audio",) else "NEXT"
        _button(surface, PREV, label_prev, tiny)
        _button(surface, NEXT, label_next, tiny)
    _button(surface, TOGGLE, "PLAY" if paused or not playing else "PAUSE",
            small, primary=True)
    if available:
        _button(surface, STOP, "STOP", small, danger=True)

    _text(surface, tiny, "VOLUME", 355, 395, SOFT, 100)
    pygame.draw.rect(surface, (65, 70, 73), VOLUME, border_radius=6)
    try:
        level = max(0, min(100, int(state.get("volume") or 0)))
    except (ValueError, TypeError, OverflowError):
        level = 0
    if level:
        pygame.draw.rect(surface, CYAN,
                         pygame.Rect(VOLUME.x, VOLUME.y,
                                     max(2, round(VOLUME.width * level / 100)),
                                     VOLUME.height), border_radius=6)
    pygame.draw.circle(surface, WHITE,
                       (VOLUME.x + round(VOLUME.width * level / 100), VOLUME.centery), 7)
    _text(surface, small, f"{level}%", 688, 388, WHITE, 58)
    return True


def hit(pos, state):
    """Physical 800x480 targets. Never route invisible controls."""
    state = state or {}
    if not PANEL.collidepoint(pos):
        return None
    source = str(state.get("source") or "radio")
    available = bool(state.get("playing") or state.get("paused"))
    if BACK.collidepoint(pos):
        return "back", None
    if available and source in MPV_VIDEO and FULL_VIDEO.collidepoint(pos):
        return "restore", None
    if VOLUME_TOUCH.collidepoint(pos):
        ratio = (pos[0] - VOLUME.x) / VOLUME.width
        return "volume", max(0, min(100, int(round(ratio * 100))))
    if TRACK_TOUCH.collidepoint(pos):
        if _can_seek(state):
            duration = float(state.get("duration"))
            ratio = max(0, min(1, (pos[0] - TRACK.x) / TRACK.w))
            return "seek", ratio * duration
        return "consume", None
    if PREV.collidepoint(pos):
        return ("prev", None) if source != "screen_mirror" else ("consume", None)
    if NEXT.collidepoint(pos):
        return ("next", None) if source != "screen_mirror" else ("consume", None)
    if TOGGLE.collidepoint(pos):
        return "toggle", None
    if STOP.collidepoint(pos):
        return ("stop", None) if available else ("consume", None)
    return "consume", None

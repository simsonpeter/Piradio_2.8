"""PiRadio 7 native dedicated YouTube Now Playing screen (800x480).

The YouTube search list is a separate page. This drawing module owns no
playback; the existing VLC / MPV engines in touch_radio.py remain in charge.
All touch targets are native 800x480 coordinates, not stretched 320x480.
"""
import math
import pygame

INK = (247, 247, 247)
MUTED = (176, 176, 176)
QUIET = (117, 117, 117)
ACCENT = (55, 215, 230)
CARD = (16, 16, 16)
EDGE = (72, 72, 72)
BACK = (0, 0, 0)

PANEL = pygame.Rect(158, 74, 629, 311)
ART = pygame.Rect(181, 137, 186, 196)
IMAGE = pygame.Rect(191, 148, 165, 172)
BODY = pygame.Rect(379, 137, 393, 196)
BACK_TO_SEARCH = pygame.Rect(643, 84, 128, 39)
VIDEO_BUTTON = pygame.Rect(525, 84, 110, 39)
TRACK = pygame.Rect(401, 277, 346, 9)
TRACK_HIT = TRACK.inflate(0, 26)
PREVIOUS = pygame.Rect(399, 311, 78, 48)
PAUSE = pygame.Rect(484, 307, 87, 54)
NEXT = pygame.Rect(579, 311, 78, 48)
STOP = pygame.Rect(665, 311, 87, 48)


def _draw_text(s, font, value, pos, color=INK, max_width=0):
    text = str(value or "")
    if not text:
        return 0
    original = text
    if max_width:
        while text and font.render(text, True, color).get_width() > max_width:
            text = text[:-1]
        if text != original:
            while text and font.render(text + "…", True, color).get_width() > max_width:
                text = text[:-1]
            text = text.rstrip() + "…" if text else "…"
    item = font.render(text, True, color)
    s.blit(item, pos)
    return item.get_width()


def _time(seconds):
    try:
        value = float(seconds)
        if not math.isfinite(value) or value < 0:
            return "--:--"
        s = int(value)
        return f"{s // 3600}:{(s // 60) % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"
    except (TypeError, ValueError, OverflowError):
        return "--:--"


def _button(s, font, rect, label, primary=False, danger=False):
    pygame.draw.rect(s, (235, 235, 235) if primary else
                     ((76, 33, 33) if danger else (32, 32, 32)),
                     rect, border_radius=12)
    pygame.draw.rect(s, (212, 212, 212) if primary else EDGE,
                     rect, 1, border_radius=12)
    text = font.render(label, True, BACK if primary else INK)
    s.blit(text, text.get_rect(center=rect.center))


def draw(surface, font, small, tiny, status, art=None):
    """Draw the 7-inch YouTube Now Playing page inside the normal PiRadio shell.

    status is plain data: {playing, paused, title, channel, position, duration,
    seekable, mode: 'audio'|'video', video_available, queue_position, queue_total}.
    """
    pygame.draw.rect(surface, CARD, PANEL, border_radius=19)
    pygame.draw.rect(surface, EDGE, PANEL, 1, border_radius=19)
    _draw_text(surface, font, "YOUTUBE  /  NOW PLAYING", (180, 91), INK, 342)
    _button(surface, tiny, BACK_TO_SEARCH, "SEARCH")
    _button(surface, tiny, VIDEO_BUTTON, "FULL VIDEO" if status.get("mode") == "audio"
            else "FULLSCREEN")
    pygame.draw.line(surface, (46, 46, 46), (178, 128), (766, 128), 1)

    pygame.draw.rect(surface, (25, 25, 25), ART, border_radius=17)
    pygame.draw.rect(surface, (64, 64, 64), ART, 1, border_radius=17)
    if art is not None and status.get("mode") == "audio":
        try:
            scale = min(IMAGE.w / art.get_width(), IMAGE.h / art.get_height())
            target = pygame.transform.smoothscale(
                art, (max(1, int(art.get_width() * scale)),
                      max(1, int(art.get_height() * scale))))
            surface.blit(target, target.get_rect(center=IMAGE.center))
        except (ValueError, pygame.error, ZeroDivisionError, AttributeError):
            art = None
    if art is None or status.get("mode") != "audio":
        # Show a clean play symbol instead of the previous radio station logo.
        pygame.draw.circle(surface, (221, 221, 221), IMAGE.center, 54)
        cx, cy = IMAGE.center
        pygame.draw.polygon(surface, (15, 15, 15),
                            [(cx - 14, cy - 25), (cx + 29, cy),
                             (cx - 14, cy + 25)])
    _draw_text(surface, small, "YOUTUBE AUDIO" if status.get("mode") == "audio"
               else "YOUTUBE VIDEO", (202, 339), ACCENT, 160)

    pygame.draw.rect(surface, (20, 20, 20), BODY, border_radius=14)
    pygame.draw.rect(surface, (47, 47, 47), BODY, 1, border_radius=14)
    track = "VIDEO" if status.get("mode") == "video" else "AUDIO"
    subtitle = "PLAYING" if status.get("playing") and not status.get("paused") else (
        "PAUSED" if status.get("paused") else "READY")
    _draw_text(surface, tiny, f"{track}  ·  {subtitle}", (399, 151), ACCENT, 340)

    full_title = str(status.get("title") or "Choose a YouTube result")
    # Two title lines with support for Tamil/English Unicode font adapters.
    first = full_title
    while len(first) > 1 and font.render(first, True, INK).get_width() > 345:
        first = first[:-1]
    if len(first) < len(full_title):
        boundary = first.rfind(" ")
        if boundary > 12:
            first = first[:boundary]
    remainder = full_title[len(first):].strip()
    _draw_text(surface, font, first, (399, 183), INK, 345)
    if remainder:
        _draw_text(surface, small, remainder, (399, 211), INK, 345)
    else:
        _draw_text(surface, tiny, status.get("channel") or "Tamil & world music",
                   (400, 219), MUTED, 340)
    queue_total = max(0, int(status.get("queue_total") or 0))
    if queue_total:
        _draw_text(surface, tiny,
                   f"QUEUE {status.get('queue_position', 1)}/{queue_total}",
                   (400, 244), QUIET, 340)

    position = status.get("position", 0)
    duration = status.get("duration", 0)
    can_seek = bool(status.get("seekable") and duration and float(duration) > 0)
    pygame.draw.rect(surface, (70, 70, 70), TRACK, border_radius=5)
    if can_seek:
        ratio = max(0, min(1, float(position or 0) / float(duration)))
        if ratio:
            fill = pygame.Rect(TRACK.x, TRACK.y,
                               max(3, int(TRACK.w * ratio)), TRACK.h)
            pygame.draw.rect(surface, ACCENT, fill, border_radius=5)
        knob_x = TRACK.x + int(TRACK.w * ratio)
        pygame.draw.circle(surface, INK, (knob_x, TRACK.centery), 7)
        _draw_text(surface, tiny, _time(position), (401, 289), MUTED, 96)
        _draw_text(surface, tiny, _time(duration), (679, 289), MUTED, 71)
    else:
        _draw_text(surface, tiny, "Timeline unavailable for this stream",
                   (401, 285), MUTED, 345)

    _button(surface, tiny, PREVIOUS, "-10s" if status.get("mode") == "video" else "PREV")
    _button(surface, small, PAUSE, "PLAY" if status.get("paused") else "PAUSE",
            primary=True)
    _button(surface, tiny, NEXT, "+10s" if status.get("mode") == "video" else "NEXT")
    _button(surface, tiny, STOP, "STOP", danger=True)
    return True


def hit(pos, status):
    """Recognize only visible controls (never forward taps to stale legacy UI)."""
    if not PANEL.collidepoint(pos):
        return None
    if BACK_TO_SEARCH.collidepoint(pos):
        return ("search", None)
    if VIDEO_BUTTON.collidepoint(pos):
        return ("video", None)
    if PREVIOUS.collidepoint(pos):
        return ("prev", None)
    if PAUSE.collidepoint(pos):
        return ("pause", None)
    if NEXT.collidepoint(pos):
        return ("next", None)
    if STOP.collidepoint(pos):
        return ("stop", None)
    duration = status.get("duration", 0) or 0
    if TRACK_HIT.collidepoint(pos) and status.get("seekable") and float(duration) > 0:
        ratio = max(0, min(1, (pos[0] - TRACK.x) / TRACK.w))
        return ("seek", float(duration) * ratio)
    return ("consume", None)

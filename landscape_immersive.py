"""PiRadio 7 immersive 800x480 interface.

Full-width radio and Home screens, plus a hidden navigation drawer. The legacy
secondary views (Tamil Bible, YouTube, Cast, settings) are composited into a
wider viewport with an inverse touch-coordinate transform. Playback ownership
and API routing stay in touch_radio.py.

No permanent sidebar; navigation is always available via the visible MENU
button or upward swipe from the bottom grab handle.
"""
from datetime import datetime
import math

import pygame
from fa_icons import draw_icon

BLACK = (0, 0, 0)
WHITE = (250, 250, 250)
MUTED = (164, 164, 164)
DIM = (106, 106, 106)
ACCENT = (63, 211, 227)
PANEL = (16, 16, 16)
BORDER = (64, 64, 64)

# Public visible touch targets.
MENU_BUTTON = pygame.Rect(12, 7, 58, 40)
NAV_HANDLE = pygame.Rect(343, 463, 114, 17)
DRAWER = pygame.Rect(15, 183, 770, 297)

# Native full-width content and mini footer, after sidebar removal.
CONTENT_SOURCE = pygame.Rect(157, 72, 632, 316)
CONTENT_DEST = pygame.Rect(20, 72, 760, 316)
MINI_SOURCE = pygame.Rect(157, 399, 630, 65)
MINI_DEST = pygame.Rect(22, 395, 756, 65)

# Immersive Radio page transport.
RADIO_ART = pygame.Rect(34, 100, 299, 281)
RADIO_INFO = pygame.Rect(351, 100, 414, 281)
RADIO_PREV = pygame.Rect(435, 278, 63, 58)
RADIO_PAUSE = pygame.Rect(519, 271, 78, 70)
RADIO_NEXT = pygame.Rect(618, 278, 63, 58)
RADIO_VOLUME = pygame.Rect(389, 361, 326, 10)
RADIO_SEEK = pygame.Rect(387, 248, 332, 10)
RADIO_FOOTER = pygame.Rect(24, 409, 751, 48)

HOME_PAGES = (
    ("HOME", "home", "menu"),
    ("RADIO", "radio", "radio"),
    ("BIBLE", "bible", "bible"),
    ("YOUTUBE", "youtube", "youtube"),
    ("FAVORITES", "favorites", "favorites"),
    ("CLOCK", "clock", "clock"),
    ("WEATHER", "weather", "forecast"),
    ("SETTINGS", "settings", "settings"),
)
HOME_TILES = tuple(
    (pygame.Rect(25 + (i % 4) * 192, 89 + (i // 4) * 145, 174, 129), page)
    for i, page in enumerate(HOME_PAGES)
)
DOCK_TILES = tuple(
    (pygame.Rect(37 + (i % 4) * 190, 231 + (i // 4) * 105, 155, 84), page)
    for i, page in enumerate(HOME_PAGES)
)
HOME_MINI = pygame.Rect(23, 397, 754, 65)
HOME_OPEN = pygame.Rect(34, 401, 500, 55)
HOME_PREV = pygame.Rect(578, 411, 49, 42)
HOME_PAUSE = pygame.Rect(638, 407, 53, 49)
HOME_NEXT = pygame.Rect(706, 411, 49, 42)


def _text(s, font, value, xy, color=WHITE, max_width=None):
    value = str(value or "")
    if not value:
        return
    if max_width:
        raw = value
        while value and font.render(value, True, color).get_width() > max_width:
            value = value[:-1]
        if value != raw:
            while value and font.render(value + "…", True, color).get_width() > max_width:
                value = value[:-1]
            value = (value.rstrip() + "…") if value else "…"
    s.blit(font.render(value, True, color), xy)


def _icon(surface, name, rect, size=27, color=WHITE):
    """Crisp built-in outlines; no system icon-font dependency."""
    x, y = rect.center
    k = max(12, int(size * 0.46))
    line = max(2, int(size / 14))
    if name in ("home", "house"):
        pygame.draw.lines(surface, color, False,
                          [(x-k, y-2), (x, y-k), (x+k, y-2)], line + 1)
        pygame.draw.lines(surface, color, False,
                          [(x-k+4,y-2),(x-k+4,y+k),(x+k-4,y+k),(x+k-4,y-2)], line)
        pygame.draw.rect(surface, color, (x-4,y+2,8,k-2),line)
    elif name == "radio":
        pygame.draw.rect(surface, color,
                         (x-k,y-k//2,2*k, k+k//2),line,border_radius=5)
        pygame.draw.circle(surface, color, (x+k//3,y+k//3),k//3,line)
        pygame.draw.line(surface,color,(x-k+4,y-k//2),(x+k//2,y-k-5),line)
        pygame.draw.line(surface,color,(x-k+4,y+2),(x-1,y+2),line)
    elif name == "bible":
        pygame.draw.rect(surface, color,(x-k,y-k,2*k,2*k),line,border_radius=4)
        pygame.draw.line(surface,color,(x-k//2,y-k),(x-k//2,y+k),line)
        pygame.draw.line(surface,color,(x+2,y-k//2),(x+2,y+k//2),line)
        pygame.draw.line(surface,color,(x-k//4,y),(x+k//2,y),line)
    elif name == "youtube":
        pygame.draw.rect(surface,color,(x-k-2,y-k//2-5,2*k+4,k+10),
                         line,border_radius=7)
        pygame.draw.polygon(surface,color,
                            [(x-5,y-9),(x+10,y),(x-5,y+9)])
    elif name == "favorites":
        points=[(x,y+k),(x-k,y-1),(x-k,y-k//2),
                (x-k//2,y-k),(x,y-k//2),(x+k//2,y-k),
                (x+k,y-k//2),(x+k,y-1)]
        pygame.draw.lines(surface,color,True,points,line+1)
    elif name == "clock":
        pygame.draw.circle(surface,color,(x,y),k,line)
        pygame.draw.lines(surface,color,False,
                          [(x,y-k//2),(x,y),(x+k//2,y+k//4)],line+1)
    elif name == "weather":
        pygame.draw.circle(surface,color,(x-4,y-4),max(5,k//2),line)
        for dx,dy in ((0,-k),(k,0),(-k,0),(0,k)):
            pygame.draw.line(surface,color,
                             (x-4+dx*3//4,y-4+dy*3//4),
                             (x-4+dx,y-4+dy),line)
        pygame.draw.lines(surface,color,False,
                          [(x-8,y+k//2),(x+11,y+k//2),
                           (x+14,y+k//4)],line+1)
    elif name == "settings":
        pygame.draw.circle(surface,color,(x,y),k//2,line)
        pygame.draw.circle(surface,color,(x,y),max(3,k//6),line)
        for index in range(8):
            radians=2*math.pi*index/8
            start=(int(x+math.cos(radians)*k*0.64),
                   int(y+math.sin(radians)*k*0.64))
            end=(int(x+math.cos(radians)*k),
                 int(y+math.sin(radians)*k))
            pygame.draw.line(surface,color,start,end,line+1)
    elif name in ("prev","next","play","pause"):
        draw_icon(surface,name,rect.center,size,color)
    else:
        draw_icon(surface,name,rect.center,size,color)


def _card(s, rect, fill=PANEL, border=BORDER, radius=19):
    pygame.draw.rect(s, fill, rect, border_radius=radius)
    pygame.draw.rect(s, border, rect, 1, border_radius=radius)


def _clock(seconds):
    try:
        value = float(seconds or 0)
        if not math.isfinite(value) or value < 0:
            return "--:--"
        total = int(value)
        return (f"{total // 3600}:{(total // 60) % 60:02d}:{total % 60:02d}"
                if total >= 3600 else f"{total // 60}:{total % 60:02d}")
    except (ValueError, TypeError, OverflowError):
        return "--:--"


def _cover(s, image, rect):
    """Preserve the logo's aspect ratio and center it in the artwork area."""
    if image is None:
        return False
    try:
        w, h = image.get_size()
        if not w or not h:
            return False
        scale = min((rect.width - 24) / w, (rect.height - 24) / h)
        size = (max(1, int(w * scale)), max(1, int(h * scale)))
        picture = pygame.transform.smoothscale(image, size)
        s.blit(picture, picture.get_rect(center=rect.center))
        return True
    except (AttributeError, pygame.error, ValueError):
        return False


def draw_header(s, font, tiny, page="radio", cast_active=False):
    pygame.draw.rect(s, BLACK, (0, 0, 800, 58))
    pygame.draw.line(s, BORDER, (19, 57), (780, 57), 1)
    _card(s, MENU_BUTTON, (27, 27, 27), BORDER, 11)
    # Simple universally recognized hamburger icon with large touch area.
    for y in (19, 27, 35):
        pygame.draw.line(s, WHITE, (27, y), (55, y), 2)
    _text(s, font, "PiRadio Pro", (84, 14), WHITE, 211)
    _text(s, tiny, page.replace("_", " ").upper(), (329, 20), MUTED, 207)
    _text(s, tiny, datetime.now().strftime("%H:%M"), (612, 20), WHITE, 65)


def draw_handle(s, tiny, opened=False):
    # 17-pixel-high bottom grab zone, always visible outside the footer.
    pygame.draw.rect(s, BLACK, (0, 461, 800, 19))
    line_color = ACCENT if opened else (165, 165, 165)
    pygame.draw.rect(s, line_color, (371, 467, 58, 4), border_radius=3)


def draw_radio(s, font, small, tiny, station, metadata, playing, volume,
               station_logo=None, video_status=None, youtube_audio=False):
    """Large, uncluttered radio/video player with no duplicative mini-player."""
    s.fill(BLACK)
    mpv = video_status if video_status and video_status.get("playing") else None
    title = ((mpv.get("title") or "Media playing") if mpv
             else station.removeprefix("YT: ").strip())
    subtitle = (
        ("Guest Cast" if mpv.get("source", "youtube_video") != "youtube_video" else "YouTube video")
        if mpv else ("YouTube audio" if youtube_audio else "Live radio")
    )
    paused = mpv.get("paused", False) if mpv else not playing
    _card(s, RADIO_ART, (18, 18, 18), (60, 60, 60), 23)
    art_rect = pygame.Rect(54, 118, 260, 242)
    if mpv:
        pygame.draw.circle(s, (47, 47, 47), art_rect.center, 85)
        icon = "youtube" if mpv.get("source", "youtube_video") == "youtube_video" else "radio"
        _icon(s, icon, art_rect, 92)
    elif not _cover(s, station_logo, art_rect):
        pygame.draw.circle(s, (48, 48, 48), art_rect.center, 85)
        _icon(s, "youtube" if youtube_audio else "radio", art_rect, 89)
    _text(s, small, "NOW PLAYING", (100, 350), MUTED, 212)

    _card(s, RADIO_INFO, (12, 12, 12), (60, 60, 60), 23)
    _text(s, tiny, subtitle.upper(), (383, 125), ACCENT, 348)
    _text(s, font, title, (384, 169), WHITE, 344)
    if mpv:
        _text(s, small, "Paused" if paused else
              ("Audio only" if mpv.get("minimized") else "Playing"),
              (386, 213), MUTED, 335)
        duration = float(mpv.get("duration") or 0)
        position = float(mpv.get("position") or 0)
        if duration > 0 and math.isfinite(duration):
            pygame.draw.rect(s, (62, 62, 62), RADIO_SEEK, border_radius=5)
            ratio = max(0, min(1, position / duration))
            pygame.draw.rect(s, ACCENT, (RADIO_SEEK.x, RADIO_SEEK.y,
                                         max(3, int(RADIO_SEEK.w * ratio)), 10),
                             border_radius=5)
            _text(s, tiny, _clock(position), (389, 261), MUTED)
            _text(s, tiny, _clock(duration), (665, 261), MUTED)
    else:
        _text(s, small, (metadata if metadata and metadata != station
                         else "Streaming now" if playing else "Ready to play"),
              (386, 212), MUTED, 350)
        pygame.draw.rect(s, (62, 62, 62), RADIO_VOLUME, border_radius=5)
        pygame.draw.rect(s, ACCENT,
                         (RADIO_VOLUME.x, RADIO_VOLUME.y,
                          max(3, round(RADIO_VOLUME.w * max(0, min(100, volume)) / 100)), 10),
                         border_radius=5)
        _text(s, tiny, f"VOLUME {volume}%", (393, 342), MUTED)

    for rect, icon, primary in (
        (RADIO_PREV, "prev", False),
        (RADIO_PAUSE, "play" if paused else "pause", True),
        (RADIO_NEXT, "next", False),
    ):
        _card(s, rect, WHITE if primary else (34, 34, 34), WHITE if primary else BORDER, 17)
        _icon(s, icon, rect, 34 if primary else 29, BLACK if primary else WHITE)

    pygame.draw.line(s, (40, 40, 40), (28, 401), (771, 401), 1)
    label = "Tap MENU for pages  •  Swipe up to navigate"
    _text(s, tiny, label, (221, 428), MUTED, 488)


def radio_hit(pos, video_status=None):
    if RADIO_PREV.collidepoint(pos):
        return "audio", "prev"
    if RADIO_PAUSE.collidepoint(pos):
        return "audio", "pause"
    if RADIO_NEXT.collidepoint(pos):
        return "audio", "next"
    mpv = video_status if video_status and video_status.get("playing") else None
    if mpv and RADIO_SEEK.inflate(0, 14).collidepoint(pos):
        duration = float(mpv.get("duration") or 0)
        if duration > 0:
            ratio = max(0, min(1, (pos[0] - RADIO_SEEK.x) / RADIO_SEEK.width))
            return "seek", duration * ratio
        return "consume", None
    if not mpv and RADIO_VOLUME.inflate(0, 30).collidepoint(pos):
        value = int(max(0, min(100, (pos[0] - RADIO_VOLUME.x) * 100 / RADIO_VOLUME.width)))
        return "volume", value
    if mpv and RADIO_ART.collidepoint(pos):
        return "restore", None
    return None


def draw_home(s, font, small, tiny, player_title, paused=False,
              source="radio"):
    s.fill(BLACK)
    for rect, (label, icon, page) in HOME_TILES:
        fill = (23, 23, 23) if page in ("radio", "youtube") else PANEL
        _card(s, rect, fill, (65, 65, 65), 18)
        _icon(s, icon, pygame.Rect(rect.x + 25, rect.y + 25, 49, 47), 35)
        _text(s, small, label.title(), (rect.x + 19, rect.bottom - 39), WHITE, 144)
    _card(s, HOME_MINI, (19, 19, 19), BORDER, 16)
    _icon(s, "bible" if source == "bible" else
          ("youtube" if source.startswith("youtube") else "radio"),
          pygame.Rect(43, 409, 38, 39), 31)
    _text(s, small, player_title or "Ready to play", (99, 404), WHITE, 430)
    _text(s, tiny, ("Paused" if paused else "Tap title to open the player"),
          (99, 435), MUTED, 430)
    for rect, icon, primary in (
        (HOME_PREV, "prev", False),
        (HOME_PAUSE, "play" if paused else "pause", True),
        (HOME_NEXT, "next", False)
    ):
        _card(s, rect, WHITE if primary else (35, 35, 35),
              WHITE if primary else BORDER, 11)
        _icon(s, icon, rect, 26, BLACK if primary else WHITE)


def home_hit(pos):
    for rect, (label, _icon_name, page) in HOME_TILES:
        if rect.collidepoint(pos):
            return "page", label
    if HOME_OPEN.collidepoint(pos):
        return "open_player", None
    for name, rect in (("prev", HOME_PREV), ("pause", HOME_PAUSE), ("next", HOME_NEXT)):
        if rect.collidepoint(pos):
            return "audio", name
    return None


def draw_dock(s, font, small, tiny, current_page):
    """Overlay: never draws the old left sidebar."""
    shade = pygame.Surface((800, 480), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 183))
    s.blit(shade, (0, 0))
    _card(s, DRAWER, (19, 19, 19), (104, 104, 104), 24)
    _text(s, font, "NAVIGATE", (38, 195), WHITE)
    _text(s, tiny, "Choose a page", (634, 203), MUTED)
    for rect, (label, icon, page) in DOCK_TILES:
        selected = page == current_page or (
            page == "youtube" and current_page == "youtube_player"
        )
        _card(s, rect, (41, 71, 77) if selected else (34, 34, 34),
              ACCENT if selected else BORDER, 15)
        _icon(s, icon, pygame.Rect(rect.x + 11, rect.y + 16, 38, 36),
              26, ACCENT if selected else WHITE)
        _text(s, small, label.title(), (rect.x + 49, rect.y + 28), WHITE, 98)
    draw_handle(s, tiny, opened=True)


def dock_hit(pos):
    """Returns destination, 'dismiss', or 'consume' while drawer is open."""
    for rect, (_, _icon_name, page) in DOCK_TILES:
        if rect.collidepoint(pos):
            return page
    return "dismiss" if not DRAWER.collidepoint(pos) else "consume"


def to_legacy(pos):
    """Coordinate inverse for both scaled secondary content and mini footer."""
    x, y = pos
    if (CONTENT_DEST.top <= y < CONTENT_DEST.bottom
            or MINI_DEST.top <= y < MINI_DEST.bottom):
        return (max(0, min(799,
                  round(CONTENT_SOURCE.x + (x - CONTENT_DEST.x)
                        * CONTENT_SOURCE.w / CONTENT_DEST.w))),
                y + (MINI_SOURCE.y - MINI_DEST.y
                     if MINI_DEST.top <= y < MINI_DEST.bottom else 0))
    return pos


def compose_page(display, legacy, include_mini=True):
    """Render existing secondary content full width while keeping touch aligned."""
    display.fill(BLACK)
    content = legacy.subsurface(CONTENT_SOURCE)
    display.blit(pygame.transform.smoothscale(
        content, (CONTENT_DEST.width, CONTENT_DEST.height)), CONTENT_DEST.topleft)
    if include_mini:
        mini = legacy.subsurface(MINI_SOURCE)
        display.blit(pygame.transform.smoothscale(
            mini, (MINI_DEST.width, MINI_DEST.height)), MINI_DEST.topleft)


def show_global_mini_on_home(s, font, small, tiny, status):
    """Use live MPV video mini-controls above Home whenever video is minimized."""
    # Home uses its own persistent mini bar; it isn't overwritten with another
    # mini panel. Source data is already surfaced by draw_home.
    return

"""Offline Font Awesome Free 4 icon adapter for PiRadio (pygame).
Install on Raspberry Pi: sudo apt install fonts-font-awesome
Falls back to simple vector shapes when the font is unavailable.
"""
from pathlib import Path
import pygame

FONT_PATHS = (
    "/usr/share/fonts/truetype/font-awesome/fontawesome-webfont.ttf",
    "/usr/share/fonts/opentype/font-awesome/FontAwesome.otf",
    "/usr/share/fonts/truetype/font-awesome/FontAwesome.ttf",
)
# Font Awesome 4 Unicode mappings (icons licensed under SIL OFL).
CODES = {
    "radio": 0xf028, "favorites": 0xf004, "weather": 0xf0c2,
    "clock": 0xf017, "alarm": 0xf0f3, "system": 0xf108,
    "languages": 0xf0ac, "settings": 0xf013, "youtube": 0xf16a,
    "bible": 0xf02d, "library": 0xf00a, "play": 0xf04b,
    "pause": 0xf04c, "prev": 0xf048, "next": 0xf051,
    "volume": 0xf028, "close": 0xf00d, "qr": 0xf029,
    "sun": 0xf185, "moon": 0xf186,
}
_font_cache = {}


def draw_icon(surface, name, center, size, color):
    """Draw a centered icon without changing any touch regions."""
    path = next((p for p in FONT_PATHS if Path(p).is_file()), None)
    if path and name in CODES:
        key = (path, size)
        if key not in _font_cache:
            _font_cache[key] = pygame.font.Font(path, size)
        glyph = _font_cache[key].render(chr(CODES[name]), True, color)
        surface.blit(glyph, glyph.get_rect(center=center))
        return
    # Deterministic vector fallback for media buttons.
    x, y = center
    k = max(4, size // 3)
    if name in ("play", "next", "prev"):
        if name == "prev":
            pygame.draw.rect(surface, color, (x-k-3, y-k, 3, 2*k))
            pygame.draw.polygon(surface, color, [(x+k,y-k),(x-k,y),(x+k,y+k)])
        else:
            pygame.draw.polygon(surface, color, [(x-k,y-k),(x+k,y),(x-k,y+k)])
            if name == "next":
                pygame.draw.rect(surface, color, (x+k+1,y-k,3,2*k))
    elif name == "pause":
        pygame.draw.rect(surface, color, (x-k,y-k, max(3,k//2),2*k))
        pygame.draw.rect(surface, color, (x+k//2,y-k,max(3,k//2),2*k))
    else:
        pygame.draw.circle(surface, color, center, max(5,size//4), 2)

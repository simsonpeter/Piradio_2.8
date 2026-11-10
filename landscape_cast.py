"""Native PiRadio 7-inch Cast pairing screen and global Cast launcher."""
import io
import pygame
import qrcode

CAST_BUTTON = pygame.Rect(689, 9, 100, 36)
RENEW_BUTTON = pygame.Rect(449, 336, 148, 40)
CLOSE_BUTTON = pygame.Rect(609, 336, 153, 40)

WHITE = (246, 246, 246)
MUTED = (171, 171, 171)
ACCENT = (56, 215, 230)
DARK = (12, 12, 12)
EDGE = (69, 69, 69)
_QR_CACHE = {}


def _text(surface, font, value, x, y, color=WHITE, width=None):
    value = str(value or "")
    if not value:
        return
    original = value
    if width is not None:
        while value and font.render(value, True, color).get_width() > width:
            value = value[:-1]
        if value and value != original:
            value = value.rstrip() + "…"
    surface.blit(font.render(value, True, color), (x, y))


def draw_cast_button(surface, font, active=False):
    fill = (35, 89, 96) if active else (28, 28, 28)
    pygame.draw.rect(surface, fill, CAST_BUTTON, border_radius=11)
    pygame.draw.rect(surface, ACCENT if active else EDGE,
                     CAST_BUTTON, 1, border_radius=11)
    text = font.render("CAST", True, WHITE)
    surface.blit(text, text.get_rect(center=CAST_BUTTON.center))


def make_qr(text):
    if text in _QR_CACHE:
        return _QR_CACHE[text]
    if len(_QR_CACHE) > 3:
        _QR_CACHE.clear()
    image = qrcode.make(text, border=2, box_size=7).convert("RGB")
    surface = pygame.image.fromstring(image.tobytes(), image.size, "RGB")
    surface = pygame.transform.smoothscale(surface, (216, 216))
    _QR_CACHE[text] = surface
    return surface


def draw_cast_page(surface, font, small, tiny, pin_state, url):
    outer = pygame.Rect(158, 74, 631, 311)
    pygame.draw.rect(surface, (13, 13, 13), outer, border_radius=20)
    pygame.draw.rect(surface, EDGE, outer, 1, border_radius=20)
    _text(surface, font, "PiRadio Cast · Guest", 176, 86)
    _text(surface, tiny, "Music • Videos • Photos • Android screen", 178, 123, MUTED, 570)

    if not pin_state["active"]:
        _text(surface, small, "Tap CAST above to start a guest session.", 180, 184)
        return

    qr = make_qr(url)
    pygame.draw.rect(surface, WHITE, (175, 146, 224, 225), border_radius=14)
    surface.blit(qr, (179, 150))

    _text(surface, small, "Scan this QR code", 429, 153, WHITE)
    _text(surface, tiny, "Phone and Pi must share the same Wi-Fi", 429, 180, MUTED, 340)
    _text(surface, tiny, url, 429, 197, MUTED, 332)
    _text(surface, tiny, "Then enter this 6-digit pairing code:", 429, 213, MUTED, 330)
    pin = pin_state.get("pin")
    if pin:
        pin_font = pygame.font.Font(None, 65)
        _text(surface, pin_font, pin, 441, 241, ACCENT, 319)
        _text(surface, tiny, f"Pairing open: {pin_state['seconds_left'] // 60}m left",
              434, 312, MUTED, 325)
    else:
        _text(surface, small, "Pairing PIN expired", 435, 258, ACCENT, 308)
        _text(surface, tiny, "Tap Renew PIN for another 10 minutes", 435, 308, MUTED, 330)

    for rect, label, color in (
        (RENEW_BUTTON, "Renew PIN", (31, 83, 88)),
        (CLOSE_BUTTON, "Close guest access", (64, 37, 37)),
    ):
        pygame.draw.rect(surface, color, rect, border_radius=9)
        pygame.draw.rect(surface, EDGE, rect, 1, border_radius=9)
        rendered = tiny.render(label, True, WHITE)
        surface.blit(rendered, rendered.get_rect(center=rect.center))

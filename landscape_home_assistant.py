"""Standalone PiRadio 7 touchscreen control of selected Home Assistant devices.

All coordinates are physical 800x480; drawing and touching never use network.
"""
import pygame

BG = (0, 0, 0)
CARD = (17, 20, 23)
BORDER = (60, 70, 77)
INK = (246, 248, 249)
DIM = (162, 171, 179)
ACCENT = (69, 215, 225)
HEADER = pygame.Rect(18, 77, 764, 76)
BACK = pygame.Rect(668, 94, 98, 43)
DEVICE_TILES = tuple(
    pygame.Rect(18 + (index % 2) * 387, 164 + (index // 2) * 74, 375, 65)
    for index in range(8)
)


def _text(surface, font, value, pos, color=INK, max_width=None):
    value = str(value or "")
    if max_width:
        original = value
        while value and font.size(value)[0] > max_width:
            value = value[:-1]
        if value != original:
            value = value.rstrip() + "…" if value else ""
    if value:
        surface.blit(font.render(value, True, color), pos)


def draw(surface, font, small, tiny, snapshot):
    """Read-only rendering; expects HomeAssistantBridge.snapshot()."""
    snapshot = snapshot or {}
    surface.fill(BG, pygame.Rect(0, 65, 800, 415))
    pygame.draw.rect(surface, CARD, HEADER, border_radius=19)
    pygame.draw.rect(surface, BORDER, HEADER, 1, border_radius=19)
    _text(surface, font, "SMART HOME", (38, 87), INK, 465)
    status = ("Connected" if snapshot.get("online")
              else (snapshot.get("message") or "Not connected"))
    _text(surface, small, status, (39, 123),
          ACCENT if snapshot.get("online") else DIM, 555)
    pygame.draw.rect(surface, (43, 47, 50), BACK, border_radius=12)
    _text(surface, small, "HOME", (686, 104), INK, 74)
    items = snapshot.get("items") or []
    if not snapshot.get("configured"):
        _text(surface, small, "Connect Home Assistant on your Raspberry Pi.",
              (33, 191), INK, 710)
        _text(surface, tiny, "Instructions: HOME_ASSISTANT_SETUP.md",
              (34, 228), DIM, 706)
        _text(surface, tiny, "No account token is shown or entered on this screen.",
              (34, 260), DIM, 706)
        return True
    if not items:
        _text(surface, small, "No devices selected", (33, 193), DIM, 500)
        return True
    for index, item in enumerate(items[:8]):
        rect = DEVICE_TILES[index]
        active = item.get("state") == "on"
        disabled = (not snapshot.get("online") or item.get("busy")
                    or item.get("state") not in ("on", "off"))
        bg = (21, 49, 53) if active and not disabled else CARD
        pygame.draw.rect(surface, bg, rect, border_radius=15)
        pygame.draw.rect(surface, ACCENT if active and not disabled else BORDER,
                         rect, 1, border_radius=15)
        is_light = str(item.get("id") or "").startswith("light.")
        icon = "●" if is_light else "▣"
        _text(surface, font, icon, (rect.x + 15, rect.y + 12),
              ACCENT if active else DIM, 30)
        _text(surface, small, item.get("name") or "Device",
              (rect.x + 54, rect.y + 9), INK, 232)
        state = ("UPDATING" if item.get("busy") else
                 ("ON" if active else
                  ("OFF" if item.get("state") == "off" else "UNAVAILABLE")))
        _text(surface, tiny, state, (rect.x + 55, rect.y + 37),
              ACCENT if active and not disabled else DIM, 228)
        pygame.draw.rect(surface,
                         ACCENT if active and not disabled else (67, 72, 76),
                         pygame.Rect(rect.right - 73, rect.y + 17, 55, 30),
                         border_radius=15)
        knob_x = rect.right - 45 if active and not disabled else rect.right - 60
        pygame.draw.circle(surface, INK, (knob_x, rect.y + 32), 11)
    return True


def hit(pos, snapshot):
    """Actions are limited to Back and currently available light/switch tiles."""
    if BACK.collidepoint(pos):
        return ("page", "menu")
    snapshot = snapshot or {}
    if not snapshot.get("online"):
        return None
    for index, item in enumerate((snapshot.get("items") or [])[:8]):
        if DEVICE_TILES[index].collidepoint(pos):
            if (item.get("busy") or item.get("state") not in ("on", "off")):
                return None
            return ("toggle", index)
    return None

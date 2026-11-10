"""Native 800x480 radio station selector for PiRadio 7.

The selector displays only TC Radio streams, never temporary YouTube items.
Existing Radio and YouTube playback engines remain unchanged.
"""
import pygame

PANEL = pygame.Rect(158, 74, 629, 312)
CLOSE = pygame.Rect(661, 85, 101, 36)
PREV = pygame.Rect(473, 337, 113, 38)
NEXT = pygame.Rect(604, 337, 113, 38)
PAGE_SIZE = 6
INK = (248, 248, 248)
MUTED = (171, 171, 171)
CYAN = (55, 215, 230)
BUTTONS = tuple(
    pygame.Rect(181 + (i % 2) * 294, 139 + (i // 2) * 61, 282, 52)
    for i in range(PAGE_SIZE)
)


def _fit(font, label, width, color=INK):
    label = str(label or "Untitled station")
    raw = label
    while len(label) > 1 and font.render(label, True, color).get_width() > width:
        label = label[:-1]
    if label != raw:
        while len(label) > 1 and font.render(label + "…", True, color).get_width() > width:
            label = label[:-1]
        label = label.rstrip() + "…"
    return font.render(label, True, color)


def draw(surface, font, small, tiny, stations, indices, offset, current_idx):
    pygame.draw.rect(surface, (13, 13, 13), PANEL, border_radius=18)
    pygame.draw.rect(surface, (79, 79, 79), PANEL, 2, border_radius=18)
    surface.blit(font.render("TC RADIO  ·  STATIONS", True, INK), (179, 86))
    pygame.draw.rect(surface, (36, 36, 36), CLOSE, border_radius=9)
    surface.blit(tiny.render("CLOSE", True, INK), (CLOSE.x+29, CLOSE.y+10))
    total = len(indices)
    if not total:
        surface.blit(small.render("Radio stations are still loading.", True, MUTED),
                     (193, 197))
    for slot, station_idx in enumerate(indices[offset:offset+PAGE_SIZE]):
        rect = BUTTONS[slot]
        current = station_idx == current_idx
        pygame.draw.rect(surface, (37, 47, 48) if current else (27, 27, 27),
                         rect, border_radius=12)
        pygame.draw.rect(surface, CYAN if current else (75, 75, 75),
                         rect, 2 if current else 1, border_radius=12)
        pygame.draw.circle(surface, CYAN if current else MUTED,
                           (rect.x+20, rect.centery), 6)
        name = stations[station_idx].get("name", "TC Radio")
        rendered = _fit(small, name, rect.width-62)
        surface.blit(rendered, (rect.x+36, rect.y+12))
    label = f"STATIONS  {offset + 1 if total else 0}-{min(offset+PAGE_SIZE,total)}  / {total}"
    surface.blit(tiny.render(label, True, MUTED), (182, 349))
    for rect, label in ((PREV,"PREV"),(NEXT,"NEXT")):
        pygame.draw.rect(surface, (37,37,37), rect, border_radius=10)
        pygame.draw.rect(surface, (83,83,83), rect, 1, border_radius=10)
        text = tiny.render(label, True, INK)
        surface.blit(text, text.get_rect(center=rect.center))


def hit(pos, indices, offset):
    if not PANEL.collidepoint(pos):
        return None
    if CLOSE.collidepoint(pos):
        return ("close", None)
    if PREV.collidepoint(pos):
        return ("prev", None)
    if NEXT.collidepoint(pos):
        return ("next", None)
    for slot, rect in enumerate(BUTTONS):
        if rect.collidepoint(pos):
            j = offset + slot
            return ("station", indices[j]) if j < len(indices) else ("consume", None)
    return ("consume", None)

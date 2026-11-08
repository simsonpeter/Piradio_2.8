"""Responsive landscape layout geometry for official Raspberry Pi 7-inch 800x480.
Pure layout definitions: no audio, GPIO or playback changes.
"""
from dataclasses import dataclass
import pygame

TARGET_SIZE = (800, 480)
MIN_TOUCH = 48

@dataclass(frozen=True)
class LandscapeLayout:
    width: int = 800
    height: int = 480

    @property
    def header(self):
        return pygame.Rect(0, 0, self.width, 60)

    @property
    def artwork(self):
        return pygame.Rect(24, 82, 285, 285)

    @property
    def player(self):
        return pygame.Rect(333, 82, 443, 285)

    @property
    def bottom_nav(self):
        return pygame.Rect(16, 390, 768, 74)

    def nav_buttons(self):
        names = ("HOME", "RADIO", "BIBLE", "YOUTUBE", "FAVORITES")
        gap = 10
        width = (self.bottom_nav.width - gap * (len(names) - 1)) // len(names)
        return {name: pygame.Rect(self.bottom_nav.x + i * (width + gap),
                                  self.bottom_nav.y, width, self.bottom_nav.height)
                for i, name in enumerate(names)}

    def hit(self, pos):
        """One deterministic target per tap; no overlapping navigation hitboxes."""
        for name, rect in self.nav_buttons().items():
            if rect.collidepoint(pos):
                return name
        return None

    def validate(self):
        regions = list(self.nav_buttons().values())
        assert all(r.width >= MIN_TOUCH and r.height >= MIN_TOUCH for r in regions)
        assert all(not a.colliderect(b) for i,a in enumerate(regions) for b in regions[i+1:])
        assert all(pygame.Rect(0,0,self.width,self.height).contains(r) for r in regions)
        return True

def draw_landscape_shell(surface, font, small, mode="light"):
    """First-stage landscape preview, independent of the legacy 320x480 renderer."""
    from ios_ipod_ui import THEMES, raised_card
    from fa_icons import draw_icon
    layout = LandscapeLayout(*surface.get_size())
    layout.validate()
    palette = THEMES[mode]
    surface.fill(palette["bg"])
    ink, muted = palette["ink"], palette["muted"]
    surface.blit(font.render("PiRadio Pro", True, ink), (24, 18))
    for region in (layout.artwork, layout.player):
        raised_card(surface, region, mode, 18, 3)
    draw_icon(surface, "radio", layout.artwork.center, 74, (64,104,176))
    surface.blit(font.render("NOW PLAYING", True, ink), (355, 112))
    surface.blit(small.render("Radio  |  Tamil Bible  |  YouTube Audio", True, muted), (355, 158))
    for name, rect in layout.nav_buttons().items():
        raised_card(surface, rect, mode, 14, 2)
        label = small.render(name, True, ink)
        surface.blit(label, label.get_rect(center=rect.center))
    return layout

"""Elegant low-overhead 800x480 ambient clock for the PiRadio 7-inch display.

The drawing routine is deliberately independent of remote-control, mpv and VLC
state. The host passes the currently playing title, alarm and cached weather.
Background artwork is cached so a 20 FPS application doesn't redraw gradients.
"""
from datetime import datetime
import math

import pygame


_BACKGROUND = None
_BACKGROUND_SIZE = None

WHITE = (244, 247, 253)
SOFT = (174, 187, 205)
MUTED = (111, 127, 150)
ACCENT = (125, 187, 226)
CARD = (17, 27, 44)
CARD_BORDER = (46, 66, 89)


def _backdrop(size):
    global _BACKGROUND, _BACKGROUND_SIZE
    if _BACKGROUND is not None and _BACKGROUND_SIZE == size:
        return _BACKGROUND
    width, height = size
    image = pygame.Surface(size)
    for y in range(height):
        shade = y / max(1, height - 1)
        color = (
            int(5 + 5 * shade),
            int(11 + 8 * shade),
            int(22 + 13 * shade),
        )
        pygame.draw.line(image, color, (0, y), (width, y))

    # A faint stationary aurora: a cached soft glow, not a demanding animation.
    halo = pygame.Surface(size, pygame.SRCALPHA)
    for radius in range(195, 17, -7):
        alpha = max(1, int((1.0 - radius / 210.0) * 3.5))
        pygame.draw.circle(halo, (50, 123, 176, alpha), (130, 250), radius)
    for radius in range(155, 17, -7):
        alpha = max(1, int((1.0 - radius / 175.0) * 3))
        pygame.draw.circle(halo, (89, 88, 167, alpha), (725, 95), radius)
    image.blit(halo, (0, 0))
    _BACKGROUND = image
    _BACKGROUND_SIZE = size
    return image


def _text(target, font, message, x, y, color=WHITE, max_width=None):
    if not message:
        return 0
    message = str(message)
    rendered = font.render(message, True, color)
    if max_width and rendered.get_width() > max_width:
        # Fit long Tamil/English radio titles without shrinking the whole UI.
        while len(message) > 2 and rendered.get_width() > max_width:
            message = message[:-2].rstrip()
            rendered = font.render(message + "…", True, color)
        if not message.endswith("…"):
            rendered = font.render(message + "…", True, color)
    target.blit(rendered, (int(x), int(y)))
    return rendered.get_width()


def draw(surface, fonts, now, weather_type, temperature, city, forecast,
         humidity, now_playing, alarm_time, weather_icon):
    """Draw the entire physical 7-inch screen, with existing cached weather.

    The supplied fonts are pre-created by touch_radio.py; no network requests,
    new fonts or filesystem operations are needed in the render loop.
    """
    w, h = surface.get_size()
    if (w, h) != (800, 480):
        # Native official 7-inch display is 800x480; keep any other size safe.
        surface.fill((7, 12, 22))
        _text(surface, fonts["medium"], "PiRadio", 24, 20)
        _text(surface, fonts["clock"], datetime.fromtimestamp(now).strftime("%H:%M"),
              22, h // 3)
        return

    surface.blit(_backdrop((w, h)), (0, 0))
    moment = datetime.fromtimestamp(now)

    # Header; quiet enough for a night-time bedside display.
    pygame.draw.circle(surface, ACCENT, (43, 42), 5)
    _text(surface, fonts["medium"], "PiRadio", 58, 25, WHITE)
    _text(surface, fonts["small"], "AMBIENT DISPLAY", 619, 32, MUTED)
    pygame.draw.line(surface, CARD_BORDER, (36, 77), (764, 77), 1)

    # Hero clock occupies most of the left-hand side.
    _text(surface, fonts["label"], "LOCAL TIME", 49, 103, ACCENT)
    clock = moment.strftime("%H:%M")
    clock_w = _text(surface, fonts["clock"], clock, 39, 119, WHITE)
    # Tiny seconds beside the main clock, not part of the giant numerals.
    _text(surface, fonts["medium"], moment.strftime("%S"),
          min(495, 45 + clock_w), 207, MUTED)
    _text(surface, fonts["date"],
          moment.strftime("%A, %d %B %Y"), 49, 279, SOFT, max_width=465)
    _text(surface, fonts["small"], "Touch anywhere to wake", 50, 319, MUTED)

    # Weather card: the existing Open-Meteo cached measurements are reused.
    weather_box = pygame.Rect(533, 96, 237, 237)
    pygame.draw.rect(surface, CARD, weather_box, border_radius=23)
    pygame.draw.rect(surface, CARD_BORDER, weather_box, 1, border_radius=23)
    _text(surface, fonts["label"], "LOCAL WEATHER", 555, 113, ACCENT)
    if callable(weather_icon):
        weather_icon(surface, 571, 187, weather_type, 26,
                     dimmed=False, on_background=CARD)
    temp_text = f"{round(temperature)}°C" if temperature is not None else "--°C"
    _text(surface, fonts["temperature"], temp_text, 609, 154, WHITE, 150)
    _text(surface, fonts["medium"], city or "Weather", 555, 224, WHITE, 194)
    if forecast:
        today = forecast[0]
        hi = today.get("high", "--")
        lo = today.get("low", "--")
        _text(surface, fonts["small"], f"High {hi}°   Low {lo}°",
              555, 267, SOFT, 202)
    else:
        _text(surface, fonts["small"], "Forecast unavailable", 555, 267, SOFT)
    if humidity is not None:
        _text(surface, fonts["small"], f"Humidity {humidity}%",
              555, 298, MUTED)

    # Bottom now-playing and alarm dock; readable even from across a room.
    dock = pygame.Rect(28, 357, 744, 94)
    pygame.draw.rect(surface, CARD, dock, border_radius=20)
    pygame.draw.rect(surface, CARD_BORDER, dock, 1, border_radius=20)
    pygame.draw.circle(surface, ACCENT, (56, 392), 7)
    _text(surface, fonts["label"], "NOW PLAYING", 75, 374, ACCENT)
    _text(surface, fonts["medium"], now_playing or "Ready to play",
          50, 407, WHITE, 522)
    pygame.draw.line(surface, CARD_BORDER, (590, 374), (590, 431), 1)
    _text(surface, fonts["label"], "NEXT ALARM", 613, 375, MUTED)
    _text(surface, fonts["medium"], alarm_time or "Off", 613, 406, WHITE)

    # Discreet breathing indicator (single dot; no full-screen redraw animation).
    pulse = (math.sin(now * 0.8) + 1.0) * 0.5
    pygame.draw.circle(surface, (int(55 + pulse * 35),
                                 int(110 + pulse * 45),
                                 int(150 + pulse * 45)), (761, 41), 3)

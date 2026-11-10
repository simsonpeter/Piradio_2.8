"""High-contrast, pure-black 800x480 ambient screen for PiRadio.

The UI is designed for the official 7-inch touchscreen: white clock,
cyan weather and soft gray secondary information. It uses cached weather
from PiRadio and makes no network calls while rendering.
"""
from datetime import datetime

import pygame


BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
SOFT = (185, 185, 185)
MUTED = (125, 125, 125)
WEATHER_CYAN = (48, 218, 236)
DIVIDER = (45, 45, 45)


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
        surface.fill(BLACK)
        _text(surface, fonts["medium"], "PiRadio", 24, 20)
        _text(surface, fonts["clock"], datetime.fromtimestamp(now).strftime("%H:%M"),
              22, h // 3)
        return

    surface.fill(BLACK)
    moment = datetime.fromtimestamp(now)

    # Header; quiet enough for a night-time bedside display.
    pygame.draw.circle(surface, WHITE, (43, 42), 5)
    _text(surface, fonts["medium"], "PiRadio", 58, 25, WHITE)
    _text(surface, fonts["small"], "AMBIENT DISPLAY", 619, 32, MUTED)
    pygame.draw.line(surface, DIVIDER, (36, 77), (764, 77), 1)

    # Hero clock occupies most of the left-hand side.
    _text(surface, fonts["label"], "LOCAL TIME", 49, 103, SOFT)
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
    pygame.draw.rect(surface, BLACK, weather_box, border_radius=23)
    pygame.draw.rect(surface, DIVIDER, weather_box, 1, border_radius=23)
    _text(surface, fonts["label"], "LOCAL WEATHER", 555, 113, WEATHER_CYAN)
    if callable(weather_icon):
        weather_icon(surface, 571, 187, weather_type, 26,
                     dimmed=False, on_background=BLACK)
    temp_text = f"{round(temperature)}°C" if temperature is not None else "--°C"
    _text(surface, fonts["temperature"], temp_text, 609, 154, WEATHER_CYAN, 150)
    _text(surface, fonts["medium"], city or "Weather", 555, 224, WEATHER_CYAN, 194)
    if forecast:
        today = forecast[0]
        hi = today.get("high", "--")
        lo = today.get("low", "--")
        _text(surface, fonts["small"], f"High {hi}°   Low {lo}°",
              555, 267, WEATHER_CYAN, 202)
    else:
        _text(surface, fonts["small"], "Forecast unavailable", 555, 267, SOFT)
    if humidity is not None:
        _text(surface, fonts["small"], f"Humidity {humidity}%",
              555, 298, WEATHER_CYAN)

    # Bottom now-playing and alarm dock; readable even from across a room.
    dock = pygame.Rect(28, 357, 744, 94)
    pygame.draw.rect(surface, BLACK, dock, border_radius=20)
    pygame.draw.rect(surface, DIVIDER, dock, 1, border_radius=20)
    pygame.draw.circle(surface, WHITE, (56, 392), 7)
    _text(surface, fonts["label"], "NOW PLAYING", 75, 374, SOFT)
    _text(surface, fonts["medium"], now_playing or "Ready to play",
          50, 407, WHITE, 522)
    pygame.draw.line(surface, DIVIDER, (590, 374), (590, 431), 1)
    _text(surface, fonts["label"], "NEXT ALARM", 613, 375, MUTED)
    _text(surface, fonts["medium"], alarm_time or "Off", 613, 406, WHITE)

    # Keep every unoccupied pixel completely black; no glow or animation.

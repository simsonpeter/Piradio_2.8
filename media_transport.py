"""Pure playback-command planning for PiRadio 7.

Pygame/Flask do not import a second playback engine. They choose one plan,
then the existing VLC, Bible or MPV backend executes it. This keeps remote
and touchscreen commands consistent without changing audio ownership.
"""
from dataclasses import dataclass
from math import isfinite


_MPV_SOURCES = frozenset({
    "youtube_video", "guest_video", "guest_audio", "guest_photos",
    "screen_mirror",
})
_ACTIONS = frozenset({
    "toggle", "next", "prev", "seek", "seek_relative",
    "stop", "minimize", "restore",
})


@dataclass(frozen=True)
class TransportPlan:
    engine: str
    operation: str
    value: float | None = None


def _seconds(value):
    if isinstance(value, bool):
        raise ValueError("Seek position must be a number")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Seek position must be a number") from exc
    if not isfinite(result):
        raise ValueError("Seek position must be finite")
    return result


def plan_media_command(source, action, seconds=None, *, seekable=False):
    """Return a safe command plan; return None for unsupported controls.

    Playback priority is resolved by the caller (MPV > Bible > VLC).
    'next/prev' on MPV video means 10-second seek, not station switching;
    on a guest photo slideshow it means playlist navigation.
    """
    if action not in _ACTIONS:
        return None

    if source in _MPV_SOURCES:
        if action == "toggle":
            return TransportPlan("mpv", "pause")
        if action == "stop":
            return TransportPlan("mpv", "stop")
        if action == "minimize":
            return TransportPlan("mpv", "minimize")
        if action == "restore":
            return TransportPlan("mpv", "restore")
        if source == "guest_photos":
            if action in ("next", "prev"):
                return TransportPlan("mpv", "playlist_next" if action == "next"
                                     else "playlist_prev")
            return None
        if source == "screen_mirror" and action in (
                "next", "prev", "seek", "seek_relative"):
            return None
        if action in ("next", "prev"):
            return TransportPlan("mpv", "seek_relative",
                                 10.0 if action == "next" else -10.0)
        if action in ("seek", "seek_relative"):
            position = _seconds(seconds)
            if action == "seek":
                if position < 0:
                    raise ValueError("Absolute seek cannot be negative")
                if not seekable:
                    return None
            return TransportPlan("mpv", action, position)
        return None

    if source == "bible":
        if action == "toggle":
            return TransportPlan("bible", "toggle")
        if action == "stop":
            return TransportPlan("bible", "stop")
        if action in ("next", "prev"):
            return TransportPlan("bible", "chapter_shift",
                                 1.0 if action == "next" else -1.0)
        return None

    if source in ("radio", "youtube_audio"):
        if action == "toggle":
            return TransportPlan("vlc", "toggle")
        if action == "stop":
            return TransportPlan("vlc", "stop")
        if action in ("next", "prev"):
            return TransportPlan("vlc", "next",
                                 1.0 if action == "next" else -1.0)
        if action == "seek" and source == "youtube_audio":
            position = _seconds(seconds)
            if position < 0:
                raise ValueError("Absolute seek cannot be negative")
            return (TransportPlan("vlc", "seek", position)
                    if seekable else None)
    return None

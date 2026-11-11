"""Input validation for PiRadio 7 Cinema timeline controls.

Pure Python: this module never launches MPV or touches the Raspberry Pi.
MPV reports real duration and seekability through JSON IPC.
"""
from math import isfinite


SEEKABLE_SOURCES = frozenset({"youtube_video", "guest_video", "guest_audio"})


def _finite_number(value):
    if isinstance(value, bool):
        raise ValueError("A numeric seek position is required")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("A numeric seek position is required") from error
    if not isfinite(result):
        raise ValueError("Seek position must be finite")
    return result


def validate_cinema_seek(action, seconds, status):
    """Return a clamped timestamp or delta for seek-capable MPV media.

    Do not attempt to seek a live mirror, photo slideshow or media whose
    duration is still unknown. Avoid exact EOF seeking because some online
    formats restart or tear down their playback process at end of file.
    """
    if action not in ("seek", "seek_relative"):
        raise ValueError("Unsupported timeline action")
    status = status or {}
    if not status.get("playing"):
        raise ValueError("No active video session")
    if status.get("source") not in SEEKABLE_SOURCES:
        raise ValueError("This media type does not support timeline seeking")
    duration = _finite_number(status.get("duration", 0))
    if duration <= 0 or not status.get("seekable"):
        raise ValueError("Timeline unavailable for this stream")
    position = _finite_number(status.get("position", 0))
    requested = _finite_number(seconds)
    maximum = max(0.0, duration - 0.25)
    if action == "seek":
        return max(0.0, min(requested, maximum))
    target = max(0.0, min(position + requested, maximum))
    return target - position


def cinema_remote_state(status):
    """Small consistent state for remote controls, no credentials or URLs."""
    status = status or {}
    playing = bool(status.get("playing"))
    paused = bool(status.get("paused"))
    source = status.get("source") or "youtube_video"
    duration = status.get("duration") or 0
    position = status.get("position") or 0
    try:
        duration = max(0.0, _finite_number(duration))
        position = max(0.0, _finite_number(position))
    except ValueError:
        duration = position = 0.0
    seekable = (
        playing and source in SEEKABLE_SOURCES
        and bool(status.get("seekable")) and duration > 0
    )
    return {
        "playing": playing,
        "paused": paused,
        "minimized": bool(status.get("minimized")),
        "buffering": bool(status.get("buffering")) if playing else False,
        "source": source,
        "title": str(status.get("title") or "PiRadio Media")[:160],
        "duration": duration,
        "position": min(position, duration) if duration else position,
        "seekable": seekable,
    }


def validate_cinema_volume(level):
    """Accept a whole-number Pi volume percentage from the phone remote.

    Reject booleans, negative levels, malformed values and oversized inputs.
    Changing the video volume uses PiRadio's central volume handler, so the
    Pi touchscreen and other remotes remain synchronised.
    """
    if type(level) is not int or not 0 <= level <= 100:
        raise ValueError("Volume must be a whole number from 0 to 100")
    return level

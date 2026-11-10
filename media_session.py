"""Shared, read-only media state for PiRadio 7.

VLC, Tamil Bible and MPV keep ownership of their playback processes.
This module only resolves which source owns the screen and phone remote.
No network calls, Pygame imports or hardware access happen here.
"""

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Mapping, Optional


def _seconds(value):
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        return 0.0
    return result if isfinite(result) and result >= 0 else 0.0


def _volume(value):
    try:
        result = int(value)
    except (ValueError, TypeError, OverflowError):
        return 0
    return max(0, min(100, result))


@dataclass(frozen=True)
class MediaSnapshot:
    """One portable snapshot for every user interface."""

    source: str
    title: str
    playing: bool
    paused: bool
    position: float
    duration: float
    seekable: bool
    minimized: bool
    volume: int
    station: int

    def as_dict(self):
        return asdict(self)


def resolve_media_snapshot(
    *,
    video_status: Optional[Mapping] = None,
    bible_active=False,
    bible_paused=False,
    bible_title="",
    vlc_state="stopped",
    vlc_source="radio",
    vlc_title="",
    vlc_position=0,
    vlc_duration=0,
    vlc_seekable=False,
    volume=80,
    station=0,
):
    """Resolve MPV > Bible > VLC, never displaying stale radio as active MPV.

    MPV status uses 'playing' to mean its process exists; the separate
    'paused' flag represents transport state.  Paused video still owns
    the session and must not fall through to a stale VLC source.
    """
    level = _volume(volume)
    try:
        station_index = max(0, int(station))
    except (TypeError, ValueError, OverflowError):
        station_index = 0

    if video_status is not None and bool(video_status.get("playing")):
        paused = bool(video_status.get("paused", False))
        duration = _seconds(video_status.get("duration"))
        position = _seconds(video_status.get("position"))
        return MediaSnapshot(
            source=str(video_status.get("source") or "youtube_video"),
            title=str(video_status.get("title") or "PiRadio Media"),
            playing=not paused,
            paused=paused,
            position=position,
            duration=duration,
            seekable=duration > 0,
            minimized=bool(video_status.get("minimized", False)),
            volume=level,
            station=station_index,
        )

    if bible_active:
        paused = bool(bible_paused)
        return MediaSnapshot(
            source="bible",
            title=str(bible_title or "Tamil Bible"),
            playing=not paused,
            paused=paused,
            position=0.0,
            duration=0.0,
            seekable=False,
            minimized=False,
            volume=level,
            station=station_index,
        )

    state = str(vlc_state).lower()
    paused = state == "paused"
    duration = _seconds(vlc_duration)
    return MediaSnapshot(
        source=vlc_source if vlc_source in ("radio", "youtube_audio") else "radio",
        title=str(vlc_title or "PiRadio"),
        playing=state == "playing",
        paused=paused,
        position=_seconds(vlc_position),
        duration=duration,
        seekable=bool(vlc_seekable) and duration > 0,
        minimized=False,
        volume=level,
        station=station_index,
    )

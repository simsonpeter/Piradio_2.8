"""Experimental mpv-based YouTube video backend for PiRadio Pro.

Requires: sudo apt install mpv
Requires a direct, playable media URL resolved by the existing YouTube code.
The display integration is intentionally opt-in until touch/Wayland testing.
"""
import json
import math
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path


class YouTubeVideoBackend:
    def __init__(self):
        self.process = None
        self.socket_path = None
        self.minimized = False
        self.video_id = None
        self.title = ""
        self.source_type = "youtube_video"

    def _command(self, *args):
        if not self.process or self.process.poll() is not None or not self.socket_path:
            return False
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(1)
                client.connect(self.socket_path)
                client.sendall((json.dumps({"command": list(args)}) + "\n").encode())
                return True
        except (OSError, ValueError):
            return False

    def _start_sources(self, sources, source_type="youtube_video", title="",
                       audio_only=False, photo_duration=None, rtsp=False):
        """Use the existing MPV engine for guest files, photos and RTSP streams."""
        if not sources:
            raise ValueError("No media selected")
        self.stop()
        if subprocess.run(["which", "mpv"], capture_output=True).returncode != 0:
            raise RuntimeError("mpv is not installed; install it with sudo apt install mpv")
        self.socket_path = str(Path(tempfile.gettempdir()) / f"piradio-video-{os.getpid()}.sock")
        try:
            os.unlink(self.socket_path)
        except FileNotFoundError:
            pass
        environment = os.environ.copy()
        environment.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        environment.setdefault("WAYLAND_DISPLAY", "wayland-0")
        cmd = ["mpv", "--no-config",
               "--hwdec=no", "--profile=fast",
               "--cache=yes", "--cache-secs=20",
               "--demuxer-max-bytes=32MiB", "--video-sync=audio",
               "--framedrop=vo",
               "--ytdl-format=bestvideo[height<=480][vcodec^=avc1]+bestaudio/best[height<=480][vcodec^=avc1]/best[height<=480]",
               "--input-ipc-server=" + self.socket_path,
               "--title=" + (str(title or "PiRadio Media")[:120])]
        if audio_only:
            # No separate window for guest audio, PiRadio remains fully usable.
            cmd.extend(["--no-video", "--force-window=no",
                        "--no-osc", "--no-input-default-bindings"])
        else:
            cmd.extend(["--force-window=yes", "--fs",
                        "--vo=gpu", "--gpu-context=wayland",
                        "--script=" + str(Path(__file__).with_name("mpv_piradio_touch.lua")),
                        "--osc=yes", "--input-default-bindings=yes"])
        if photo_duration is not None:
            cmd.append("--image-display-duration=" + str(photo_duration))
            if len(sources) > 1:
                cmd.append("--loop-playlist=inf")
        if rtsp:
            # Live phone screen streams should not accumulate seconds of cache.
            cmd.extend(["--cache=no", "--profile=low-latency"])
        cmd.append("--")
        cmd.extend(sources)
        try:
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=environment,
            )
        except Exception:
            self.socket_path = None
            raise
        self.minimized = bool(audio_only)
        self.video_id = None
        self.source_type = source_type
        self.title = str(title or "PiRadio Media")[:160]
        return True

    def start(self, media_url):
        if not isinstance(media_url, str) or not media_url.startswith(("https://", "http://")):
            raise ValueError("A resolved HTTP(S) video URL is required")
        return self._start_sources([media_url], source_type="youtube_video",
                                   title="YouTube video")

    def start_local(self, files, kind):
        """Play uploaded media from private guest cache files only."""
        if kind not in ("photos", "audio", "video"):
            raise ValueError("Unsupported local media type")
        if isinstance(files, (str, bytes)) or not isinstance(files, (list, tuple)) or not files:
            raise ValueError("Choose media files")
        base = (Path.home() / ".cache" / "piradio-guest-cast").resolve()
        paths = []
        for name in files:
            resolved = Path(name).resolve(strict=True)
            if resolved.parent != base or not resolved.is_file():
                raise ValueError("Guest file is outside the private cast cache")
            paths.append(str(resolved))
        if kind != "photos" and len(paths) != 1:
            raise ValueError("Send one audio or video file at a time")
        if kind == "photos":
            seconds = "8" if len(paths) > 1 else "inf"
            title = "Guest photo slideshow" if len(paths) > 1 else "Guest photo"
        else:
            seconds = None
            title = Path(paths[0]).name
            # No filename information in randomised disk name; callers can
            # set a friendly title after startup if desired.
        return self._start_sources(
            paths, source_type="guest_" + kind, title=title,
            audio_only=(kind == "audio"), photo_duration=seconds,
        )

    def start_network_stream(self, media_url, title="Android screen mirror"):
        """An already validated same-LAN RTSP URL from ScreenStream Android."""
        if not isinstance(media_url, str) or not media_url.startswith("rtsp://"):
            raise ValueError("RTSP stream required")
        return self._start_sources(
            [media_url], source_type="screen_mirror", title=title, rtsp=True
        )

    def start_youtube(self, video_id, title=""):
        """Use mpv yt-dlp integration to resolve the video stream itself."""
        import re
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", str(video_id)):
            raise ValueError("Invalid YouTube video ID")
        self.start("https://www.youtube.com/watch?v=" + video_id)
        self.video_id = str(video_id)
        self.title = str(title or "YouTube video")[:160]

    def pause(self):
        return self._command("cycle", "pause")

    def seek(self, seconds):
        return self._command("seek", float(seconds), "relative")

    def seek_absolute(self, seconds):
        """Seek to a specific playback timestamp (seconds)."""
        return self._command("seek", max(0, float(seconds)), "absolute", "exact")

    def playback_status(self):
        """Read the active mpv state for both Pi and phone controls.

        A Lua touchscreen MINIMISE action changes mpv's vid property directly
        without invoking this Python object's minimize_audio(). Querying the
        property lets the PiRadio mini-player follow either control path.
        IPC responses are matched by request_id; unsolicited events are ignored.
        """
        empty = {
            "playing": False, "position": 0, "duration": 0,
            "paused": False, "minimized": False, "title": "",
            "video_id": None, "source": self.source_type,
        }
        if not self.is_playing() or not self.socket_path:
            self.minimized = False
            return empty
        result = {
            "playing": True, "position": 0, "duration": 0,
            "paused": False, "minimized": self.minimized,
            "title": self.title or "PiRadio Media", "video_id": self.video_id,
            "source": self.source_type,
        }
        keys = {
            1: ("time-pos", "position"),
            2: ("duration", "duration"),
            3: ("pause", "paused"),
            4: ("vid", "_video_track"),
            5: ("window-minimized", "_window_minimized"),
        }
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(0.65)
                client.connect(self.socket_path)
                requests = "".join(
                    json.dumps({
                        "command": ["get_property", name],
                        "request_id": request_id,
                    }) + "\n"
                    for request_id, (name, _field) in keys.items()
                )
                client.sendall(requests.encode("utf-8"))
                pending = set(keys)
                buffer = b""
                deadline = time.monotonic() + 0.75
                while pending and time.monotonic() < deadline:
                    try:
                        chunk = client.recv(4096)
                    except socket.timeout:
                        break
                    if not chunk:
                        break
                    buffer += chunk
                    while b"\n" in buffer:
                        row, buffer = buffer.split(b"\n", 1)
                        try:
                            message = json.loads(row)
                        except (ValueError, UnicodeDecodeError):
                            continue
                        request_id = message.get("request_id")
                        if request_id not in pending:
                            continue
                        pending.discard(request_id)
                        if message.get("error") == "success":
                            result[keys[request_id][1]] = message.get("data")
        except (OSError, ValueError, ConnectionError):
            pass

        if "_video_track" in result:
            track = result.pop("_video_track")
            # mpv uses vid=no for audio-only and after its own Lua MINIMISE.
            self.minimized = track in ("no", False, 0, None)
        if "_window_minimized" in result:
            minimized = result.pop("_window_minimized")
            if isinstance(minimized, bool):
                self.minimized = self.minimized or minimized
        result["minimized"] = self.minimized
        for numeric in ("position", "duration"):
            try:
                value = float(result[numeric])
                result[numeric] = value if math.isfinite(value) and value >= 0 else 0
            except (ValueError, TypeError, OverflowError):
                result[numeric] = 0
        return result

    def volume(self, value):
        return self._command("set_property", "volume", max(0, min(100, int(value))))

    def minimize_audio(self):
        """Disable video rendering, keeping audio alive. UI must return to PiRadio."""
        ok = self._command("set_property", "vid", "no")
        self._command("set_property", "window-minimized", "yes")
        self.minimized = ok
        return ok

    def restore_video(self):
        """Re-enable video and fullscreen on the same playback process."""
        ok = self._command("set_property", "vid", "auto")
        self._command("set_property", "window-minimized", "no")
        self._command("set_property", "fullscreen", "yes")
        self.minimized = False
        return ok

    def is_playing(self):
        return self.process is not None and self.process.poll() is None

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self._command("quit")
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
        self.process = None
        self.minimized = False
        self.video_id = None
        self.title = ""
        self.source_type = "youtube_video"
        if self.socket_path:
            try:
                os.unlink(self.socket_path)
            except FileNotFoundError:
                pass
        self.socket_path = None

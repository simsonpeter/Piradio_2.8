"""Experimental mpv-based YouTube video backend for PiRadio Pro.

Requires: sudo apt install mpv
Requires a direct, playable media URL resolved by the existing YouTube code.
The display integration is intentionally opt-in until touch/Wayland testing.
"""
import json
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

    def start(self, media_url):
        if not isinstance(media_url, str) or not media_url.startswith(("https://", "http://")):
            raise ValueError("A resolved HTTP(S) video URL is required")
        self.stop()
        if subprocess.run(["which", "mpv"], capture_output=True).returncode != 0:
            raise RuntimeError("mpv is not installed; install it with sudo apt install mpv")
        self.socket_path = str(Path(tempfile.gettempdir()) / f"piradio-video-{os.getpid()}.sock")
        try:
            os.unlink(self.socket_path)
        except FileNotFoundError:
            pass
        self.process = subprocess.Popen(
            ["mpv", "--no-config", "--force-window=yes", "--fs",
             "--osc=yes", "--input-default-bindings=yes",
             "--input-ipc-server=" + self.socket_path,
             "--title=PiRadio YouTube Video", media_url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.minimized = False

    def start_youtube(self, video_id):
        """Use mpv yt-dlp integration to resolve the video stream itself."""
        import re
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", str(video_id)):
            raise ValueError("Invalid YouTube video ID")
        self.start("https://www.youtube.com/watch?v=" + video_id)

    def pause(self):
        return self._command("cycle", "pause")

    def seek(self, seconds):
        return self._command("seek", float(seconds), "relative")

    def volume(self, value):
        return self._command("set_property", "volume", max(0, min(100, int(value))))

    def minimize_audio(self):
        """Disable video rendering, keeping audio alive. UI must return to PiRadio."""
        ok = self._command("set_property", "vid", "no")
        self._command("set_property", "fullscreen", "no")
        self.minimized = ok
        return ok

    def restore_video(self):
        """Re-enable video and fullscreen on the same playback process."""
        ok = self._command("set_property", "vid", "auto")
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
        if self.socket_path:
            try:
                os.unlink(self.socket_path)
            except FileNotFoundError:
                pass
        self.socket_path = None

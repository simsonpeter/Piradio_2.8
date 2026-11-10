"""Opt-in guest casting for PiRadio 7.

This is NOT a Google Cast receiver. A guest uses their phone browser on the
same Wi-Fi to upload selected media or a YouTube link, and controls the active
MPV session with a short-lived token. Android screen share uses a separate
RTSP sender such as ScreenStream in RTSP Server mode.

Safety:
- Nothing is pairable until the Pi owner opens the CAST page.
- The pairing PIN is shown only on the physical Pi screen.
- No anonymous transport, upload, or stream URL endpoints.
- Guest files are confined to a private cache directory with size limits.
- URLs are restricted to approved YouTube hosts or same-LAN RTSP sources.
- All subprocess calls are made by the existing MPV backend without shells.
"""
import ipaddress
import os
from pathlib import Path
import re
import secrets
import shutil
import threading
import time
from urllib.parse import parse_qs, urlsplit

from flask import Response, jsonify, request
from werkzeug.utils import secure_filename


PHOTO_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})
AUDIO_EXTS = frozenset({".mp3", ".aac", ".m4a", ".ogg", ".opus", ".flac", ".wav"})
VIDEO_EXTS = frozenset({".mp4", ".m4v", ".mov", ".webm", ".mkv"})
MAX_UPLOAD_BYTES = 256 * 1024 * 1024
MAX_PHOTO_BYTES = 20 * 1024 * 1024
MAX_PHOTOS = 20


def media_kind(filename):
    ext = Path(filename).suffix.lower()
    if ext in PHOTO_EXTS:
        return "photos"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in VIDEO_EXTS:
        return "video"
    return None


def youtube_id_from_url(value):
    try:
        parsed = urlsplit(str(value).strip())
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or parsed.username or parsed.password:
            return None
        if host == "youtu.be":
            candidate = parsed.path.lstrip("/").split("/", 1)[0]
        elif host in ("youtube.com", "www.youtube.com", "m.youtube.com",
                      "music.youtube.com"):
            if parsed.path == "/watch":
                candidate = parse_qs(parsed.query).get("v", [""])[0]
            elif parsed.path.startswith(("/shorts/", "/live/")):
                candidate = parsed.path.split("/")[2]
            else:
                return None
        else:
            return None
        return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate) else None
    except (ValueError, AttributeError):
        return None


def validate_rtsp(url, pi_ip):
    """Only allow an RTSP server in the Pi's IPv4 /24, not arbitrary URLs."""
    parsed = urlsplit(str(url).strip())
    if parsed.scheme != "rtsp" or parsed.username or parsed.password:
        raise ValueError("Use a plain rtsp:// address without a password")
    if parsed.query or parsed.fragment:
        raise ValueError("Copy the plain RTSP server URL from the Android app")
    try:
        phone_ip = ipaddress.IPv4Address(parsed.hostname or "")
        local_ip = ipaddress.IPv4Address(pi_ip)
        if not phone_ip.is_private or phone_ip.is_loopback or phone_ip.is_link_local:
            raise ValueError("The stream must come from a local phone")
        if phone_ip not in ipaddress.IPv4Network(f"{local_ip}/24", strict=False):
            raise ValueError("Connect the phone and Pi to the same Wi-Fi network")
        port = parsed.port or 554
    except (ipaddress.AddressValueError, ValueError) as error:
        raise ValueError(f"Invalid same-Wi-Fi RTSP address: {error}") from error
    if port not in (554, 8554, 8555):
        raise ValueError("Set the ScreenStream RTSP server port to 8554")
    if not parsed.path.startswith("/") or "\n" in url or "\r" in url:
        raise ValueError("Invalid RTSP stream path")
    return str(url).strip()


def photo_signature(filename, header):
    suffix = Path(filename).suffix.lower()
    return (
        (suffix in (".jpg", ".jpeg") and header.startswith(b"\xff\xd8\xff"))
        or (suffix == ".png" and header.startswith(b"\x89PNG\r\n\x1a\n"))
        or (suffix == ".webp" and header.startswith(b"RIFF")
            and header[8:12] == b"WEBP")
        or (suffix == ".gif" and header.startswith((b"GIF87a", b"GIF89a")))
    )


class GuestCastSession:
    def __init__(self, cache_path=None, time_fn=None):
        self.lock = threading.RLock()
        self.now = time_fn or time.time
        self.cache = Path(cache_path or Path.home() / ".cache" / "piradio-guest-cast")
        self.cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            self.cache.chmod(0o700)
        except OSError:
            pass
        self.active = False
        self.pin = None
        self.pin_expires = 0
        self.tokens = {}
        self.attempts = {}
        self.current_files = []
        self.session_id = 0

    def open(self):
        """Called only on the physical Pi touchscreen."""
        with self.lock:
            self.active = True
            self.pin = f"{secrets.randbelow(1_000_000):06d}"
            self.pin_expires = self.now() + 600
            return self.screen_state()

    def screen_state(self):
        with self.lock:
            return {
                "active": self.active,
                "pin": self.pin if self.active and self.now() < self.pin_expires else None,
                "seconds_left": max(0, int(self.pin_expires - self.now())) if self.active else 0,
            }

    def close(self):
        with self.lock:
            self.active = False
            self.pin = None
            self.pin_expires = 0
            self.tokens.clear()
            self.attempts.clear()
            self.session_id += 1

    def public_status(self):
        with self.lock:
            return {"pairing_open": bool(self.active and self.now() < self.pin_expires)}

    def pair(self, candidate, client_ip):
        with self.lock:
            now = self.now()
            recent = [t for t in self.attempts.get(client_ip, []) if now - t < 300]
            if len(recent) >= 8:
                self.attempts[client_ip] = recent
                raise PermissionError("Too many PIN attempts. Try again later.")
            recent.append(now)
            self.attempts[client_ip] = recent
            if not self.active or now >= self.pin_expires:
                raise PermissionError("Open CAST on the Pi screen to obtain a fresh PIN")
            if not isinstance(candidate, str) or not re.fullmatch(r"\d{6}", candidate):
                raise PermissionError("Enter the six-digit PIN on the Pi screen")
            if not secrets.compare_digest(candidate, self.pin):
                raise PermissionError("Incorrect PIN")
            token = secrets.token_urlsafe(32)
            self.tokens[token] = now + 3600
            self.attempts.pop(client_ip, None)
            return token

    def authorize(self, token):
        if not isinstance(token, str) or len(token) > 128:
            return False
        with self.lock:
            if not self.active:
                return False
            expiry = self.tokens.get(token, 0)
            if expiry <= self.now():
                self.tokens.pop(token, None)
                return False
            return True

    def require_auth(self):
        raw = request.headers.get("Authorization", "")
        token = raw[7:] if raw.startswith("Bearer ") else ""
        return self.authorize(token)

    def allocate(self, uploads):
        """Save selected files with random names. Return safe local paths/kind.

        File uploads are bounded both by Flask's request limit and streaming
        chunk limits. A failed upload does not invalidate the previous media.
        """
        if not uploads or len(uploads) > MAX_PHOTOS:
            raise ValueError(f"Choose 1 to {MAX_PHOTOS} files")
        types = {media_kind(item.filename or "") for item in uploads}
        if len(types) != 1 or None in types:
            raise ValueError("Choose supported audio, video, or photos of one type")
        kind = next(iter(types))
        if kind != "photos" and len(uploads) != 1:
            raise ValueError("Send one audio or video file at a time")
        if shutil.disk_usage(self.cache).free < 400 * 1024 * 1024:
            raise ValueError("Not enough free disk space for guest uploads")
        saved = []
        total = 0
        try:
            for item in uploads:
                ext = Path(secure_filename(item.filename)).suffix.lower()
                unique = secrets.token_hex(12) + ext
                destination = self.cache / unique
                written = 0
                head = b""
                with destination.open("xb") as output:
                    os.chmod(destination, 0o600)
                    saved.append(destination)
                    while True:
                        chunk = item.stream.read(1024 * 1024)
                        if not chunk:
                            break
                        if not head:
                            head = chunk[:16]
                        written += len(chunk)
                        total += len(chunk)
                        if total > MAX_UPLOAD_BYTES or (
                            kind == "photos" and written > MAX_PHOTO_BYTES
                        ):
                            raise ValueError("File too large (256 MB total, 20 MB per photo)")
                        output.write(chunk)
                if written == 0:
                    raise ValueError("Empty file")
                if kind == "photos" and not photo_signature(item.filename, head):
                    raise ValueError("Unsupported or invalid image file")
            return [str(path) for path in saved], kind
        except Exception:
            for path in saved:
                path.unlink(missing_ok=True)
            raise

    def replace_files(self, files):
        with self.lock:
            old = self.current_files
            self.current_files = list(files)
            for filename in old:
                if filename not in self.current_files:
                    try:
                        Path(filename).unlink(missing_ok=True)
                    except OSError:
                        pass

    def shutdown_files(self):
        self.replace_files([])


def register_cast_routes(app, session, get_backend, stop_existing_audio,
                         get_pi_ip, get_volume, set_volume):
    """Register browser-cast endpoints before the Flask server starts."""
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES + 8 * 1024 * 1024

    def fail(message, code=400):
        result = jsonify({"success": False, "error": message})
        result.headers["Cache-Control"] = "no-store"
        return result, code

    def auth():
        if not session.require_auth():
            return fail("Enter the PiRadio Cast PIN to connect", 401)
        return None

    @app.route("/cast", methods=["GET"])
    def cast_portal():
        result = Response(CAST_HTML, mimetype="text/html")
        result.headers["Cache-Control"] = "no-store"
        result.headers["X-Content-Type-Options"] = "nosniff"
        result.headers["Content-Security-Policy"] = (
            "default-src 'none'; base-uri 'none'; form-action 'self'; "
            "script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
            "connect-src 'self'; img-src 'self' data:"
        )
        return result

    @app.route("/api/cast/public", methods=["GET"])
    def cast_public():
        return jsonify(session.public_status())

    @app.route("/api/cast/pair", methods=["POST"])
    def cast_pair():
        data = request.get_json(silent=True) or {}
        try:
            token = session.pair(data.get("pin"), request.remote_addr or "unknown")
            return jsonify({"success": True, "token": token})
        except PermissionError as error:
            return fail(str(error), 403)

    @app.route("/api/cast/upload", methods=["POST"])
    def cast_upload():
        denied = auth()
        if denied:
            return denied
        try:
            files, kind = session.allocate(request.files.getlist("files"))
            backend = get_backend()
            if backend is None:
                raise RuntimeError("PiRadio video player is not ready")
            stop_existing_audio()
            if not backend.start_local(files, kind):
                raise RuntimeError("Could not start MPV")
            session.replace_files(files)
            return jsonify({"success": True, "kind": kind,
                            "count": len(files), "title": backend.title})
        except (ValueError, RuntimeError, OSError) as error:
            return fail(str(error))

    @app.route("/api/cast/youtube", methods=["POST"])
    def cast_youtube():
        denied = auth()
        if denied:
            return denied
        data = request.get_json(silent=True) or {}
        video_id = youtube_id_from_url(data.get("url", ""))
        if not video_id:
            return fail("Paste a valid YouTube video link (HTTPS)")
        try:
            backend = get_backend()
            if backend is None:
                raise RuntimeError("PiRadio is not ready")
            stop_existing_audio()
            backend.start_youtube(video_id, title="Guest YouTube video")
            backend.volume(get_volume())
            session.shutdown_files()
            return jsonify({"success": True, "video_id": video_id})
        except (RuntimeError, OSError, ValueError) as error:
            return fail(str(error))

    @app.route("/api/cast/mirror", methods=["POST"])
    def cast_mirror():
        denied = auth()
        if denied:
            return denied
        data = request.get_json(silent=True) or {}
        try:
            stream = validate_rtsp(data.get("url") or "", get_pi_ip())
            backend = get_backend()
            if backend is None:
                raise RuntimeError("PiRadio is not ready")
            stop_existing_audio()
            backend.start_network_stream(stream, title="Android screen mirror")
            backend.volume(get_volume())
            session.shutdown_files()
            return jsonify({"success": True, "message": "RTSP receiver started"})
        except (RuntimeError, OSError, ValueError) as error:
            return fail(str(error))

    @app.route("/api/cast/status", methods=["GET"])
    def cast_status():
        denied = auth()
        if denied:
            return denied
        backend = get_backend()
        status = backend.playback_status() if backend else {"playing": False}
        return jsonify({"success": True, **status, "volume": get_volume()})

    @app.route("/api/cast/control", methods=["POST"])
    def cast_control():
        denied = auth()
        if denied:
            return denied
        data = request.get_json(silent=True) or {}
        action = str(data.get("action", ""))
        backend = get_backend()
        if backend is None or not backend.is_playing():
            return fail("Nothing is playing on PiRadio")
        result = False
        try:
            if action == "pause":
                result = backend.pause()
            elif action == "stop":
                backend.stop()
                session.shutdown_files()
                return jsonify({"success": True, "playing": False})
            elif action == "seek_relative":
                delta = float(data.get("seconds", 0))
                if abs(delta) > 120:
                    return fail("Seek is limited to two minutes per tap")
                result = backend.seek(delta)
            elif action == "seek":
                seconds = float(data.get("seconds", 0))
                if not 0 <= seconds <= 24 * 3600:
                    return fail("Invalid seek position")
                result = backend.seek_absolute(seconds)
            elif action == "next":
                result = backend._command("playlist-next", "weak")
            elif action == "previous":
                result = backend._command("playlist-prev", "weak")
            elif action == "volume":
                requested = int(data.get("value", -1))
                if not 0 <= requested <= 100:
                    return fail("Volume must be 0–100")
                set_volume(requested)
                result = True
            elif action == "minimize" and backend.source_type not in ("guest_photos", "screen_mirror"):
                result = backend.minimize_audio()
            elif action == "restore":
                result = backend.restore_video()
            else:
                return fail("Unsupported control")
        except (ValueError, TypeError, OverflowError) as error:
            return fail(str(error))
        if not result:
            return fail("The player did not accept this command", 409)
        return jsonify({"success": True})

    return session


CAST_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#050505">
<title>PiRadio Cast · Guest</title>
<style>
:root{color-scheme:dark;--bg:#050505;--card:#141414;--border:#414141;--fg:#fff;--muted:#b0b0b0;--accent:#35d6e8}
*{box-sizing:border-box}body{margin:0;padding:20px 16px 60px;background:var(--bg);color:var(--fg);font:16px system-ui,sans-serif}
main{max-width:650px;margin:auto}h1{font-size:26px;margin:5px 0}h2{font-size:18px;margin:8px 0 14px}
p{line-height:1.5;color:var(--muted)}.sub{margin-top:2px;font-size:14px}
.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:18px;margin:16px 0}
label{display:block;font-size:14px;color:#ddd;margin:10px 0 7px}
input[type=text],input[type=password],input[type=url],input[type=file]{width:100%;min-height:47px;padding:12px;border:1px solid #777;border-radius:11px;background:#070707;color:white;font-size:16px}
button{min-height:46px;border-radius:11px;border:1px solid #777;background:#292929;color:#fff;font:600 15px system-ui;padding:9px 14px;cursor:pointer}
button.main{background:var(--accent);color:#001a20;border:0}button:disabled{opacity:.4;cursor:not-allowed}
button:focus-visible,input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.actions>*{flex:1}
.row{display:flex;justify-content:space-between;align-items:center;gap:12px}
.note{font-size:13px;color:#aaa}.pill{font-size:12px;border:1px solid #666;border-radius:999px;padding:6px 10px;color:var(--accent)}
#status{min-height:25px;color:var(--accent);white-space:pre-wrap}#connected{display:none}
#playbackTitle{font-size:17px;font-weight:650;overflow-wrap:anywhere}
#seek{width:100%;accent-color:var(--accent);margin:13px 0;min-height:22px}
#volume{width:100%;accent-color:white}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.tabbar{display:flex;gap:8px;margin:14px 0}.tabbar button{flex:1}
.hidden{display:none!important}
</style>
</head>
<body>
<main>
<div class="row"><div><h1>◉ PiRadio Cast</h1><div class="sub">Share from your phone to the 7-inch PiRadio screen</div></div><span class="pill">PRIVATE Wi-Fi</span></div>
<p id="status" role="status">Open CAST on the PiRadio screen to start pairing.</p>
<section id="pair" class="card">
<h2>Connect to PiRadio</h2>
<p>Join the same Wi-Fi as the Raspberry Pi. Open <strong>CAST</strong> on its touchscreen and enter the six-digit code shown there.</p>
<label for="pin">Six-digit pairing PIN</label>
<input id="pin" type="text" inputmode="numeric" pattern="[0-9]*" maxlength="6" autocomplete="one-time-code" placeholder="000000">
<div class="actions"><button id="pairButton" class="main">Connect</button></div>
</section>
<div id="connected">
<section class="card">
<div class="row"><h2>Send to PiRadio</h2><span class="pill">Connected</span></div>
<label for="files">Music, video, or photos (up to 20 photos)</label>
<input type="file" id="files" multiple accept="image/jpeg,image/png,image/webp,image/gif,audio/*,video/*">
<p class="note">Supported: JPG, PNG, WebP, GIF; MP3, AAC, M4A, OGG, FLAC, WAV; MP4, MOV, WebM, MKV. Up to 256 MB per upload. Files stay on the Pi temporarily.</p>
<button class="main" id="sendFiles">Send selected files</button>
<div class="tabbar">
<button id="tabYouTube">YouTube link</button>
<button id="tabMirror">Android screen mirror</button>
</div>
<div id="youtubePanel" class="hidden">
<label for="ytUrl">Paste a YouTube link</label>
<input type="url" id="ytUrl" placeholder="https://www.youtube.com/watch?v=...">
<button id="sendYouTube">Play on PiRadio</button>
</div>
<div id="mirrorPanel" class="hidden">
<p class="note">For Android screen mirroring, install ScreenStream on the sending phone, choose <b>RTSP → Server</b>, set port 8554, start sharing, then paste its displayed RTSP address below. Some apps block protected video/audio capture.</p>
<label for="rtspUrl">RTSP server address from phone</label>
<input id="rtspUrl" type="url" placeholder="rtsp://phone-ip:8554/path">
<button id="startMirror">Show phone screen on PiRadio</button>
</div>
</section>
<section class="card">
<div class="row"><h2>Now playing</h2><span id="playState" class="pill">Idle</span></div>
<div id="playbackTitle">Waiting for media...</div>
<div class="row note"><span id="elapsed">0:00</span><span id="duration">--:--</span></div>
<input type="range" id="seek" min="0" max="1" value="0" step="0.5" disabled>
<div class="grid">
<button data-action="previous">Previous photo</button>
<button data-action="next">Next photo</button>
<button data-action="seek_relative" data-value="-10">↶ 10s</button>
<button data-action="seek_relative" data-value="10">10s ↷</button>
<button data-action="pause" class="main">Play / Pause</button>
<button data-action="restore">Fullscreen</button>
<button data-action="minimize">Audio only</button>
<button data-action="stop">Stop</button>
</div>
<label for="volume">Volume: <span id="volumeText">50%</span></label>
<input type="range" id="volume" min="0" max="100" step="1" value="50">
</section>
</div>
<p class="note">No PiRadio remote installation required. This portal is not Google's Chromecast protocol; YouTube's Cast button and system-level Cast discovery are not supported.</p>
</main>
<script>
"use strict";
let token = "", seeking = false, timer = null;
const el = id => document.getElementById(id);
function message(text){el("status").textContent=text;}
function fmt(n){n=Number(n);if(!Number.isFinite(n))return "--:--";n=Math.max(0,Math.floor(n));return Math.floor(n/3600)?Math.floor(n/3600)+":"+String(Math.floor(n/60)%60).padStart(2,"0")+":"+String(n%60).padStart(2,"0"):Math.floor(n/60)+":"+String(n%60).padStart(2,"0");}
async function api(path, options={}){
  const headers = {...(options.headers||{})};
  if(token)headers.Authorization="Bearer "+token;
  const resp=await fetch(path,{...options,headers,cache:"no-store"});
  const data=await resp.json();
  if(!resp.ok || data.success===false){
    if(resp.status===401){token="";el("pair").style.display="block";el("connected").style.display="none";}
    throw new Error(data.error||"Request failed");
  }
  return data;
}
async function send(action,extra={}){
  try{
    const result=await api("/api/cast/control",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action,...extra})});
    await poll();return result;
  }catch(e){message(e.message);}
}
async function poll(){
 if(!token)return;
 try{
  const s=await api("/api/cast/status");
  el("playbackTitle").textContent=s.playing?(s.title||"PiRadio media"):"Waiting for media...";
  el("playState").textContent=!s.playing?"Idle":s.paused?"Paused":s.minimized?"Audio only":"Playing";
  const duration=Number(s.duration)||0,position=Number(s.position)||0;
  el("elapsed").textContent=fmt(position);el("duration").textContent=duration?fmt(duration):"--:--";
  const slider=el("seek");
  slider.max=Math.max(1,duration);slider.disabled=!(duration>0);
  if(!seeking)slider.value=Math.min(duration,Math.max(0,position));
  if(document.activeElement!==el("volume"))el("volume").value=s.volume;
  el("volumeText").textContent=s.volume+"%";
 }catch(e){message(e.message);}
}
el("pairButton").addEventListener("click",async()=>{
 try{
  const result=await api("/api/cast/pair",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({pin:el("pin").value.trim()})});
  token=result.token;el("pin").value="";
  el("pair").style.display="none";el("connected").style.display="block";
  message("Connected. Your phone now controls media on PiRadio.");
  await poll();
  if(timer)clearInterval(timer);
  timer=setInterval(poll,2000);
 }catch(e){message(e.message);}
});
el("sendFiles").addEventListener("click",async()=>{
 const files=el("files").files;
 if(!files.length){message("Choose one or more files first.");return;}
 const button=el("sendFiles");button.disabled=true;message("Uploading to PiRadio...");
 try{
  const form=new FormData();
  for(const file of files)form.append("files",file,file.name);
  const result=await api("/api/cast/upload",{method:"POST",body:form});
  message("Sent "+result.count+" file(s). Playing on PiRadio.");
  await poll();
 }catch(e){message(e.message);}finally{button.disabled=false;}
});
el("tabYouTube").addEventListener("click",()=>{el("youtubePanel").classList.toggle("hidden");el("mirrorPanel").classList.add("hidden");});
el("tabMirror").addEventListener("click",()=>{el("mirrorPanel").classList.toggle("hidden");el("youtubePanel").classList.add("hidden");});
el("sendYouTube").addEventListener("click",async()=>{
 try{await api("/api/cast/youtube",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url:el("ytUrl").value})});message("Starting YouTube on PiRadio...");await poll();}
 catch(e){message(e.message);}
});
el("startMirror").addEventListener("click",async()=>{
 try{await api("/api/cast/mirror",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url:el("rtspUrl").value})});message("Starting screen mirror...");await poll();}
 catch(e){message(e.message);}
});
document.querySelectorAll("[data-action]").forEach(button=>{
 button.addEventListener("click",()=>{const extra=button.dataset.value?{seconds:Number(button.dataset.value)}:{};send(button.dataset.action,extra);});
});
el("seek").addEventListener("pointerdown",()=>{seeking=true;});
el("seek").addEventListener("change",async e=>{seeking=false;await send("seek",{seconds:Number(e.target.value)});});
el("seek").addEventListener("pointerup",()=>{seeking=false;});
el("volume").addEventListener("change",e=>send("volume",{value:Number(e.target.value)}));
el("volume").addEventListener("input",e=>{el("volumeText").textContent=e.target.value+"%";});
fetch("/api/cast/public",{cache:"no-store"}).then(r=>r.json()).then(d=>{
 if(d.pairing_open)message("Pairing is open. Enter the PIN shown on PiRadio.");
}).catch(()=>message("Unable to reach PiRadio. Check Wi-Fi."));
</script>
</body>
</html>"""

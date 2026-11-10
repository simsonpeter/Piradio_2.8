"""PiRadio 7-inch Smart Photo Frame.

Native 800x480 Pygame slideshow, configured from a PIN-protected phone webpage.
Photos live in ~/Pictures/PiRadio-Frame. Nothing here stops or owns the VLC/MPV
audio engines. Pillow downsizes decoding on a background thread.
"""
from datetime import datetime
from io import BytesIO
import json
import os
from pathlib import Path
import random
import re
import secrets
import shutil
import threading
import time

from flask import Response, jsonify, request
from PIL import Image, ImageOps, UnidentifiedImageError
import pygame
import qrcode
from werkzeug.utils import secure_filename

Image.MAX_IMAGE_PIXELS = 60_000_000

ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_PHOTOS = 300
MAX_UPLOAD = 128 * 1024 * 1024
MAX_FILE = 20 * 1024 * 1024
MAX_GALLERY_BYTES = 1024 * 1024 * 1024
DURATIONS = (5, 8, 12, 20, 30)
DEFAULTS = {
    "interval": 8,
    "shuffle": True,
    "fit": "cover",
    "clock": True,
    "weather": True,
    "auto_idle": False,
}
FRAME_BUTTON = pygame.Rect(578, 9, 105, 36)
PHOTO_PREVIOUS = pygame.Rect(311, 409, 63, 50)
PHOTO_PAUSE = pygame.Rect(384, 405, 70, 58)
PHOTO_NEXT = pygame.Rect(465, 409, 63, 50)
PHOTO_ADD = pygame.Rect(18, 409, 180, 48)
PHOTO_SETTINGS = pygame.Rect(540, 409, 110, 48)
PHOTO_CLOSE = pygame.Rect(682, 12, 105, 46)
PHOTO_QR = pygame.Rect(155, 103, 228, 228)


def _image_header(filename, content):
    ext = Path(filename).suffix.lower()
    return (
        ext in (".jpg", ".jpeg") and content.startswith(b"\xff\xd8\xff")
        or ext == ".png" and content.startswith(b"\x89PNG\r\n\x1a\n")
        or ext == ".webp" and content.startswith(b"RIFF")
           and content[8:12] == b"WEBP"
        or ext == ".gif" and content.startswith((b"GIF87a", b"GIF89a"))
    )


class PhotoFrameLibrary:
    """Persistent album, simple options, explicit pairing and upload limits."""
    def __init__(self, root=None, settings_path=None, clock=None):
        self.root = Path(root or Path.home() / "Pictures" / "PiRadio-Frame")
        self.root.mkdir(parents=True, exist_ok=True)
        self.settings_path = Path(settings_path or Path.home() / ".config" / "piradio-photo-frame.json")
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock or time.time
        self.lock = threading.RLock()
        self.options = dict(DEFAULTS)
        self._load_options()
        self.pairing = False
        self.pin = None
        self.pin_expires = 0
        self.tokens = {}
        self.attempts = {}
        self.commands = []

    def _load_options(self):
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            for name, value in data.items():
                if self.valid_option(name, value):
                    self.options[name] = value
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    @staticmethod
    def valid_option(name, value):
        if name == "interval":
            return type(value) is int and value in DURATIONS
        if name == "fit":
            return value in ("cover", "contain")
        if name in ("shuffle", "clock", "weather", "auto_idle"):
            return type(value) is bool
        return False

    def set_options(self, values):
        if not isinstance(values, dict) or not values:
            raise ValueError("No valid settings provided")
        if any(not self.valid_option(k, v) for k, v in values.items()):
            raise ValueError("Invalid frame setting")
        with self.lock:
            self.options.update(values)
            tmp = self.settings_path.with_suffix(".tmp")
            try:
                tmp.write_text(json.dumps(self.options, indent=2), encoding="utf-8")
                tmp.replace(self.settings_path)
            finally:
                tmp.unlink(missing_ok=True)
            return dict(self.options)

    def list_photos(self):
        try:
            return sorted(
                (p for p in self.root.iterdir() if p.is_file()
                 and not p.is_symlink() and p.suffix.lower() in ALLOWED),
                key=lambda p: p.name.lower(),
            )[:MAX_PHOTOS]
        except OSError:
            return []

    def start_pairing(self):
        with self.lock:
            self.pairing = True
            self.pin = f"{secrets.randbelow(1000000):06d}"
            self.pin_expires = self.clock() + 600
            # Opening a fresh owner pairing window revokes prior guest sessions.
            self.tokens.clear()
            return self.screen_pairing()

    def screen_pairing(self):
        with self.lock:
            remaining = max(0, int(self.pin_expires - self.clock()))
            return {
                "pairing": bool(self.pairing and remaining),
                "pin": self.pin if self.pairing and remaining else None,
                "remaining": remaining,
            }

    def close_pairing(self):
        with self.lock:
            self.pairing = False
            self.pin = None
            self.pin_expires = 0
            self.tokens.clear()
            self.commands.clear()

    def pair(self, code, address):
        with self.lock:
            now = self.clock()
            history = [t for t in self.attempts.get(address, []) if now - t < 300]
            if len(history) >= 8:
                raise PermissionError("Too many PIN attempts. Retry in five minutes")
            history.append(now)
            self.attempts[address] = history
            if not self.pairing or now >= self.pin_expires:
                raise PermissionError("Open Photo Frame on PiRadio to see a fresh PIN")
            if not isinstance(code, str) or not re.fullmatch(r"\d{6}", code):
                raise PermissionError("Enter the six-digit code on PiRadio")
            if not secrets.compare_digest(code, self.pin):
                raise PermissionError("Incorrect PIN")
            self.attempts.pop(address, None)
            token = secrets.token_urlsafe(32)
            self.tokens[token] = now + 3600
            return token

    def authorize(self, request_object):
        raw = request_object.headers.get("Authorization", "")
        token = raw[7:] if raw.startswith("Bearer ") else ""
        with self.lock:
            return bool(
                self.pairing and token in self.tokens
                and self.tokens[token] > self.clock()
            )

    def add_photos(self, uploads):
        if not uploads or len(uploads) > 20:
            raise ValueError("Select 1–20 image files")
        existing = self.list_photos()
        if len(existing) + len(uploads) > MAX_PHOTOS:
            raise ValueError("Gallery limit: 300 photos")
        used = sum(p.stat().st_size for p in existing)
        if shutil.disk_usage(self.root).free < 200 * 1024 * 1024:
            raise ValueError("Not enough free disk space")
        stored = []
        total = 0
        try:
            for upload in uploads:
                basename = secure_filename(upload.filename or "")[:80]
                suffix = Path(basename).suffix.lower()
                if suffix not in ALLOWED:
                    raise ValueError("Only JPEG, PNG, WebP and GIF images are supported")
                target = self.root / (secrets.token_hex(10) + "_" + basename)
                # A temporary file avoids exposing a partially written image.
                temporary = self.root / (secrets.token_hex(12) + ".upload")
                header = b""
                size = 0
                try:
                    with temporary.open("xb") as out:
                        os.chmod(temporary, 0o600)
                        while True:
                            chunk = upload.stream.read(1024 * 1024)
                            if not chunk:
                                break
                            if not header:
                                header = chunk[:16]
                            size += len(chunk)
                            total += len(chunk)
                            if size > MAX_FILE or total > MAX_UPLOAD or (
                                    used + total > MAX_GALLERY_BYTES):
                                raise ValueError("Photo too large or gallery storage limit reached")
                            out.write(chunk)
                    if not size or not _image_header(basename, header):
                        raise ValueError("Invalid image data")
                    with Image.open(temporary) as picture:
                        picture.verify()
                    temporary.rename(target)
                    stored.append(target)
                finally:
                    temporary.unlink(missing_ok=True)
            return len(stored)
        except Exception:
            for image in stored:
                image.unlink(missing_ok=True)
            raise

    def request_command(self, action):
        if action not in ("next", "previous", "pause", "resume", "open", "close", "refresh"):
            raise ValueError("Unsupported Photo Frame control")
        with self.lock:
            self.commands.append(action)
            self.commands = self.commands[-20:]

    def consume_commands(self):
        with self.lock:
            result = self.commands[:]
            self.commands.clear()
            return result


def register_frame_routes(app, library):
    """Phone portal with a separate limited frame PIN, no public upload route."""
    app.config["MAX_CONTENT_LENGTH"] = max(
        app.config.get("MAX_CONTENT_LENGTH") or 0, MAX_UPLOAD + 4 * 1024 * 1024)

    def unauthorized():
        return jsonify({"success": False, "error": "Pair using the PIN on PiRadio"}), 401

    @app.route("/frame")
    def photo_frame_portal():
        result = Response(FRAME_HTML, mimetype="text/html")
        result.headers["Cache-Control"] = "no-store"
        result.headers["X-Content-Type-Options"] = "nosniff"
        result.headers["Content-Security-Policy"] = (
            "default-src 'none'; base-uri 'none'; form-action 'self'; "
            "script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
            "connect-src 'self'; img-src 'self' data:"
        )
        return result

    @app.route("/api/frame/pair", methods=["POST"])
    def photo_frame_pair():
        pin = (request.get_json(silent=True) or {}).get("pin")
        try:
            token = library.pair(pin, request.remote_addr or "unknown")
            return jsonify({"success": True, "token": token})
        except PermissionError as error:
            return jsonify({"success": False, "error": str(error)}), 403

    @app.route("/api/frame/status")
    def photo_frame_status():
        if not library.authorize(request):
            return unauthorized()
        return jsonify({
            "success": True,
            "photos": len(library.list_photos()),
            "settings": dict(library.options),
        })

    @app.route("/api/frame/upload", methods=["POST"])
    def photo_frame_upload():
        if not library.authorize(request):
            return unauthorized()
        try:
            count = library.add_photos(request.files.getlist("photos"))
            library.request_command("refresh")
            return jsonify({"success": True, "added": count,
                            "total": len(library.list_photos())})
        except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError) as error:
            return jsonify({"success": False, "error": str(error)}), 400

    @app.route("/api/frame/options", methods=["POST"])
    def photo_frame_options():
        if not library.authorize(request):
            return unauthorized()
        try:
            options = library.set_options(request.get_json(silent=True) or {})
            library.request_command("refresh")
            return jsonify({"success": True, "settings": options})
        except (OSError, ValueError) as error:
            return jsonify({"success": False, "error": str(error)}), 400

    @app.route("/api/frame/control", methods=["POST"])
    def photo_frame_control():
        if not library.authorize(request):
            return unauthorized()
        action = (request.get_json(silent=True) or {}).get("action")
        try:
            library.request_command(action)
            return jsonify({"success": True, "action": action})
        except ValueError as error:
            return jsonify({"success": False, "error": str(error)}), 400


class PhotoFrameRenderer:
    """Large photo slideshow. UI Pygame operations remain on main thread."""
    def __init__(self, library):
        self.library = library
        self.photos = []
        self.index = 0
        self.path = None
        self.ready = None
        self.image = None
        self.previous = None
        self.change_at = 0
        self.image_changed_at = 0
        self.loading = False
        self.generation = 0
        self.waiting_for = None
        self.paused = False
        self.controls_until = 0
        self.show_pairing = False
        self.next_scan = 0
        self.last_options = None
        self.qr_cache = None

    def refresh(self, now=None):
        now = now or time.time()
        existing = self.path
        ordered = self.library.list_photos()
        if self.library.options["shuffle"]:
            random.shuffle(ordered)
        self.photos = ordered
        self.index = self.photos.index(existing) if existing in self.photos else 0
        self.next_scan = now + 20
        self.change_at = now + self.library.options["interval"]

    def activate(self, now):
        self.library.start_pairing()
        self.controls_until = now + 9
        self.show_pairing = not bool(self.library.list_photos())
        self.refresh(now)

    def close(self):
        self.library.close_pairing()
        self.show_pairing = False

    def step(self, direction, now):
        if not self.photos:
            self.refresh(now)
        if self.photos:
            self.index = (self.index + direction) % len(self.photos)
            self.path = None
            self.change_at = now + self.library.options["interval"]
            self.controls_until = now + 5

    def _decode_worker(self, source, generation, fit):
        try:
            with Image.open(source) as image:
                image.seek(0)
                source_image = ImageOps.exif_transpose(image).convert("RGB")
                if fit == "cover":
                    transformed = ImageOps.fit(
                        source_image, (800, 480), Image.Resampling.LANCZOS,
                        centering=(0.5, 0.5))
                else:
                    source_image.thumbnail((800, 480), Image.Resampling.LANCZOS)
                    transformed = Image.new("RGB", (800, 480), (0, 0, 0))
                    transformed.paste(source_image,
                                      ((800-source_image.width)//2,
                                       (480-source_image.height)//2))
                pixels = transformed.tobytes()
        except (OSError, ValueError, UnidentifiedImageError,
                Image.DecompressionBombError):
            pixels = None
        self.ready = (generation, source, pixels)

    def tick(self, now):
        if now >= self.next_scan:
            known = set(self.photos)
            current = set(self.library.list_photos())
            if known != current or self.last_options != self.library.options:
                self.refresh(now)
                self.path = None
            else:
                self.next_scan = now + 20
        self.last_options = dict(self.library.options)
        if not self.photos:
            self.image = None
            self.path = None
            return
        if not self.paused and now >= self.change_at and self.image is not None:
            self.step(1, now)
        current_path = self.photos[self.index]
        if current_path != self.path and not self.loading:
            self.loading = True
            self.generation += 1
            thread = threading.Thread(
                target=self._decode_worker,
                args=(current_path, self.generation, self.library.options["fit"]),
                daemon=True)
            thread.start()
            self.waiting_for = current_path
        if self.ready is not None:
            generation, source, pixels = self.ready
            self.ready = None
            if generation == self.generation and source == self.waiting_for:
                self.loading = False
                if pixels is None:
                    self.path = source
                    # Skip corrupt image on next interval; never crash Pygame.
                    self.change_at = now + 2
                    return
                self.previous = self.image
                self.image = pygame.image.fromstring(pixels, (800,480), "RGB")
                self.path = source
                self.image_changed_at = now
                self.change_at = now + self.library.options["interval"]

    def _text(self, surface, font, value, x, y, color=(255,255,255)):
        text = font.render(str(value), True, color)
        surface.blit(text, (x,y))
        return text

    def _qr(self, url):
        if self.qr_cache is None or self.qr_cache[0] != url:
            image = qrcode.make(url, border=2, box_size=6).convert("RGB")
            pixels = image.tobytes()
            qr = pygame.image.fromstring(pixels, image.size, "RGB")
            self.qr_cache = (url, pygame.transform.smoothscale(qr, (210,210)))
        return self.qr_cache[1]

    def draw(self, surface, font, small, tiny, now, city="", temperature=None,
             playing="", url="", ambient=False):
        self.tick(now)
        surface.fill((0,0,0))
        if self.image is not None:
            surface.blit(self.image, (0,0))
            if self.previous is not None:
                ratio = (now - self.image_changed_at) / 0.6
                if ratio < 1:
                    previous = self.previous.copy()
                    previous.set_alpha(int(255 * max(0,1-ratio)))
                    surface.blit(previous,(0,0))
                else:
                    self.previous = None
        else:
            big = pygame.font.Font(None, 46)
            label = "Your memories, beautifully displayed"
            heading = big.render(label, True, (239,239,239))
            surface.blit(heading, heading.get_rect(center=(400,165)))
            self._text(surface, small, "Add photos from your phone to begin",
                       268, 224, (173,173,173))

        if self.library.options["clock"]:
            shadow = pygame.Surface((293,94), pygame.SRCALPHA)
            pygame.draw.rect(shadow,(0,0,0,145),shadow.get_rect(),border_radius=14)
            surface.blit(shadow,(18,18))
            time_big = pygame.font.Font(None,68)
            self._text(surface,time_big,datetime.now().strftime("%H:%M"),
                       31,24)
            self._text(surface,tiny,datetime.now().strftime("%a, %d %b %Y"),
                       36,83,(198,198,198))
        if self.library.options["weather"] and temperature is not None:
            chip = pygame.Surface((186,66),pygame.SRCALPHA)
            pygame.draw.rect(chip,(0,0,0,150),chip.get_rect(),border_radius=14)
            surface.blit(chip,(601,20))
            self._text(surface,small,f"{temperature}°C",617,25)
            self._text(surface,tiny,str(city)[:19],617,53,(218,218,218))

        if ambient:
            return
        # Tap once to display clean, temporary controls over the photograph.
        if now < self.controls_until or not self.photos:
            bottom = pygame.Surface((800,90),pygame.SRCALPHA)
            bottom.fill((0,0,0,190))
            surface.blit(bottom,(0,390))
            self._text(surface,tiny,
                       f"PHOTO FRAME   {self.index+1 if self.photos else 0}/{len(self.photos)}",
                       205,432,(187,187,187))
            for rect,label,primary in (
                (PHOTO_ADD, "ADD PHOTOS",False),
                (PHOTO_PREVIOUS, "◀",False),
                (PHOTO_PAUSE, "▶" if self.paused else "Ⅱ",True),
                (PHOTO_NEXT, "▶",False),
                (PHOTO_SETTINGS, "FIT / FILL",False),
                (PHOTO_CLOSE, "EXIT",False),
            ):
                fill = (238,238,238) if primary else (29,29,29)
                pygame.draw.rect(surface,fill,rect,border_radius=10)
                pygame.draw.rect(surface,(91,91,91),rect,1,border_radius=10)
                label_surf=tiny.render(label,True,(0,0,0) if primary else (255,255,255))
                surface.blit(label_surf,label_surf.get_rect(center=rect.center))
            if playing:
                self._text(surface,tiny,str(playing)[:52],15,370,(245,245,245))
        if self.show_pairing or not self.photos:
            shade = pygame.Surface((800,480),pygame.SRCALPHA)
            shade.fill((0,0,0,215))
            surface.blit(shade,(0,0))
            self._text(surface,font,"ADD PHOTOS TO PIRADIO",170,24)
            pygame.draw.rect(surface,(250,250,250),PHOTO_QR,border_radius=12)
            surface.blit(self._qr(url),(PHOTO_QR.x+9,PHOTO_QR.y+9))
            pairing=self.library.screen_pairing()
            self._text(surface,small,"1. Scan the QR code",417,144)
            self._text(surface,tiny,"2. Enter the six-digit PIN",417,183,(190,190,190))
            if pairing["pin"]:
                code_font=pygame.font.Font(None,64)
                self._text(surface,code_font,pairing["pin"],420,222,(72,219,229))
                self._text(surface,tiny,f"Valid for {pairing['remaining']//60} minutes",
                           423,284,(192,192,192))
            else:
                self._text(surface,small,"PIN expired. Tap RENEW",411,238,(72,219,229))
            self._text(surface,tiny,"Phone and Pi must use the same Wi-Fi",
                       411,311,(192,192,192))
            renew=pygame.Rect(413,339,146,45)
            done=pygame.Rect(571,339,167,45)
            for rect,label in ((renew,"RENEW PIN"),(done,"VIEW PHOTOS")):
                pygame.draw.rect(surface,(35,35,35),rect,border_radius=10)
                pygame.draw.rect(surface,(110,110,110),rect,1,border_radius=10)
                item=tiny.render(label,True,(250,250,250))
                surface.blit(item,item.get_rect(center=rect.center))
            exit_rect = pygame.Rect(682, 12, 105, 46)
            pygame.draw.rect(surface, (56, 31, 31), exit_rect, border_radius=11)
            pygame.draw.rect(surface, (128, 128, 128), exit_rect, 1, border_radius=11)
            exit_label = tiny.render("EXIT", True, (255, 255, 255))
            surface.blit(exit_label, exit_label.get_rect(center=exit_rect.center))
            self._text(surface,tiny,url,163,396,(204,204,204))

    def hit(self, point, now):
        """Tap to reveal actions, or handle visible overlay safely."""
        # The exit button must remain functional even with zero images.
        if PHOTO_CLOSE.collidepoint(point):
            return "close"
        if self.show_pairing or not self.photos:
            renew=pygame.Rect(413,339,146,45)
            done=pygame.Rect(571,339,167,45)
            if renew.collidepoint(point):
                self.library.start_pairing()
                return "consume"
            if done.collidepoint(point):
                self.show_pairing = False
                self.controls_until = now+8
                return "consume"
            return "consume"
        if now >= self.controls_until:
            self.controls_until = now + 7
            return "consume"
        self.controls_until = now + 8
        if PHOTO_CLOSE.collidepoint(point):
            return "close"
        if PHOTO_ADD.collidepoint(point):
            if not self.library.screen_pairing()["pin"]:
                self.library.start_pairing()
            self.show_pairing = True
            return "consume"
        if PHOTO_PREVIOUS.collidepoint(point):
            self.step(-1, now)
        elif PHOTO_NEXT.collidepoint(point):
            self.step(1, now)
        elif PHOTO_PAUSE.collidepoint(point):
            self.paused = not self.paused
            self.change_at = now + self.library.options["interval"]
        elif PHOTO_SETTINGS.collidepoint(point):
            return "settings"
        return "consume"


FRAME_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#080808">
<title>PiRadio Photo Frame</title>
<style>
:root{color-scheme:dark;--card:#161616;--muted:#bbb;--line:#494949;--highlight:#45dbea}
*{box-sizing:border-box}body{margin:0;background:#050505;color:white;font:16px system-ui,sans-serif;padding:18px 15px 50px}
main{max-width:600px;margin:auto}h1{font-size:27px;margin:8px 0}h2{font-size:19px;margin:0 0 12px}
p{color:var(--muted);line-height:1.5}section{background:var(--card);border:1px solid var(--line);border-radius:17px;padding:18px;margin:15px 0}
input[type=text],input[type=file],select{display:block;width:100%;min-height:45px;padding:10px;margin:8px 0 12px;background:#0d0d0d;color:white;border:1px solid #777;border-radius:10px;font-size:16px}
button{background:#343434;border:1px solid #777;border-radius:10px;color:white;font:600 15px system-ui;padding:12px;margin:3px;min-height:45px}
.primary{background:var(--highlight);color:#00171a;border:0}button:disabled{opacity:.4}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.row button{flex:1}
label{display:block;margin:12px 0 4px}.switch{display:flex;align-items:center;gap:12px}.switch input{width:22px;height:22px}
#online{color:var(--highlight);min-height:23px}#album{display:none}
</style>
</head><body>
<main><h1>PiRadio • Smart Photo Frame</h1>
<p>Send family photos to the 7-inch display, then enjoy an elegant slideshow with clock and weather.</p>
<p id="online">Tap PHOTO on PiRadio, scan the QR code, then enter the PIN.</p>
<section id="pair"><h2>Connect your phone</h2><label for="pin">Six-digit PIN on the Pi screen</label>
<input id="pin" type="text" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="000000">
<button id="connect" class="primary">Connect to Photo Frame</button></section>
<div id="album">
<section><h2>Your photo gallery</h2><p id="count">Loading photos...</p>
<label for="photos">Choose up to 20 photos</label>
<input id="photos" type="file" multiple accept="image/jpeg,image/png,image/webp,image/gif">
<p>JPEG, PNG, WebP and GIF. Up to 20 MB per photo and 128 MB per upload. Photos are saved on the Pi.</p>
<button id="send" class="primary">Add photos to frame</button>
<div class="row"><button data-control="previous">◀ Previous</button>
<button data-control="pause">Pause</button><button data-control="resume">Resume</button>
<button data-control="next">Next ▶</button></div>
<div class="row"><button data-control="open">Show photo frame</button>
<button data-control="close">Close frame</button></div>
</section>
<section><h2>Slideshow settings</h2>
<label for="interval">Time per photo</label>
<select id="interval"><option value="5">5 seconds</option><option value="8">8 seconds</option>
<option value="12">12 seconds</option><option value="20">20 seconds</option>
<option value="30">30 seconds</option></select>
<label for="fit">Photo layout</label><select id="fit">
<option value="cover">Fill entire screen (crop edges)</option>
<option value="contain">Show entire picture (black borders)</option></select>
<label class="switch"><input id="shuffle" type="checkbox">Shuffle pictures</label>
<label class="switch"><input id="clock" type="checkbox">Show clock</label>
<label class="switch"><input id="weather" type="checkbox">Show weather</label>
<label class="switch"><input id="auto_idle" type="checkbox">Use as idle screensaver</label>
<p>Idle screensaver is OFF by default to preserve your existing clock screensaver.</p>
<button id="save" class="primary">Save settings</button>
</section></div>
<p>For use on the same trusted Wi-Fi only. This is not Google Photos cloud sync.</p>
</main>
<script>
"use strict";
let token="";
const byId=x=>document.getElementById(x);
function message(x){byId("online").textContent=x;}
async function api(path,options={}){
 const headers={...(options.headers||{})};
 if(token)headers.Authorization="Bearer "+token;
 const response=await fetch(path,{...options,headers,cache:"no-store"});
 const data=await response.json();
 if(!response.ok||data.success===false){
  if(response.status===401){token="";byId("album").style.display="none";byId("pair").style.display="block";}
  throw new Error(data.error||"Request failed");
 }
 return data;
}
async function refresh(){
 const data=await api("/api/frame/status");
 byId("count").textContent=data.photos+" photo"+(data.photos===1?"":"s")+" saved on PiRadio";
 for(const key of ["interval","fit","shuffle","clock","weather","auto_idle"]){
  const el=byId(key);if(el.type==="checkbox")el.checked=data.settings[key];else el.value=String(data.settings[key]);
 }
}
byId("connect").addEventListener("click",async()=>{
 try{
  const data=await api("/api/frame/pair",{method:"POST",headers:{"Content-Type":"application/json"},
   body:JSON.stringify({pin:byId("pin").value.trim()})});
  token=data.token;byId("pin").value="";
  byId("pair").style.display="none";byId("album").style.display="block";
  message("Connected. You can add photos and control the frame.");await refresh();
 }catch(err){message(err.message);}
});
byId("send").addEventListener("click",async()=>{
 const photos=byId("photos").files;if(!photos.length){message("Choose photos first.");return;}
 const button=byId("send");button.disabled=true;message("Sending photos...");
 try{
  const form=new FormData();for(const f of photos)form.append("photos",f,f.name);
  const data=await api("/api/frame/upload",{method:"POST",body:form});
  byId("count").textContent=data.total+" photos saved on PiRadio";
  byId("photos").value="";message("Added "+data.added+" photos successfully.");
 }catch(err){message(err.message);}finally{button.disabled=false;}
});
byId("save").addEventListener("click",async()=>{
 const data={interval:Number(byId("interval").value),fit:byId("fit").value};
 for(const key of ["shuffle","clock","weather","auto_idle"])data[key]=byId(key).checked;
 try{await api("/api/frame/options",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
 message("Photo Frame settings saved.");}catch(err){message(err.message);}
});
document.querySelectorAll("[data-control]").forEach(button=>{
 button.addEventListener("click",async()=>{
  try{await api("/api/frame/control",{method:"POST",
   headers:{"Content-Type":"application/json"},body:JSON.stringify({action:button.dataset.control})});
   message("Photo Frame: "+button.dataset.control);
  }catch(err){message(err.message);}
 });
});
</script>
</body></html>"""

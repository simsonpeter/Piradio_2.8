"""Optional Home Assistant bridge for PiRadio 7.

- Configuration is local only: ~/.config/piradio7/home_assistant.json (0600).
- Never include access tokens or arbitrary entity state in web endpoints.
- Only allowlisted light/switch entities, never locks, doors or covers.
- No network requests on the Pygame rendering/event thread.
- Home Assistant REST requests use verified TLS (if HTTPS), fixed configured
  URL, short timeouts, and no redirects.
"""
import ipaddress
import json
import re
import stat
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests


DEFAULT_CONFIG = Path.home() / ".config" / "piradio7" / "home_assistant.json"
ENTITY_PATTERN = re.compile(r"^(?:light|switch)\.[a-z0-9_]+$")
POLL_SECONDS = 20


def validate_base_url(url):
    if not isinstance(url, str):
        raise ValueError("Home Assistant URL must be a string")
    parts = urlsplit(url.strip())
    if (parts.scheme not in ("http", "https") or not parts.hostname
            or parts.username or parts.password or parts.path not in ("", "/")
            or parts.query or parts.fragment):
        raise ValueError("Use only the Home Assistant server URL (no path or credentials)")
    try:
        if parts.port is not None and not (1 <= parts.port <= 65535):
            raise ValueError("Invalid Home Assistant port")
    except ValueError as error:
        raise ValueError("Invalid Home Assistant port") from error
    host = parts.hostname.lower()
    if parts.scheme == "http":
        try:
            address = ipaddress.ip_address(host)
            private = address.is_private or address.is_loopback
        except ValueError:
            private = host in ("localhost", "homeassistant") or host.endswith((".local", ".lan"))
        if not private:
            raise ValueError("Use HTTPS outside your private home network")
    return url.strip().rstrip("/")


def validate_entities(entities):
    if not isinstance(entities, list) or not 1 <= len(entities) <= 8:
        raise ValueError("Select between 1 and 8 lights or switches")
    if not all(isinstance(e, str) and ENTITY_PATTERN.fullmatch(e) for e in entities):
        raise ValueError("Only light.* and switch.* entity IDs are supported")
    if len(set(entities)) != len(entities):
        raise ValueError("Duplicate Home Assistant entity")
    return list(entities)


def read_local_config(path=DEFAULT_CONFIG):
    path = Path(path)
    if not path.is_file():
        return None, "Not configured"
    if path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        return None, "Secure config permissions: chmod 600"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Invalid configuration")
        base = validate_base_url(data.get("url"))
        entities = validate_entities(data.get("entities"))
        token = data.get("token")
        if (not isinstance(token, str) or len(token.strip()) < 20
                or token.strip() == "PASTE_TOKEN_LOCALLY"):
            raise ValueError("Add a Home Assistant access token locally")
        return {"url": base, "entities": entities, "token": token.strip()}, ""
    except (OSError, ValueError, TypeError):
        return None, "Check local Home Assistant configuration"


class HomeAssistantBridge:
    """Thread-safe cached state. Only Pygame calls .tick() and .toggle()."""

    def __init__(self, config_path=DEFAULT_CONFIG, session_factory=requests.Session,
                 clock=time.monotonic):
        self._lock = threading.Lock()
        self._clock = clock
        self._session_factory = session_factory
        self._config, self._setup_message = read_local_config(config_path)
        self._online = False
        self._updating = False
        self._next_check = 0
        self._error = self._setup_message or "Connecting to Home Assistant"
        self._items = [
            {"id": entity, "name": entity.split(".", 1)[1].replace("_", " ").title(),
             "state": "unknown", "busy": False}
            for entity in (self._config["entities"] if self._config else [])
        ]

    @property
    def configured(self):
        return self._config is not None

    def snapshot(self):
        with self._lock:
            return {
                "configured": self.configured,
                "online": self._online,
                "updating": self._updating,
                "message": self._error,
                "items": [dict(item) for item in self._items],
            }

    def tick(self, now=None):
        """Nonblocking. Schedule a refresh at most once every 20 seconds."""
        if not self.configured:
            return
        now = self._clock() if now is None else now
        with self._lock:
            if self._updating or now < self._next_check:
                return
            self._updating = True
            self._next_check = now + POLL_SECONDS
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _session(self):
        client = self._session_factory()
        client.trust_env = False
        client.headers.update({
            "Authorization": "Bearer " + self._config["token"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        return client

    def _read_states(self, client):
        result = []
        for entity in self._config["entities"]:
            response = client.get(
                self._config["url"] + "/api/states/" + entity,
                timeout=(2, 4), allow_redirects=False,
            )
            if response.status_code == 401:
                raise PermissionError("Access token rejected")
            if response.status_code != 200:
                raise RuntimeError("Home Assistant device unavailable")
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("entity_id") != entity:
                raise RuntimeError("Unexpected Home Assistant response")
            raw = payload.get("state")
            state = raw if raw in ("on", "off") else "unavailable"
            attributes = payload.get("attributes")
            name = attributes.get("friendly_name") if isinstance(attributes, dict) else None
            if not isinstance(name, str) or not name.strip():
                name = entity.split(".", 1)[1].replace("_", " ").title()
            result.append({"id": entity, "name": name.strip()[:44],
                           "state": state, "busy": False})
        return result

    def _refresh_worker(self):
        client = None
        try:
            client = self._session()
            items = self._read_states(client)
            with self._lock:
                # Keep busy markers while a user-initiated command runs.
                busy_ids = {i["id"] for i in self._items if i["busy"]}
                for item in items:
                    item["busy"] = item["id"] in busy_ids
                self._items = items
                self._online = True
                self._error = ""
        except PermissionError:
            with self._lock:
                self._online = False
                self._error = "Home Assistant access token rejected"
        except (requests.RequestException, ValueError, RuntimeError, OSError):
            with self._lock:
                self._online = False
                self._error = "Home Assistant unavailable"
        finally:
            if client:
                client.close()
            with self._lock:
                self._updating = False

    def toggle(self, index):
        """Only an explicit physical touchscreen tap can call this function."""
        with self._lock:
            if (not self._online or type(index) is not int
                    or not (0 <= index < len(self._items))):
                return False
            item = self._items[index]
            if item["busy"] or item["state"] not in ("on", "off"):
                return False
            item["busy"] = True
            entity_id = item["id"]
            target = "turn_off" if item["state"] == "on" else "turn_on"
        threading.Thread(target=self._toggle_worker, args=(entity_id, target),
                         daemon=True).start()
        return True

    def _toggle_worker(self, entity_id, action):
        client = None
        try:
            domain = entity_id.split(".", 1)[0]
            if domain not in ("light", "switch"):
                raise ValueError("Unsupported device")
            client = self._session()
            response = client.post(
                self._config["url"] + "/api/services/" + domain + "/" + action,
                json={"entity_id": entity_id},
                timeout=(2, 4), allow_redirects=False,
            )
            if response.status_code == 401:
                raise PermissionError("Access token rejected")
            if not 200 <= response.status_code < 300:
                raise RuntimeError("Device command rejected")
            with self._lock:
                # Optimistic confirmation from Home Assistant's successful
                # service response; periodic state polling still reconciles
                # the real device state on the next frame.
                for item in self._items:
                    if item["id"] == entity_id:
                        item["state"] = "off" if action == "turn_off" else "on"
                        break
                self._next_check = 0
                self._error = ""
        except (requests.RequestException, ValueError, RuntimeError, PermissionError, OSError):
            with self._lock:
                self._error = "Device control failed"
        finally:
            if client:
                client.close()
            with self._lock:
                for item in self._items:
                    if item["id"] == entity_id:
                        item["busy"] = False
                        break

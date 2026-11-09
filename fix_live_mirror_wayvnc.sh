#!/usr/bin/env bash
# Make Raspberry Pi OS WayVNC compatible with browser noVNC.
# IMPORTANT: authentication-free RFB is restricted to 127.0.0.1 only;
# remote access remains protected by the user's private Tailscale HTTPS Serve endpoint.
set -euo pipefail

CONFIG="/etc/wayvnc/config"
if [[ ! -f "$CONFIG" ]]; then
  echo "Cannot find $CONFIG; enable VNC using sudo raspi-config first." >&2
  exit 1
fi
if ! systemctl is-active --quiet piradio-mirror-web.service; then
  echo "PiRadio mirror web service is not running; run bash setup_live_mirror.sh first." >&2
  exit 1
fi
if ! command -v tailscale >/dev/null || ! tailscale status >/dev/null 2>&1; then
  echo "Tailscale is not connected; refusing to enable local-only VNC without the remote VPN." >&2
  exit 1
fi

BACKUP="/etc/wayvnc/config.piradio-backup-$(date +%Y%m%d-%H%M%S)"
sudo cp -p "$CONFIG" "$BACKUP"
echo "WayVNC config backed up to $BACKUP"

sudo python3 - "$CONFIG" <<'PY'
import pathlib, re, sys
config = pathlib.Path(sys.argv[1])
content = config.read_text()
for key, value in (("address", "127.0.0.1"), ("enable_auth", "false")):
    pattern = r"(?m)^\s*" + key + r"\s*=.*$"
    line = f"{key}={value}"
    if re.search(pattern, content):
        content = re.sub(pattern, line, content)
    else:
        content = content.rstrip("\n") + "\n" + line + "\n"
config.write_text(content.rstrip("\n") + "\n")
PY

echo "Restarting WayVNC using loopback-only browser-compatible mode..."
sudo systemctl restart wayvnc
sleep 2
if ! systemctl is-active --quiet wayvnc; then
  echo "WayVNC failed to start; restoring original configuration." >&2
  sudo cp -p "$BACKUP" "$CONFIG"
  sudo systemctl restart wayvnc || true
  exit 1
fi
LISTENERS="$(sudo ss -ltnp)"
if ! printf '%s\n' "$LISTENERS" | grep -Eq 'LISTEN.*127\.0\.0\.1:5900[[:space:]]'; then
  echo "Port 5900 is not confirmed on loopback only. Reverting for safety." >&2
  sudo cp -p "$BACKUP" "$CONFIG"
  sudo systemctl restart wayvnc || true
  sudo ss -ltnp | grep 5900 || true
  exit 1
fi
if printf '%s\n' "$LISTENERS" | grep ':5900 ' | grep -Eq '([0-9.]+|\[::\]|\*):5900' && \
   printf '%s\n' "$LISTENERS" | grep ':5900 ' | grep -Ev '127\.0\.0\.1:5900'; then
  echo "Unexpected non-loopback VNC listener. Reverting for safety." >&2
  sudo cp -p "$BACKUP" "$CONFIG"
  sudo systemctl restart wayvnc || true
  exit 1
fi
echo "Success: WayVNC listens on localhost only. NoVNC should now connect."
echo "Your secure remote continues through Tailscale Serve HTTPS on port 8443."
echo "Open the PiRadio app and tap Live Screen Mirror; if necessary tap Reconnect."
echo "Security note: local processes on the Pi can access unencrypted VNC; protect Pi login access."

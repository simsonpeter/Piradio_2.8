#!/usr/bin/env bash
# PiRadio 7-inch live mirror: browser-based interactive VNC inside the private Tailscale network.
set -euo pipefail

if [[ "$EUID" -eq 0 ]]; then
  echo "Run as your normal Pi login: bash setup_live_mirror.sh (not with sudo)" >&2
  exit 1
fi
if ! command -v tailscale >/dev/null 2>&1; then
  echo "Tailscale is not installed. Set up Tailscale on the Pi first." >&2
  exit 1
fi
if ! tailscale status >/dev/null 2>&1; then
  echo "Tailscale is not connected. Run: sudo tailscale up" >&2
  exit 1
fi
echo "Installing noVNC and Websockify..."
sudo apt-get update
sudo apt-get install -y novnc websockify
if [[ ! -f /usr/share/novnc/vnc.html ]]; then
  echo "The noVNC web client was not installed to /usr/share/novnc." >&2
  exit 1
fi
WEBSOCKIFY="$(command -v websockify)"
echo "Configuring loopback-only mirror gateway..."
sudo tee /etc/systemd/system/piradio-mirror-web.service >/dev/null <<EOF
[Unit]
Description=PiRadio noVNC gateway (loopback only, via Tailscale Serve)
After=network.target

[Service]
Type=simple
User=$(id -un)
Group=$(id -gn)
ExecStart=$WEBSOCKIFY --web=/usr/share/novnc 127.0.0.1:6080 127.0.0.1:5900
Restart=on-failure
RestartSec=3
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now piradio-mirror-web.service
if ! curl -fsS --max-time 5 http://127.0.0.1:6080/vnc.html >/dev/null; then
  echo "noVNC gateway did not start correctly. Run: sudo systemctl status piradio-mirror-web.service" >&2
  exit 1
fi
echo "Enabling PRIVATE HTTPS mirror at port 8443 (NOT Tailscale Funnel)..."
sudo tailscale serve --bg --https=8443 http://127.0.0.1:6080
echo
echo "Current Tailscale services:"
sudo tailscale serve status
echo
if ! ss -ltn | grep -q ':5900 '; then
  echo "WARNING: No VNC server found listening on port 5900."
  echo "Enable VNC in sudo raspi-config > Interface Options > VNC > Yes, then reboot."
else
  echo "WayVNC port 5900 is listening."
fi
echo "Open the existing PiRadio HTTPS remote and tap the screen icon to launch Live Mirror."
echo "Ensure your Android Tailscale VPN is connected."

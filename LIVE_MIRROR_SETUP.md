# PiRadio 7-inch live screen mirror

The **Live Mirror** button in the existing PiRadio phone remote shows and controls the actual 800 × 480 Raspberry Pi screen. It uses Raspberry Pi OS WayVNC, noVNC in an iframe, and a **private** Tailscale Serve HTTPS endpoint. This is different from the simulated 7-inch preview. It can mirror mpv fullscreen playback if the Wayland compositor captures the mpv window.

## Prerequisites

- Raspberry Pi OS Trixie graphical desktop (labwc), with the 7-inch PiRadio running.
- Your original PiRadio remote already works through a private Tailscale Serve URL (HTTPS port 443).
- Tailscale is also connected on your Android phone.
- **VNC enabled** via `sudo raspi-config` → Interface Options → VNC → Yes. Reboot if prompted. Raspberry Pi OS typically runs WayVNC on port 5900.
- Never enable Tailscale Funnel or forward ports 5900/6080/8443 on your internet router.

## Install

From `~/tcradio` after updating to this branch:

```bash
sudo raspi-config
# Interface Options > VNC > Yes, then exit
bash setup_live_mirror.sh
```

The script installs Debian `novnc` and `websockify`, creates `piradio-mirror-web.service` (binding **only** to 127.0.0.1:6080), and configures an additional **private** Tailscale HTTPS Serve entry on port 8443. It does **not** modify your existing port 443 → 8080 remote.

Use the same phone PWA URL as before, but refresh the app; tap the **screen icon** in the header, or the **Live Screen Mirror** button on the YouTube page. The interactive mirror is within the remote app. Rotate the phone to landscape and use the fullscreen button for a larger view.

Expected mirror endpoint: `https://<your-pi>.<your-tailnet>.ts.net:8443/vnc.html?autoconnect=1&resize=scale&path=websockify`. Your exact address comes from `tailscale serve status`.

## If noVNC loads but reports Failed to connect

Raspberry Pi OS WayVNC defaults to encrypted/PAM VNC security types which browser noVNC may not support. The compatibility fix is `bash fix_live_mirror_wayvnc.sh`. It backs up `/etc/wayvnc/config`, changes WayVNC to listen **only** on `127.0.0.1:5900` with VNC-layer authentication disabled, restarts the service and verifies that port 5900 is loopback-only. The noVNC browser connection still uses **private Tailscale Serve HTTPS**. Do not forward port 5900 or use Tailscale Funnel. Other local processes on the Pi can access this VNC listener, so keep SSH/local access locked down. To reverse the change, restore the path printed by the fix script into `/etc/wayvnc/config` and restart `wayvnc`.

## Troubleshooting

- **Black / disconnected**: Confirm a graphical session is running, VNC is enabled, and your phone has the Tailscale VPN active. Run `sudo systemctl status piradio-mirror-web.service`, `ss -lnt | grep -E ':(5900|6080) '`, and `tailscale serve status`.
- **Connect button / password**: Use the VNC login configured by your Raspberry Pi, not your Tailscale account. Never put a VNC password into the GitHub code.
- **Site cannot be reached**: Confirm that HTTPS Serve port 8443 is listed in `tailscale serve status`; test opening the full HTTPS mirror endpoint directly in phone Chrome.
- **Old remote still opens**: Reload your original Tailscale HTTPS page (or close/reopen its installed PWA).
- **Video is slow**: VNC screen sharing is not a low-latency media streamer. Use the original Pi video remote and playback timeline for the smoothest video experience.

The mirror feature cannot control a Pi that is powered off or disconnected from the internet.

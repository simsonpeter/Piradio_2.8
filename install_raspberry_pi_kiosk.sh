#!/usr/bin/env bash
set -euo pipefail

INSTALL_LCD=true
if [[ "${TCRADIOS_SKIP_LCD:-0}" == "1" ]]; then
    INSTALL_LCD=false
fi
if [[ ${1:-} == "--skip-lcd" ]]; then
    INSTALL_LCD=false
elif [[ $# -gt 0 ]]; then
    echo "Usage: sudo $0 [--skip-lcd]" >&2
    exit 1
fi

if [[ ${EUID} -ne 0 ]]; then
    echo "Run this installer with sudo: sudo ./install_raspberry_pi_kiosk.sh" >&2
    exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_USER="${SUDO_USER:-}"
LCD_DRIVER_DIR=""
LCD_SHOW_COMMIT="a36c00a55e11f0de3b4be0e66f0a2cec47076e23"

if [[ -z "${INSTALL_USER}" || "${INSTALL_USER}" == "root" ]]; then
    echo "Run this installer with sudo from the desktop user account." >&2
    exit 1
fi

INSTALL_HOME="$(getent passwd "${INSTALL_USER}" | cut -d: -f6)"
if [[ -z "${INSTALL_HOME}" || ! -d "${INSTALL_HOME}" ]]; then
    echo "Could not determine the home directory for ${INSTALL_USER}." >&2
    exit 1
fi
LCD_DRIVER_DIR="${INSTALL_HOME}/LCD-show"

CONFIG_FILE=""
CMDLINE_FILE=""
for candidate in /boot/firmware/config.txt /boot/config.txt; do
    if [[ -f "${candidate}" ]]; then
        CONFIG_FILE="${candidate}"
        break
    fi
done
for candidate in /boot/firmware/cmdline.txt /boot/cmdline.txt; do
    if [[ -f "${candidate}" ]]; then
        CMDLINE_FILE="${candidate}"
        break
    fi
done

if [[ -z "${CONFIG_FILE}" || -z "${CMDLINE_FILE}" ]]; then
    echo "Raspberry Pi boot configuration was not found." >&2
    exit 1
fi

cp -an "${CONFIG_FILE}" "${CONFIG_FILE}.tcradios-backup"
cp -an "${CMDLINE_FILE}" "${CMDLINE_FILE}.tcradios-backup"

echo "Installing all TCRADIOS application, audio, and boot dependencies..."
apt-get update
AUDIO_PACKAGES=(pulseaudio-module-bluetooth)
if dpkg-query -W -f='${Status}' pipewire 2>/dev/null | grep -q "install ok installed"; then
    AUDIO_PACKAGES=(
        pipewire-audio
        pipewire-pulse
        libpipewire-0.3-modules
        libspa-0.2-bluetooth
        wireplumber
    )
fi
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    git \
    vlc \
    python3-vlc \
    python3-pygame \
    python3-gpiozero \
    python3-flask \
    python3-requests \
    python3-pil \
    python3-qrcode \
    alsa-utils \
    pulseaudio-utils \
    espeak \
    fonts-noto-core \
    fonts-noto-extra \
    fonts-lohit-taml \
    libraqm0 \
    ffmpeg \
    nodejs \
    curl \
    yt-dlp \
    util-linux \
    x11-xserver-utils \
    unclutter \
    plymouth \
    plymouth-themes \
    bluez \
    network-manager \
    "${AUDIO_PACKAGES[@]}"

echo "Verifying Python dependencies..."
/usr/bin/python3 - <<'PY'
import pygame
import qrcode
import requests
import vlc
from flask import Flask
from PIL import Image, ImageDraw, ImageFont

print("All TCRADIOS Python dependencies are available.")
PY

echo "Installing the bundled Tamil font for song names..."
install -d /usr/local/share/fonts/tcradios
if [[ -d "${SCRIPT_DIR}/fonts" ]]; then
    install -m 0644 "${SCRIPT_DIR}"/fonts/*.ttf /usr/local/share/fonts/tcradios/ || true
fi
fc-cache -f /usr/local/share/fonts/tcradios >/dev/null 2>&1 || true

echo "Installing a current yt-dlp for YouTube search and playback..."
YTDLP_TMP="$(mktemp)"
if curl -fsSL "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp" -o "${YTDLP_TMP}"; then
    install -m 0755 "${YTDLP_TMP}" /usr/local/bin/yt-dlp
    echo "yt-dlp $(/usr/local/bin/yt-dlp --version) installed."
else
    echo "Warning: current yt-dlp could not be downloaded. The apt package will be used." >&2
fi
rm -f "${YTDLP_TMP}"

THEME_DIR="/usr/share/plymouth/themes/tcradios"
install -d "${THEME_DIR}"
install -m 0644 "${SCRIPT_DIR}/boot/tcradios.plymouth" "${THEME_DIR}/tcradios.plymouth"
install -m 0644 "${SCRIPT_DIR}/boot/tcradios.script" "${THEME_DIR}/tcradios.script"

cp -an "${CONFIG_FILE}" "${CONFIG_FILE}.tcradios-backup"
cp -an "${CMDLINE_FILE}" "${CMDLINE_FILE}.tcradios-backup"

if ! grep -qF "# TCRADIOS quiet boot" "${CONFIG_FILE}"; then
    printf '\n[all]\n# TCRADIOS quiet boot\ndisable_splash=1\n' >> "${CONFIG_FILE}"
fi

python3 - "${CMDLINE_FILE}" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
tokens = path.read_text().strip().split()
remove = {"nosplash", "plymouth.enable=0"}
tokens = [token for token in tokens if token not in remove]
required = [
    "quiet",
    "splash",
    "logo.nologo",
    "loglevel=3",
    "systemd.show_status=false",
    "vt.global_cursor_default=0",
    "plymouth.ignore-serial-consoles",
]
for token in required:
    if token not in tokens:
        tokens.append(token)
path.write_text(" ".join(tokens) + "\n")
PY

plymouth-set-default-theme tcradios
if command -v update-initramfs >/dev/null 2>&1; then
    update-initramfs -u
fi

echo "Installing automatic TCRADIOS launch..."
cat > /usr/local/bin/tcradios-start <<EOF
#!/usr/bin/env bash
set -e
# Both XDG and compositor launchers must contend for the same lock.
exec 9>"/tmp/tcradios-\${UID}.lock"
flock -n 9 || exit 0

if [[ ! -t 1 ]]; then
    exec >>"\${HOME}/.tcradios-start.log" 2>&1
fi

export DISPLAY="\${DISPLAY:-:0}"
export XDG_CURRENT_DESKTOP="\${XDG_CURRENT_DESKTOP:-labwc}"
DISPLAY_NUMBER="\${DISPLAY#:}"
for _ in {1..20}; do
    if [[ -S "/tmp/.X11-unix/X\${DISPLAY_NUMBER}" ]] || [[ -n "\${WAYLAND_DISPLAY:-}" ]]; then
        break
    fi
    sleep 0.25
done
# Do not reveal the desktop: keep Plymouth up until the radio window is drawn.
if command -v xset >/dev/null 2>&1; then
    xset s off >/dev/null 2>&1 || true
    xset -dpms >/dev/null 2>&1 || true
    xset s noblank >/dev/null 2>&1 || true
fi
if command -v xsetroot >/dev/null 2>&1; then
    xsetroot -cursor_name none >/dev/null 2>&1 || true
fi
if command -v unclutter >/dev/null 2>&1; then
    unclutter -idle 0 -root >/dev/null 2>&1 &
fi
cd $(printf '%q' "${SCRIPT_DIR}")
exec /usr/bin/python3 $(printf '%q' "${SCRIPT_DIR}/touch_radio.py")
EOF
chmod 0755 /usr/local/bin/tcradios-start

AUTOSTART_DIR="${INSTALL_HOME}/.config/autostart"
install -d -o "${INSTALL_USER}" -g "${INSTALL_USER}" "${AUTOSTART_DIR}"
# Remove the legacy direct launcher, which bypasses the shared process lock.
rm -f "${AUTOSTART_DIR}/tcradio.desktop"
install -m 0644 -o "${INSTALL_USER}" -g "${INSTALL_USER}" \
    "${SCRIPT_DIR}/boot/tcradios-autostart.desktop" \
    "${AUTOSTART_DIR}/tcradios.desktop"

LABWC_DIR="${INSTALL_HOME}/.config/labwc"
LABWC_AUTOSTART="${LABWC_DIR}/autostart"
install -d -o "${INSTALL_USER}" -g "${INSTALL_USER}" "${LABWC_DIR}"
cat > "${LABWC_AUTOSTART}" <<'EOF'
#!/bin/sh
# TCRADIOS kiosk: radio only. No panel, desktop, or notification popups.
/usr/local/bin/tcradios-start &
EOF
chown "${INSTALL_USER}:${INSTALL_USER}" "${LABWC_AUTOSTART}"
chmod 0755 "${LABWC_AUTOSTART}"
for sys_autostart in /etc/xdg/labwc/autostart /usr/share/labwc/autostart; do
    if [[ -f "${sys_autostart}" ]]; then
        cp -an "${sys_autostart}" "${sys_autostart}.tcradios-backup"
        cat > "${sys_autostart}" <<'EOF'
#!/bin/sh
/usr/local/bin/tcradios-start &
EOF
        chmod 0755 "${sys_autostart}"
    fi
done

# Hide the Raspberry Pi desktop chrome so boot is splash then radio.
hide_xdg_autostart() {
    local name="$1"
    printf '%s\n' "[Desktop Entry]" "Hidden=true" \
        > "${AUTOSTART_DIR}/${name}.desktop"
    chown "${INSTALL_USER}:${INSTALL_USER}" "${AUTOSTART_DIR}/${name}.desktop"
}

keep_autostart='pulseaudio|pipewire|wireplumber|gnome-keyring|polkit|at-spi|xdg-permission|xdg-desktop-portal'
if [[ -d /etc/xdg/autostart ]]; then
    while IFS= read -r desktop_file; do
        base="$(basename "${desktop_file}" .desktop)"
        if echo "${base}" | grep -Eiq "${keep_autostart}"; then
            continue
        fi
        hide_xdg_autostart "${base}"
    done < <(find /etc/xdg/autostart -maxdepth 1 -name '*.desktop' | sort)
fi
for extra in \
    wf-panel-pi \
    lxpanel \
    lxpanel-pi \
    pcmanfm \
    pcmanfm-desktop \
    pcmanfm-pi \
    nm-applet \
    nm-tray \
    notification-daemon \
    xfce4-notifyd \
    mako \
    dunst \
    fnott \
    lxqt-notificationd \
    update-notifier \
    gnome-software-service \
    piwiz \
    pprompt \
    print-applet \
    light-locker \
    xscreensaver \
    pi-packages \
    rp-prefapps \
    geoclue-demo-agent \
    user-dirs-update-gtk \
    xdg-user-dirs
do
    hide_xdg_autostart "${extra}"
done

LXSESSION_DIR="${INSTALL_HOME}/.config/lxsession/LXDE-pi"
if [[ -d /etc/xdg/lxsession/LXDE-pi || -d "${LXSESSION_DIR}" ]]; then
    install -d -o "${INSTALL_USER}" -g "${INSTALL_USER}" "${LXSESSION_DIR}"
    cat > "${LXSESSION_DIR}/autostart" <<'EOF'
@/usr/local/bin/tcradios-start
EOF
    chown "${INSTALL_USER}:${INSTALL_USER}" "${LXSESSION_DIR}/autostart"
fi

WAYFIRE_INI="${INSTALL_HOME}/.config/wayfire.ini"
if [[ -f "${WAYFIRE_INI}" ]]; then
    python3 - "${WAYFIRE_INI}" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
lines = []
skip_keys = {"panel", "background", "autostart_wf_shell", "xdg_autostart"}
in_autostart = False
for line in text.splitlines():
    stripped = line.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        in_autostart = stripped.lower() == "[autostart]"
        lines.append(line)
        continue
    if in_autostart:
        key = stripped.split("=", 1)[0].strip().lower()
        if key in skip_keys or key.endswith("panel") or "wf-panel" in stripped or "pcmanfm" in stripped:
            continue
        if "tcradios-start" in stripped:
            continue
    lines.append(line)
if "[autostart]" not in text.lower():
    lines.append("[autostart]")
lines.append("autostart_wf_shell = false")
lines.append("tcradios = /usr/local/bin/tcradios-start")
path.write_text("\n".join(lines) + "\n")
PY
    chown "${INSTALL_USER}:${INSTALL_USER}" "${WAYFIRE_INI}"
fi

install -d /etc/NetworkManager/conf.d
cat > /etc/NetworkManager/conf.d/tcradios-kiosk.conf <<'EOF'
[connectivity]
uri=
interval=0
EOF
if command -v nmcli >/dev/null 2>&1; then
    nmcli general reload >/dev/null 2>&1 || true
fi

# Disable the legacy service used by older PiRadio installations. It starts a
# second process outside the launcher's shared lock.
if systemctl list-unit-files tcradio.service --no-legend 2>/dev/null | grep -q '^tcradio.service'; then
    systemctl disable --now tcradio.service || true
fi

if command -v raspi-config >/dev/null 2>&1; then
    echo "Enabling desktop auto-login..."
    raspi-config nonint do_boot_behaviour B4 || \
        echo "Warning: desktop auto-login could not be enabled automatically." >&2
fi

systemctl set-default graphical.target
# The long Plymouth wait keeps the splash on screen. Shutdown Plymouth
# services also deadlock the LCD35 display, so reboot never finishes.
systemctl mask plymouth-quit-wait.service
systemctl mask plymouth-reboot.service
systemctl mask plymouth-poweroff.service
systemctl mask plymouth-halt.service
systemctl disable NetworkManager-wait-online.service || true

install -d /etc/systemd/system.conf.d
cat > /etc/systemd/system.conf.d/tcradios-reboot.conf <<EOF
[Manager]
DefaultTimeoutStopSec=15s
DefaultTimeoutAbortSec=15s
EOF

install -d /etc/systemd/logind.conf.d
cat > /etc/systemd/logind.conf.d/tcradios.conf <<EOF
[Login]
KillUserProcesses=yes
UserStopDelaySec=5
EOF

if [[ -d /etc/lightdm ]]; then
    install -d /etc/lightdm/lightdm.conf.d
    cat > /etc/lightdm/lightdm.conf.d/90-tcradios-nocursor.conf <<'EOF'
[Seat:*]
xserver-command=X -nocursor
EOF
fi

# Keep Plymouth covering the desktop until the radio window is on screen.
systemctl disable --now tcradios-release-display.service >/dev/null 2>&1 || true
rm -f /etc/systemd/system/tcradios-release-display.service
systemctl daemon-reload || true

usermod -aG netdev,plugdev "${INSTALL_USER}" || true

cat > /etc/sudoers.d/tcradios-power <<EOF
${INSTALL_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl poweroff, /usr/bin/systemctl reboot, /usr/bin/nmcli
EOF
chmod 0440 /etc/sudoers.d/tcradios-power
visudo -cf /etc/sudoers.d/tcradios-power

echo
echo "TCRADIOS branded boot is installed."
echo "Backups:"
echo "  ${CONFIG_FILE}.tcradios-backup"
echo "  ${CMDLINE_FILE}.tcradios-backup"

LCD_SHOW_DIR="/opt/tcradios-LCD-show"
if [[ "${INSTALL_LCD}" != true ]]; then
    echo "LCD driver installation skipped."
    echo "Reboot to activate TCRADIOS: sudo reboot"
elif [[ -f "${LCD_DRIVER_DIR}/.have_installed" || -f "${LCD_SHOW_DIR}/.have_installed" ]]; then
    echo "GoodTFT LCD35 driver is already installed."
    echo "Reboot to activate TCRADIOS: sudo reboot"
else
    echo
    echo "Installing the GoodTFT LCD35 driver with 270-degree rotation..."
    if [[ -e "${LCD_SHOW_DIR}" && ! -d "${LCD_SHOW_DIR}/.git" ]]; then
        echo "${LCD_SHOW_DIR} exists but is not a Git checkout." >&2
        echo "Move or remove it, then run this installer again." >&2
        exit 1
    fi
    if [[ ! -d "${LCD_SHOW_DIR}/.git" ]]; then
        git clone https://github.com/goodtft/LCD-show.git "${LCD_SHOW_DIR}"
    fi
    git -C "${LCD_SHOW_DIR}" fetch origin "${LCD_SHOW_COMMIT}"
    git -C "${LCD_SHOW_DIR}" -c advice.detachedHead=false \
        checkout --detach "${LCD_SHOW_COMMIT}"
    chmod -R 0755 "${LCD_SHOW_DIR}"

    # The vendor scripts reboot twice and switch the Pi to console auto-login.
    # Defer those reboots so this installer can restore graphical auto-login
    # and finish the TCRADIOS boot configuration first.
    python3 - \
        "${LCD_SHOW_DIR}/LCD35-show" \
        "${LCD_SHOW_DIR}/rotate.sh" <<'PY'
import pathlib
import sys

marker = ": # reboot deferred to the TCRADIOS installer"
for filename in sys.argv[1:]:
    path = pathlib.Path(filename)
    content = path.read_text()
    if marker not in content:
        path.write_text(content.replace("sudo reboot", marker))
    if "sudo reboot" in path.read_text():
        raise SystemExit(f"Could not defer reboot in {filename}")
PY

    (
        cd "${LCD_SHOW_DIR}"
        ./LCD35-show 270
    )
    echo "GoodTFT LCD35 installed at 270 degrees."
    echo "Rebooting to activate the display and TCRADIOS..."
    sync
    reboot
    exit 0
fi

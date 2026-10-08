#!/usr/bin/env bash
set -euo pipefail

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
install -m 0755 "${SCRIPT_DIR}/boot/tcradios-session" /usr/local/bin/tcradios-session
install -d /usr/share/wayland-sessions /usr/share/xsessions
install -m 0644 "${SCRIPT_DIR}/boot/tcradios-session.desktop" \
    /usr/share/wayland-sessions/tcradios.desktop
install -m 0644 "${SCRIPT_DIR}/boot/tcradios-session.desktop" \
    /usr/share/xsessions/tcradios.desktop

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
export XDG_CURRENT_DESKTOP="\${XDG_CURRENT_DESKTOP:-TCRADIOS}"
DISPLAY_NUMBER="\${DISPLAY#:}"
for _ in {1..20}; do
    if [[ -S "/tmp/.X11-unix/X\${DISPLAY_NUMBER}" ]] || [[ -n "\${WAYLAND_DISPLAY:-}" ]]; then
        break
    fi
    sleep 0.25
done
# Strip Raspberry Pi desktop chrome so Wi-Fi/update toasts cannot appear.
for pattern in \
    wf-panel-pi \
    lxpanel \
    'pcmanfm --desktop' \
    nm-applet \
    nm-tray \
    update-notifier \
    gnome-software \
    piwiz \
    mako \
    dunst \
    notification-daemon \
    xfce4-notifyd \
    lxqt-notificationd
do
    pkill -f "\${pattern}" >/dev/null 2>&1 || true
done
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

write_kiosk_autostart() {
    local path="$1"
    local dir
    dir="$(dirname "${path}")"
    install -d "${dir}"
    if [[ -f "${path}" && ! -f "${path}.tcradios-backup" ]]; then
        cp -an "${path}" "${path}.tcradios-backup"
    fi
    cat > "${path}" <<'EOF'
#!/bin/sh
/usr/local/bin/tcradios-start &
EOF
    chmod 0755 "${path}"
}

LABWC_DIR="${INSTALL_HOME}/.config/labwc"
write_kiosk_autostart "${LABWC_DIR}/autostart"
chown -R "${INSTALL_USER}:${INSTALL_USER}" "${LABWC_DIR}"
while IFS= read -r autostart_path; do
    write_kiosk_autostart "${autostart_path}"
done < <(
    find /etc /usr/share /usr/lib -type f \( -path '*labwc*/autostart' -o -path '*labwc-pi*/autostart' \) 2>/dev/null || true
)

# lxsession runs the system file AND the user file, so replace both.
install -d /etc/xdg/lxsession/LXDE-pi
install -d "${INSTALL_HOME}/.config/lxsession/LXDE-pi"
for lx_autostart in \
    /etc/xdg/lxsession/LXDE-pi/autostart \
    "${INSTALL_HOME}/.config/lxsession/LXDE-pi/autostart"
do
    if [[ -f "${lx_autostart}" && ! -f "${lx_autostart}.tcradios-backup" ]]; then
        cp -an "${lx_autostart}" "${lx_autostart}.tcradios-backup"
    fi
    printf '@/usr/local/bin/tcradios-start\n' > "${lx_autostart}"
done
chown -R "${INSTALL_USER}:${INSTALL_USER}" "${INSTALL_HOME}/.config/lxsession"

# Hide the Raspberry Pi desktop chrome so boot is splash then radio.
hide_xdg_autostart() {
    local name="$1"
    printf '%s\n' "[Desktop Entry]" "Hidden=true" \
        > "${AUTOSTART_DIR}/${name}.desktop"
    chown "${INSTALL_USER}:${INSTALL_USER}" "${AUTOSTART_DIR}/${name}.desktop"
}

keep_autostart='pulseaudio|pipewire|wireplumber|gnome-keyring|polkit|at-spi|xdg-permission|xdg-desktop-portal'
hide_system_xdg_autostart() {
    local desktop_file="$1"
    local base
    base="$(basename "${desktop_file}" .desktop)"
    if echo "${base}" | grep -Eiq "${keep_autostart}"; then
        return 0
    fi
    if [[ -f "${desktop_file}" && ! -f "${desktop_file}.tcradios-backup" ]]; then
        cp -an "${desktop_file}" "${desktop_file}.tcradios-backup"
    fi
    printf '%s\n' "[Desktop Entry]" "Hidden=true" > "${desktop_file}"
}

if [[ -d /etc/xdg/autostart ]]; then
    while IFS= read -r desktop_file; do
        hide_system_xdg_autostart "${desktop_file}"
        hide_xdg_autostart "$(basename "${desktop_file}" .desktop)"
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
    echo "Enabling graphical auto-login..."
    raspi-config nonint do_boot_behaviour B4 || \
        echo "Warning: graphical auto-login could not be enabled automatically." >&2
fi

printf '%s\n' "[Desktop]" "Session=tcradios" > "${INSTALL_HOME}/.dmrc"
chown "${INSTALL_USER}:${INSTALL_USER}" "${INSTALL_HOME}/.dmrc"
if [[ -d /var/lib/AccountsService/users ]]; then
    cat > "/var/lib/AccountsService/users/${INSTALL_USER}" <<EOF
[User]
Language=
XSession=tcradios
Session=tcradios
SystemAccount=false
EOF
fi
if [[ -d /etc/lightdm ]]; then
    install -d /etc/lightdm/lightdm.conf.d
    cat > /etc/lightdm/lightdm.conf.d/91-tcradios-session.conf <<EOF
[Seat:*]
user-session=tcradios
autologin-session=tcradios
autologin-user=${INSTALL_USER}
xserver-command=X -nocursor
EOF
fi
if [[ -f /etc/greetd/config.toml ]]; then
    python3 - "${INSTALL_USER}" <<'PY'
from pathlib import Path
import sys
user = sys.argv[1]
path = Path("/etc/greetd/config.toml")
text = path.read_text()
block = (
    "\n[initial_session]\n"
    f'command = "/usr/local/bin/tcradios-session"\n'
    f'user = "{user}"\n'
)
if "[initial_session]" in text:
    lines = []
    skip = False
    for line in text.splitlines():
        if line.strip() == "[initial_session]":
            skip = True
            continue
        if skip and line.startswith("["):
            skip = False
        if skip:
            continue
        lines.append(line)
    text = "\n".join(lines)
path.write_text(text.rstrip() + "\n" + block)
PY
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

if [[ "${TCRADIOS_SKIP_LCD:-0}" == "1" ]]; then
    echo "LCD driver installation skipped (TCRADIOS_SKIP_LCD=1)."
    echo "Reboot to activate TCRADIOS: sudo reboot"
elif [[ -f "${LCD_DRIVER_DIR}/.have_installed" ]]; then
    echo "GoodTFT LCD35 driver is already installed."
    echo "Reboot to activate TCRADIOS: sudo reboot"
else
    echo
    echo "Installing the reviewed GoodTFT LCD35 driver with 270-degree rotation."
    echo "The display installer will reboot the Raspberry Pi automatically."
    rm -rf "${LCD_DRIVER_DIR}"
    install -d -o "${INSTALL_USER}" -g "${INSTALL_USER}" "${LCD_DRIVER_DIR}"
    git -C "${LCD_DRIVER_DIR}" init
    git -C "${LCD_DRIVER_DIR}" remote add origin https://github.com/goodtft/LCD-show.git
    git -C "${LCD_DRIVER_DIR}" fetch --depth 1 origin "${LCD_SHOW_COMMIT}"
    git -C "${LCD_DRIVER_DIR}" checkout --detach FETCH_HEAD
    chown -R "${INSTALL_USER}:${INSTALL_USER}" "${LCD_DRIVER_DIR}"
    chmod -R 0755 "${LCD_DRIVER_DIR}"
    sync
    cd "${LCD_DRIVER_DIR}"
    exec ./LCD35-show 270
fi

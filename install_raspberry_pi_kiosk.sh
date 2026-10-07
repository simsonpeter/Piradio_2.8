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
    ffmpeg \
    nodejs \
    curl \
    yt-dlp \
    util-linux \
    x11-xserver-utils \
    plymouth \
    plymouth-themes \
    bluez \
    "${AUDIO_PACKAGES[@]}"

echo "Verifying Python dependencies..."
/usr/bin/python3 - <<'PY'
import pygame
import qrcode
import requests
import vlc
from flask import Flask
from PIL import Image, ImageDraw

print("All TCRADIOS Python dependencies are available.")
PY

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
# Drop the boot splash as soon as the desktop is ready to draw.
plymouth quit >/dev/null 2>&1 || true
DISPLAY_NUMBER="\${DISPLAY#:}"
for _ in {1..30}; do
    [[ -S "/tmp/.X11-unix/X\${DISPLAY_NUMBER}" ]] && break
    sleep 1
done

# Give the desktop session time to finish establishing display authorization.
sleep 3
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

if [[ -d /etc/xdg/labwc ]]; then
    # Register with Labwc as well. Some Raspberry Pi OS images include Labwc
    # while the selected desktop still uses XDG autostart. The launcher lock
    # safely prevents both mechanisms from creating duplicate radio processes.
    install -d -o "${INSTALL_USER}" -g "${INSTALL_USER}" "${LABWC_DIR}"
    touch "${LABWC_AUTOSTART}"
    sed -i '\|/usr/local/bin/tcradios-start|d' "${LABWC_AUTOSTART}"
    sed -i '\|touch_radio.py|d' "${LABWC_AUTOSTART}"
    printf '\n/usr/local/bin/tcradios-start &\n' >> "${LABWC_AUTOSTART}"
    chown "${INSTALL_USER}:${INSTALL_USER}" "${LABWC_AUTOSTART}"
    chmod 0755 "${LABWC_AUTOSTART}"
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

cat > /etc/systemd/system/tcradios-release-display.service <<EOF
[Unit]
Description=Release the TCRADIOS boot splash
DefaultDependencies=no
After=plymouth-start.service
Before=graphical.target display-manager.service
Conflicts=shutdown.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c '/usr/bin/plymouth quit || true'
TimeoutStartSec=5

[Install]
WantedBy=graphical.target
EOF
systemctl enable tcradios-release-display.service

cat > /etc/sudoers.d/tcradios-power <<EOF
${INSTALL_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl poweroff, /usr/bin/systemctl reboot
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

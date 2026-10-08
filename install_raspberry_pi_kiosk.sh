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
# Undo the radio-only kiosk session that left LightDM stuck on the splash.
rm -f /usr/local/bin/tcradios-session
rm -f /usr/share/wayland-sessions/tcradios.desktop
rm -f /usr/share/xsessions/tcradios.desktop
rm -f /etc/lightdm/lightdm.conf.d/91-tcradios-session.conf
rm -f "${INSTALL_HOME}/.dmrc"
if [[ -f "/var/lib/AccountsService/users/${INSTALL_USER}" ]]; then
    sed -i '/^XSession=tcradios/d;/^Session=tcradios/d' \
        "/var/lib/AccountsService/users/${INSTALL_USER}" || true
fi
for sys_autostart in \
    /etc/xdg/labwc/autostart \
    /usr/share/labwc/autostart \
    /etc/xdg/labwc-pi/autostart
do
    if [[ -f "${sys_autostart}.tcradios-backup" ]]; then
        mv -f "${sys_autostart}.tcradios-backup" "${sys_autostart}"
    fi
done

# Point /usr/local/bin at the repo launcher so git updates take effect.
cat > /usr/local/bin/tcradios-start <<EOF
#!/usr/bin/env bash
exec $(printf '%q' "${SCRIPT_DIR}/boot/tcradios-start") "\$@"
EOF
chmod 0755 /usr/local/bin/tcradios-start

AUTOSTART_DIR="${INSTALL_HOME}/.config/autostart"
install -d -o "${INSTALL_USER}" -g "${INSTALL_USER}" "${AUTOSTART_DIR}"
# Remove the legacy direct launcher, which bypasses the shared process lock.
rm -f "${AUTOSTART_DIR}/tcradio.desktop"
install -m 0644 -o "${INSTALL_USER}" -g "${INSTALL_USER}" \
    "${SCRIPT_DIR}/boot/tcradios-autostart.desktop" \
    "${AUTOSTART_DIR}/tcradios.desktop"

# Remove Hidden=true stubs from the kiosk attempt so the desktop panel returns.
if [[ -d "${AUTOSTART_DIR}" ]]; then
    while IFS= read -r desktop_file; do
        [[ "$(basename "${desktop_file}")" == "tcradios.desktop" ]] && continue
        if python3 - "${desktop_file}" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(errors="replace")
lines = [line.strip() for line in text.splitlines() if line.strip()]
raise SystemExit(0 if lines == ["[Desktop Entry]", "Hidden=true"] else 1)
PY
        then
            rm -f "${desktop_file}"
        fi
    done < <(find "${AUTOSTART_DIR}" -maxdepth 1 -name '*.desktop' | sort)
fi

LABWC_DIR="${INSTALL_HOME}/.config/labwc"
LABWC_AUTOSTART="${LABWC_DIR}/autostart"
install -d -o "${INSTALL_USER}" -g "${INSTALL_USER}" "${LABWC_DIR}"
cat > "${LABWC_AUTOSTART}" <<'EOF'
#!/bin/sh
if [ -x /etc/xdg/labwc/autostart ]; then
    /etc/xdg/labwc/autostart &
elif [ -x /usr/share/labwc/autostart ]; then
    /usr/share/labwc/autostart &
fi
/usr/local/bin/tcradios-start &
EOF
chown "${INSTALL_USER}:${INSTALL_USER}" "${LABWC_AUTOSTART}"
chmod 0755 "${LABWC_AUTOSTART}"

LXSESSION_DIR="${INSTALL_HOME}/.config/lxsession/LXDE-pi"
install -d -o "${INSTALL_USER}" -g "${INSTALL_USER}" "${LXSESSION_DIR}"
SYS_LX_AUTOSTART="/etc/xdg/lxsession/LXDE-pi/autostart"
if [[ -f "${SYS_LX_AUTOSTART}" ]]; then
    grep -v 'tcradios-start' "${SYS_LX_AUTOSTART}" > "${LXSESSION_DIR}/autostart" || true
fi
touch "${LXSESSION_DIR}/autostart"
if ! grep -q 'tcradios-start' "${LXSESSION_DIR}/autostart"; then
    printf '%s\n' '@/usr/local/bin/tcradios-start' >> "${LXSESSION_DIR}/autostart"
fi
chown "${INSTALL_USER}:${INSTALL_USER}" "${LXSESSION_DIR}/autostart"

WAYFIRE_INI="${INSTALL_HOME}/.config/wayfire.ini"
if [[ -f "${WAYFIRE_INI}" ]]; then
    python3 - "${WAYFIRE_INI}" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
lines = []
in_autostart = False
seen_tcradios = False
for line in text.splitlines():
    stripped = line.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        in_autostart = stripped.lower() == "[autostart]"
        lines.append(line)
        continue
    if in_autostart and "tcradios-start" in stripped:
        seen_tcradios = True
    lines.append(line)
if "[autostart]" not in text.lower():
    lines.append("[autostart]")
if not seen_tcradios:
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
    echo "Enabling X11 desktop auto-login..."
    raspi-config nonint do_wayland W1 || \
        echo "Warning: X11 could not be selected automatically." >&2
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

cat > /etc/systemd/system/tcradios-release-display.service <<'EOF'
[Unit]
Description=Release the TCRADIOS boot splash
DefaultDependencies=no
After=plymouth-start.service
Before=graphical.target display-manager.service
Conflicts=shutdown.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'timeout 2 /usr/bin/plymouth quit || true'
TimeoutStartSec=5

[Install]
WantedBy=graphical.target
EOF
systemctl daemon-reload || true
systemctl enable tcradios-release-display.service

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

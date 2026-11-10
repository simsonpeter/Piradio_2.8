#!/usr/bin/env bash
# Install a reusable desktop/app-menu launcher for the PiRadio 7 Python app.
# This does not alter labwc/Wayfire, auto-login, the screen driver, or autostart.
set -euo pipefail

if [[ ${EUID} -eq 0 ]]; then
    echo 'Run this installer WITHOUT sudo, as your normal Pi desktop user.' >&2
    exit 1
fi

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -f "${REPO_DIR}/touch_radio.py" ||
      ! -f "${REPO_DIR}/boot/tcradios-start" ||
      ! -f "${REPO_DIR}/boot/piradio-open" ]]; then
    echo 'Missing PiRadio Python app or its launch scripts.' >&2
    exit 1
fi

BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
mkdir -p "${BIN_DIR}" "${APP_DIR}"

# Put a stable command on the user's PATH, even if the checkout changes.
# %q preserves spaces and special characters in repository paths.
printf '#!/usr/bin/env bash\nexec %q %q "$@"\n' \
    '/usr/bin/bash' "${REPO_DIR}/boot/piradio-open" \
    > "${BIN_DIR}/piradio7"
chmod 0755 "${BIN_DIR}/piradio7"

# Freedesktop launcher: visible in the desktop application menu and runnable
# from the desktop icon where desktop shortcuts are enabled.
cat > "${APP_DIR}/piradio7.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=PiRadio 7
GenericName=Smart Radio and Multimedia Player
Comment=Open PiRadio Radio, Tamil Bible, YouTube, Cast and Photo Frame
Exec="${BIN_DIR}/piradio7"
Icon=multimedia-player
Terminal=false
StartupNotify=false
Categories=AudioVideo;Audio;Player;
Keywords=radio;bible;youtube;photo;music;cast;
EOF
chmod 0644 "${APP_DIR}/piradio7.desktop"

# Do not create or alter a kiosk desktop configuration. Desktop icons may be
# hidden by an existing kiosk installation; terminal/menu launcher still works.
DESKTOP_DIR="${HOME}/Desktop"
if command -v xdg-user-dir >/dev/null 2>&1; then
    reported="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
    if [[ -n "${reported}" ]]; then DESKTOP_DIR="${reported}"; fi
fi
if [[ -d "${DESKTOP_DIR}" ]]; then
    cp "${APP_DIR}/piradio7.desktop" "${DESKTOP_DIR}/PiRadio7.desktop"
    chmod 0755 "${DESKTOP_DIR}/PiRadio7.desktop"
    if command -v gio >/dev/null 2>&1; then
        gio set "${DESKTOP_DIR}/PiRadio7.desktop" metadata::trusted true 2>/dev/null || true
    fi
    echo "Desktop shortcut: ${DESKTOP_DIR}/PiRadio7.desktop"
else
    echo 'Desktop folder is hidden/unavailable in kiosk mode. App menu and terminal command were installed.'
fi

printf '\nPiRadio 7 launchers installed.\n'
printf 'App menu: PiRadio 7\n'
printf 'Start without reboot: %s\n' "${BIN_DIR}/piradio7"
printf 'Check status:         %s status\n' "${BIN_DIR}/piradio7"
printf 'Logs:                 %s/.tcradios-start.log\n' "${HOME}"

#!/usr/bin/env bash
# Apply a radio update without reinstalling the LCD driver.
# Run on the Pi: sudo ./boot/update-radio.sh
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "Run with sudo: sudo ./boot/update-radio.sh" >&2
    exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
INSTALL_USER="${SUDO_USER:-}"
if [[ -z "${INSTALL_USER}" || "${INSTALL_USER}" == "root" ]]; then
    echo "Run this from the desktop user account with sudo." >&2
    exit 1
fi
INSTALL_HOME="$(getent passwd "${INSTALL_USER}" | cut -d: -f6)"

echo "Stopping a stuck radio and dismissing the splash..."
timeout 2 plymouth quit >/dev/null 2>&1 || true
pkill -f touch_radio.py >/dev/null 2>&1 || true
sleep 0.4
rm -f /tmp/tcradios-*.lock

echo "Removing leftover kiosk session files..."
rm -f /usr/local/bin/tcradios-session
rm -f /usr/share/wayland-sessions/tcradios.desktop
rm -f /usr/share/xsessions/tcradios.desktop
rm -f /etc/lightdm/lightdm.conf.d/91-tcradios-session.conf
rm -f "${INSTALL_HOME}/.dmrc"
if [[ -f "/var/lib/AccountsService/users/${INSTALL_USER}" ]]; then
    sed -i '/^XSession=tcradios/d;/^Session=tcradios/d' \
        "/var/lib/AccountsService/users/${INSTALL_USER}" || true
fi

echo "Installing launcher and boot splash..."
install -m 0755 "${SCRIPT_DIR}/tcradios-start" /usr/local/bin/tcradios-start
THEME_DIR="/usr/share/plymouth/themes/tcradios"
if [[ -d "${THEME_DIR}" ]]; then
    install -m 0644 "${SCRIPT_DIR}/tcradios.plymouth" "${THEME_DIR}/tcradios.plymouth"
    install -m 0644 "${SCRIPT_DIR}/tcradios.script" "${THEME_DIR}/tcradios.script"
fi

AUTOSTART_DIR="${INSTALL_HOME}/.config/autostart"
install -d -o "${INSTALL_USER}" -g "${INSTALL_USER}" "${AUTOSTART_DIR}"
install -m 0644 -o "${INSTALL_USER}" -g "${INSTALL_USER}" \
    "${SCRIPT_DIR}/tcradios-autostart.desktop" \
    "${AUTOSTART_DIR}/tcradios.desktop"
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

for sys_autostart in /etc/xdg/labwc/autostart /usr/share/labwc/autostart; do
    if [[ -f "${sys_autostart}.tcradios-backup" ]]; then
        mv -f "${sys_autostart}.tcradios-backup" "${sys_autostart}"
    fi
done

echo "Starting TCRADIOS..."
timeout 2 plymouth quit >/dev/null 2>&1 || true
runuser -u "${INSTALL_USER}" -- env DISPLAY="${DISPLAY:-:0}" /usr/local/bin/tcradios-start &
echo "Update applied from ${REPO_DIR}."
echo "If the splash is still up, unplug power once, then boot again."

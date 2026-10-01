#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "Run this installer with sudo: sudo ./install_raspberry_pi_kiosk.sh" >&2
    exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_USER="${SUDO_USER:-}"

if [[ -z "${INSTALL_USER}" || "${INSTALL_USER}" == "root" ]]; then
    echo "Run this installer with sudo from the desktop user account." >&2
    exit 1
fi

INSTALL_HOME="$(getent passwd "${INSTALL_USER}" | cut -d: -f6)"
if [[ -z "${INSTALL_HOME}" || ! -d "${INSTALL_HOME}" ]]; then
    echo "Could not determine the home directory for ${INSTALL_USER}." >&2
    exit 1
fi

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

echo "Installing Plymouth and the TCRADIOS boot theme..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y plymouth plymouth-themes

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
LOCK_DIR="\${XDG_RUNTIME_DIR:-/tmp}"
exec 9>"\${LOCK_DIR}/tcradios-\${UID}.lock"
flock -n 9 || exit 0
cd $(printf '%q' "${SCRIPT_DIR}")
exec /usr/bin/python3 $(printf '%q' "${SCRIPT_DIR}/touch_radio.py")
EOF
chmod 0755 /usr/local/bin/tcradios-start

AUTOSTART_DIR="${INSTALL_HOME}/.config/autostart"
install -d -o "${INSTALL_USER}" -g "${INSTALL_USER}" "${AUTOSTART_DIR}"
install -m 0644 -o "${INSTALL_USER}" -g "${INSTALL_USER}" \
    "${SCRIPT_DIR}/boot/tcradios-autostart.desktop" \
    "${AUTOSTART_DIR}/tcradios.desktop"

# Raspberry Pi OS Bookworm uses labwc; the lock in the launcher prevents a
# duplicate process if the desktop also handles the XDG autostart entry.
LABWC_DIR="${INSTALL_HOME}/.config/labwc"
LABWC_AUTOSTART="${LABWC_DIR}/autostart"
install -d -o "${INSTALL_USER}" -g "${INSTALL_USER}" "${LABWC_DIR}"
touch "${LABWC_AUTOSTART}"
if ! grep -qxF "/usr/local/bin/tcradios-start &" "${LABWC_AUTOSTART}"; then
    printf '\n/usr/local/bin/tcradios-start &\n' >> "${LABWC_AUTOSTART}"
fi
chown "${INSTALL_USER}:${INSTALL_USER}" "${LABWC_AUTOSTART}"

if command -v raspi-config >/dev/null 2>&1; then
    echo "Enabling desktop auto-login..."
    raspi-config nonint do_boot_behaviour B4 || \
        echo "Warning: desktop auto-login could not be enabled automatically." >&2
fi

systemctl set-default graphical.target

echo
echo "TCRADIOS branded boot is installed."
echo "Backups:"
echo "  ${CONFIG_FILE}.tcradios-backup"
echo "  ${CMDLINE_FILE}.tcradios-backup"
echo "Reboot to activate it: sudo reboot"

#!/usr/bin/env bash
# Restore the last working radio without touching the LCD driver.
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "Run: sudo ./boot/unstick.sh" >&2
    exit 1
fi

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="${SUDO_USER:-}"
if [[ -z "${USER_NAME}" || "${USER_NAME}" == "root" ]]; then
    echo "Run from the Pi desktop user with sudo." >&2
    exit 1
fi
USER_HOME="$(getent passwd "${USER_NAME}" | cut -d: -f6)"

timeout 2 plymouth quit >/dev/null 2>&1 || true
pkill -9 -f touch_radio.py >/dev/null 2>&1 || true
sleep 0.3
rm -f /tmp/tcradios-*.lock

rm -f /usr/local/bin/tcradios-session \
      /usr/share/wayland-sessions/tcradios.desktop \
      /usr/share/xsessions/tcradios.desktop \
      /etc/lightdm/lightdm.conf.d/91-tcradios-session.conf \
      "${USER_HOME}/.dmrc"

if [[ -f "/var/lib/AccountsService/users/${USER_NAME}" ]]; then
    sed -i '/^XSession=tcradios/d;/^Session=tcradios/d' \
        "/var/lib/AccountsService/users/${USER_NAME}" || true
fi

if [[ -d "${USER_HOME}/.config/autostart" ]]; then
    find "${USER_HOME}/.config/autostart" -maxdepth 1 -name '*.desktop' \
        ! -name 'tcradios.desktop' -print0 \
        | while IFS= read -r -d '' file; do
        if python3 - "${file}" <<'PY'
from pathlib import Path
import sys
lines = [line.strip() for line in Path(sys.argv[1]).read_text(errors="replace").splitlines() if line.strip()]
raise SystemExit(0 if lines == ["[Desktop Entry]", "Hidden=true"] else 1)
PY
        then
            rm -f "${file}"
        fi
    done
fi

LXDIR="${USER_HOME}/.config/lxsession/LXDE-pi"
mkdir -p "${LXDIR}"
if [[ -f /etc/xdg/lxsession/LXDE-pi/autostart ]]; then
    grep -v tcradios-start /etc/xdg/lxsession/LXDE-pi/autostart \
        > "${LXDIR}/autostart" || true
fi
touch "${LXDIR}/autostart"
if ! grep -q tcradios-start "${LXDIR}/autostart"; then
    echo '@/usr/local/bin/tcradios-start' >> "${LXDIR}/autostart"
fi
chown -R "${USER_NAME}:${USER_NAME}" "${USER_HOME}/.config/lxsession" || true

install -d -o "${USER_NAME}" -g "${USER_NAME}" "${USER_HOME}/.config/autostart"
install -m 0644 -o "${USER_NAME}" -g "${USER_NAME}" \
    "${REPO_DIR}/boot/tcradios-autostart.desktop" \
    "${USER_HOME}/.config/autostart/tcradios.desktop"

if [[ -d /usr/share/plymouth/themes/tcradios ]]; then
    install -m 0644 "${REPO_DIR}/boot/tcradios.script" \
        /usr/share/plymouth/themes/tcradios/tcradios.script
fi

cat > /usr/local/bin/tcradios-start <<EOF
#!/usr/bin/env bash
exec $(printf '%q' "${REPO_DIR}/boot/tcradios-start") "\$@"
EOF
chmod 0755 /usr/local/bin/tcradios-start
chmod 0755 "${REPO_DIR}/boot/tcradios-start"

timeout 2 plymouth quit >/dev/null 2>&1 || true
runuser -u "${USER_NAME}" -- env DISPLAY=:0 "${REPO_DIR}/boot/tcradios-start" >/dev/null 2>&1 &
echo "Restored last working radio from ${REPO_DIR}"
echo "Desktop is OK. If splash is still frozen, unplug power once."

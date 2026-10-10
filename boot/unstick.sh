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
# Stop the app and its launcher. Killing only the Python file left the
# launcher free to start a second player, so old and new audio overlapped.
for pid in $(pgrep -f '[t]ouch_radio.py' || true); do
    cmd="$(tr '\0' ' ' < "/proc/${pid}/cmdline" 2>/dev/null || true)"
    base="${cmd%% *}"
    base="${base##*/}"
    case "${base}" in
        python|python3|python3.*)
            kill -9 "${pid}" >/dev/null 2>&1 || true
            ;;
    esac
done
pkill -9 -f '[t]cradios-start' >/dev/null 2>&1 || true
sleep 0.4
rm -f /tmp/tcradios-*.lock /tmp/tcradios-player.lock

rm -f /usr/local/bin/tcradios-session \
      /usr/share/wayland-sessions/tcradios.desktop \
      /usr/share/xsessions/tcradios.desktop \
      /etc/lightdm/lightdm.conf.d/91-tcradios-session.conf \
      "${USER_HOME}/.dmrc"

if [[ -f "/var/lib/AccountsService/users/${USER_NAME}" ]]; then
    sed -i '/^XSession=tcradios/d;/^Session=tcradios/d' \
        "/var/lib/AccountsService/users/${USER_NAME}" || true
fi
if [[ -f /etc/greetd/config.toml ]] && grep -q tcradios /etc/greetd/config.toml; then
    python3 - <<'PY'
from pathlib import Path
path = Path("/etc/greetd/config.toml")
lines, skip = [], False
for line in path.read_text().splitlines():
    stripped = line.strip()
    if stripped == "[initial_session]":
        skip = True
        continue
    if skip and stripped.startswith("["):
        skip = False
    if skip:
        continue
    lines.append(line)
path.write_text("\n".join(lines).rstrip() + "\n")
PY
fi
for sys_autostart in /etc/xdg/labwc/autostart /usr/share/labwc/autostart; do
    if [[ -f "${sys_autostart}.tcradios-backup" ]]; then
        mv -f "${sys_autostart}.tcradios-backup" "${sys_autostart}"
    fi
done
LABWC_DIR="${USER_HOME}/.config/labwc"
install -d -o "${USER_NAME}" -g "${USER_NAME}" "${LABWC_DIR}"
cat > "${LABWC_DIR}/autostart" <<'EOF'
#!/bin/sh
if [ -x /etc/xdg/labwc/autostart ]; then
    /etc/xdg/labwc/autostart &
elif [ -x /usr/share/labwc/autostart ]; then
    /usr/share/labwc/autostart &
fi
/usr/local/bin/tcradios-start &
EOF
chown "${USER_NAME}:${USER_NAME}" "${LABWC_DIR}/autostart"
chmod 0755 "${LABWC_DIR}/autostart"

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
systemctl enable tcradios-release-display.service >/dev/null 2>&1 || true
systemctl mask plymouth-quit-wait.service >/dev/null 2>&1 || true
systemctl start tcradios-release-display.service >/dev/null 2>&1 || true

timeout 2 plymouth quit >/dev/null 2>&1 || true
runuser -u "${USER_NAME}" -- env DISPLAY=:0 "${REPO_DIR}/boot/tcradios-start" >/dev/null 2>&1 &
echo "Restored last working radio from ${REPO_DIR}"
echo "Desktop is OK. If splash is still frozen, unplug power once."

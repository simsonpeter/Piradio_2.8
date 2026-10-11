#!/usr/bin/env bash
# One-script install for Raspberry Pi 5 + official 7-inch Touch Display 2.
# Does not install the GoodTFT LCD35 driver.
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "Run: sudo ./install_official_7inch.sh" >&2
    exit 1
fi

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export TCRADIOS_SKIP_LCD=1
export TCRADIOS_DISPLAY=official7
echo "Installing TCRADIOS for the official 7-inch DSI touchscreen..."
exec "${ROOT}/install_raspberry_pi_kiosk.sh" "$@"

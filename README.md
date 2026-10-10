# PiRadio.3.5

Touchscreen internet radio for Raspberry Pi. Use the official 7-inch installer
on a Pi 5 with Raspberry Pi Touch Display 2 (720×1280). The original 3.5-inch
GoodTFT LCD35 installer remains available below.

## Raspberry Pi 5 + official 7-inch touchscreen

Install Raspberry Pi OS Desktop, connect the official 7-inch DSI panel (ribbon
to CAM/DISP, power from GPIO), connect the Pi to the internet, open a terminal,
and paste this single command:

```bash
sudo apt update && sudo apt install -y git && rm -rf "$HOME/tcradio" && git clone https://github.com/simsonpeter/Piradio_2.8.git "$HOME/tcradio" && cd "$HOME/tcradio" && sudo ./install_official_7inch.sh
```

That script installs dependencies, splash, autostart, and the 7-inch UI. It does
**not** install the GoodTFT LCD35 driver. Reboot when it finishes:

```bash
sudo reboot
```

## 3.5-inch GoodTFT LCD35 installation

```bash
sudo apt update && sudo apt install -y git && rm -rf "$HOME/tcradio" && git clone https://github.com/simsonpeter/Piradio_2.8.git "$HOME/tcradio" && cd "$HOME/tcradio" && sudo ./install_raspberry_pi_kiosk.sh
```

The 3.5-inch installer automatically:

- installs all Python, VLC, audio, Bluetooth, font, and YouTube dependencies;
- installs the GoodTFT LCD35 driver with 270-degree screen and touch rotation;
- configures the `TCRADIOS by JayathaSoft` boot splash;
- enables quiet, faster boot and desktop auto-login;
- removes known legacy launchers that can start the radio twice;
- starts PiRadio automatically after boot.

The GoodTFT driver reboots the Raspberry Pi automatically during the first
installation. No separate LCD commands are required.

## Updating an existing installation

Do not re-run the full installer. That can freeze the splash.

```bash
cd "$HOME/tcradio"
git fetch origin
git checkout main
git reset --hard origin/main
sudo ./boot/unstick.sh
```

Additional boot and troubleshooting details are available in
[`boot/README.md`](boot/README.md).

# PiRadio.3.5

Touchscreen internet radio designed for the 3.5-inch GoodTFT LCD35 Raspberry
Pi display.

## Fresh Raspberry Pi OS installation

Install Raspberry Pi OS Desktop, connect the Pi to the internet, open a
terminal, and paste this single command:

```bash
sudo apt update && sudo apt install -y git && rm -rf "$HOME/tcradio" && git clone https://github.com/simsonpeter/Piradio_2.8.git "$HOME/tcradio" && cd "$HOME/tcradio" && sudo ./install_raspberry_pi_kiosk.sh
```

The installer automatically:

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

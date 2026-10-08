# TCRADIOS branded Raspberry Pi boot

The installer configures:

- every required Python, VLC, YouTube, audio, Bluetooth, font, and boot package;
- a dependency import check that stops immediately if anything is unavailable;
- a black Plymouth splash displaying `TCRADIOS` and `by JayathaSoft`;
- quiet Linux boot options that hide the Raspberry Pi logo, text, and cursor;
- removal of known legacy launchers that can start the radio twice;
- removal of the long Plymouth and network-online boot waits;
- the GoodTFT `LCD35-show` driver with 270-degree rotation;
- desktop auto-login where `raspi-config` is available;
- automatic fullscreen launch of `touch_radio.py`;
- the GoodTFT LCD35 driver with 270-degree screen and touch rotation;
- a five-second in-app splash that covers the remaining application startup time.

Run from the repository directory on the Raspberry Pi:

```bash
chmod +x install_raspberry_pi_kiosk.sh
sudo ./install_raspberry_pi_kiosk.sh
```

The GoodTFT driver reboots the Raspberry Pi automatically at the end. To
install TCRADIOS without modifying the display driver, use:

```bash
sudo ./install_raspberry_pi_kiosk.sh --skip-lcd
sudo reboot
```

The installer supports both `/boot/firmware` and legacy `/boot` layouts. It
backs up `config.txt` and `cmdline.txt` before changing them. On a fresh
Raspberry Pi OS Desktop installation, no separate dependency-install command
is required.

On the first installation, the reviewed GoodTFT driver revision is downloaded
from `goodtft/LCD-show`, configured as `LCD35` at 270 degrees, and reboots the
Pi automatically. Later installer runs detect the existing display driver and
do not reinstall it. To intentionally skip display setup, run:

```bash
sudo TCRADIOS_SKIP_LCD=1 ./install_raspberry_pi_kiosk.sh
```

The earliest firmware output can vary by Raspberry Pi model and attached
display. Normal Raspberry Pi OS boot logos and console messages are hidden.

If automatic launch fails, inspect:

```bash
cat ~/.tcradios-start.log
```

The installer registers both XDG and Labwc autostart when Labwc is present,
because some Raspberry Pi OS images include Labwc without using it for the
active session. A shared process lock prevents duplicate radio launches. The
launcher waits for display `:0` before starting the radio.

## Bluetooth audio

The installer adds the complete Bluetooth-capable audio stack for the sound
server installed on the Pi. If a speaker reports
`br-connection-profile-unavailable` after an upgrade, run the installer again
and reboot:

```bash
sudo ./install_raspberry_pi_kiosk.sh
```

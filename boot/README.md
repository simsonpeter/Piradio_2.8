# TCRADIOS branded Raspberry Pi boot

The installer configures:

- a black Plymouth splash displaying `TCRADIOS` and `by JayathaSoft`;
- quiet Linux boot options that hide the Raspberry Pi logo, text, and cursor;
- desktop auto-login where `raspi-config` is available;
- automatic fullscreen launch of `touch_radio.py`;
- an in-app splash that covers the remaining application startup time.

Run from the repository directory on the Raspberry Pi:

```bash
chmod +x install_raspberry_pi_kiosk.sh
sudo ./install_raspberry_pi_kiosk.sh
sudo reboot
```

The installer supports both `/boot/firmware` and legacy `/boot` layouts. It
backs up `config.txt` and `cmdline.txt` before changing them.

The earliest firmware output can vary by Raspberry Pi model and attached
display. Normal Raspberry Pi OS boot logos and console messages are hidden.

If automatic launch fails, inspect:

```bash
cat ~/.tcradios-start.log
```

The launcher waits for display `:0` before starting the radio.

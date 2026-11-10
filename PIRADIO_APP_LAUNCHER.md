# PiRadio 7 — Reopen the Python app without rebooting

PiRadio 7 is an existing Python/Pygame application in `touch_radio.py`.
This update adds a reusable launcher, rather than changing the radio engine.

## Install the app launcher once

From a terminal **on the Raspberry Pi**, as your normal desktop user:

```bash
cd ~/tcradio
git pull --ff-only origin feature/7inch-smart-photo-frame
bash install_piradio_app_launcher.sh
```

**Do not run the installer with sudo.** It does not change the existing
kiosk startup configuration or your boot splash.

After installation, PiRadio 7 is available from your desktop's application
menu under **Sound & Video**, and as a **PiRadio7** desktop icon if desktop
icons are enabled. Both start the real Python app, with radio, Tamil Bible,
YouTube, Smart Photo Frame and floating navigation.

If PiRadio has been closed, it can be reopened from a terminal or via SSH,
**without restarting the Pi**:

```bash
~/.local/bin/piradio7
```

To check whether PiRadio is already running:

```bash
~/.local/bin/piradio7 status
```

The command returns immediately and opens PiRadio on the existing graphical
session. The original `boot/tcradios-start` launcher uses an exclusive lock
to prevent multiple instances. After PiRadio exits, the lock is released and
the application can be launched again.

## Important for PiRadio kiosk mode

The original kiosk installer deliberately hides the desktop panel and desktop
icons on certain Raspberry Pi OS images. That means a shortcut file can be
correctly installed but **not visible on the screen** when PiRadio closes.
The terminal/SSH launch command above still works. A visible desktop icon
requires a desktop session with an icon-handling file manager enabled;
the launcher installer does not change the kiosk's display manager or desktop
settings.

## Troubleshooting

If the application fails to appear, check the startup log:

```bash
tail -n 60 ~/.tcradios-start.log
```

If `~/.local/bin/piradio7` reports that it is already running, do not
start another copy. PiRadio's original automatic boot startup is unchanged.

**Note:** The GitHub update creates and tests the launcher files, but cannot
save them onto your Pi remotely. Run the one-time installation command above
on the Raspberry Pi to make the desktop launcher available.

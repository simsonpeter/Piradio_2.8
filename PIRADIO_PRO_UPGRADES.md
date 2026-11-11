# PiRadio 7 Smart Media Hub V2 — Three Pro Upgrades

All three phases are on **`feature/7inch-smart-media-hub-v2`**. Existing Radio,
Tamil Bible, YouTube Cinema, Guest Cast, Weather, Smart Remote, Photo Frame
and the optional Home Assistant page remain preserved.

**Pre-upgrade GitHub backup:** `backup/7inch-v2-pre-pro-upgrades-2026-11-11`
is pinned to the last existing working commit
`536f4bc0ed17f3b69bfb115e06f9c9602692867d`.

## Phase 1: Audio Visualizer Pro

- Open the PiRadio **Home** dashboard and tap **VISUALIZER** on Now Playing.
- Native 800 × 480 black/cyan page with 24 frequency-band bars.
- Only authentic PCM from the *current output sink monitor* is displayed.
- The optional monitor reads from PipeWire/PulseAudio, **not** a microphone.
- It does not restart, stop, pause, mute, re-route or resample your main
  VLC, MPV or Bible audio.
- It stops capturing when the page closes.
- If you use direct ALSA hardware playback that bypasses PulseAudio /
  PipeWire, no live samples may be visible. The page will not fake bars.
- Libraries: `python3-numpy`, `pulseaudio-utils` (provides `parec` and
  `pactl`). These tools do not require replacing your installed sound server.

Check dependencies on Raspberry Pi OS Trixie:

```bash
/usr/bin/python3 -c "import numpy; print('NumPy OK')"
command -v parec
command -v pactl
pactl get-default-sink
```

If NumPy or the PulseAudio utilities are missing:

```bash
sudo apt update
sudo apt install -y python3-numpy pulseaudio-utils
```

## Phase 2: Bluetooth Auto-Reconnect 2.0

- Reuses the existing Bluetooth **preferred speaker** stored in
  `~/.radio_audio`; no new pairing screen or duplicated device list.
- Periodic background checks (about 40 seconds when connected).
- When the selected paired speaker disconnects, reconnects with gradual
  retry delays of 25s, 50s, 100s, 180s and 300s.
- Does not automatically pair with unknown nearby devices.
- Pauses background checks while manual Bluetooth actions hold the
  AudioOutputManager lock.
- Bluetooth Settings shows a small connection/retry status.
- If you have no selected Bluetooth device, background reconnect remains
  inactive; the Pi's built-in output is unaffected.

**Prerequisite:** Connect and select your speaker once through PiRadio's
Bluetooth Settings. The speaker must be powered on and within range.

## Phase 3: Smart Photo Frame Pro

- Open Photo Frame on the Pi, then open `http://PI-IP:8080/frame` on your
  phone. Enter the PIN displayed on PiRadio.
- New **Photo albums** section allows creating up to 12 albums and selecting
  one to display. Album names are validated; no arbitrary file paths.
- All Photos selects the complete combined gallery; existing root images
  stay in place. **No migration, deletion or overwriting of legacy photos.**
- Upload new photos to the selected album or the original gallery.
- New transitions: Smooth fade (0.6 s), Cinematic fade (1.5 s), Instant.
- Album selection and transition style persist across app restarts in a
  separate private settings file near the existing Photo Frame settings.
- Existing limits still apply: 300 total photos, 20MB per photo,
  128MB per upload and 1GB total stored photos.
- Album controls use the same existing 6-digit pairing PIN + bearer token.

## Updating an existing PiRadio 7 installation

```bash
cd ~/tcradio
git pull --ff-only origin feature/7inch-smart-media-hub-v2
python3 -m unittest discover -s tests -p 'test_audio_visualizer.py' -v
python3 -m unittest discover -s tests -p 'test_bluetooth_reconnect.py' -v
python3 -m unittest discover -s tests -p 'test_photo_frame_pro.py' -v
```

If tests show `OK`, restart PiRadio using your normal launcher (or
`sudo reboot` for your kiosk setup).

**Visual monitor caveat:** The visualizer can only display bars for PCM
captured by the current output sink. If audio plays but no bars show, check
whether the stream is being routed through PipeWire/PulseAudio. Do not change
the functioning player output simply to force the visualizer to display
something.

**Bluetooth caveat:** Software can retry a paired speaker but cannot force
a powered-off speaker to connect.

## Rollback without deleting anything

Your pre-upgrade branch is saved on GitHub. If the upgrade does not work on
your display, do not run `git reset --hard` or remove gallery files.
Instead, switch cleanly to the backed-up commit and restart the app:

```bash
cd ~/tcradio
git fetch origin backup/7inch-v2-pre-pro-upgrades-2026-11-11
git switch -c pi7-before-pro origin/backup/7inch-v2-pre-pro-upgrades-2026-11-11
sudo reboot
```

Use this only if you need to roll back and your tracked working tree is
clean; the normal upgrade is a fast-forward pull. The Photo Frame album
settings and existing pictures live outside the Git repository and remain
intact.

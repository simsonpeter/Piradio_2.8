# PiRadio 7 — Smart Media Hub V2 (development branch)

This is an incremental update of the existing Python/Pygame PiRadio app.
It is **not** a replacement firmware, a clean installer or a second radio.

## Protected versions

- Existing development baseline: `feature/7inch-smart-photo-frame`
- Independent GitHub backup: `backup/7inch-smart-photo-frame-2026-11-10`
- New ongoing development: `feature/7inch-smart-media-hub-v2`
- Backup source commit: `e10f5434b7fd18b516e02f54552769f897f538aa`

Neither the backup nor the original branch should be rewritten while V2 is
developed. The original `main` branch is also not modified.

## Phase 1 status

Completed in GitHub:
- Created a pinned backup branch and a separate V2 branch.
- Added isolated media-state unit tests and dedicated CI checks.
- Kept the original kiosk and Python app launchers unchanged.

**Not performed:** no Raspberry Pi installation, no SD card image, no backup
of local-only station preferences, photo files, Wi-Fi/Bluetooth settings or
user configuration. Make a separate local-data backup before deploying V2.

## Phase 2 status — initial safe integration

Added `media_session.py` with a pure-Python, hardware-free snapshot
normalizer. Source precedence is MPV (including paused/minimized) over Bible
over VLC. This eliminates stale VLC station metadata from the remote's
now-playing and status API while MPV owns playback.

- `GET /api/media/session`: normalized source, title, playing, paused,
  position, duration, seekable, minimized, volume and station index.
- `GET /api/status`: same snapshot, preserving its old keys for older clients.
- `GET /api/nowplaying`: uses the same active title, not stale radio metadata.
- Existing VLC, Bible, MPV, touchscreen and guest control code is otherwise
  preserved. **The touchscreen visual integration is a follow-up.**

The module does not change audio routing or the player processes; it only
shares a reliable snapshot. Tests cover casting, paused MPV, Bible, VLC,
seekability, YouTube audio and invalid metadata.

## Safe Raspberry Pi update, only after real-device validation is planned

First check which repository your existing `~/tcradio` directory uses:

```bash
cd ~/tcradio
git remote -v
git branch --show-current
git status --short
```

Make a backup of local settings, photo uploads, and `~/tcradio` before
switching branches. Do **not** use `git reset --hard` or `rm -rf`.

To test the V2 branch **only if the working tree is clean** and the origin is
`simsonpeter/Piradio_2.8`:

```bash
cd ~/tcradio
git fetch origin
git switch --track origin/feature/7inch-smart-media-hub-v2
python3 -m py_compile media_session.py touch_radio.py
python3 -m unittest discover -s tests -p 'test_media_session.py' -v
```

If the local branch is already present, use
`git switch feature/7inch-smart-media-hub-v2` followed by
`git pull --ff-only`. Do not rerun the full kiosk installer.

To return to the original Git branch:
```bash
cd ~/tcradio
git switch feature/7inch-smart-photo-frame
```

Do not perform the switch on a dirty working tree, or while an existing
PiRadio process is running. Reopening the app through its installed launcher
uses the currently checked-out code. If device validation fails, roll back
before restarting the app.

## Remaining phases

1. Extend shared media state to the touchscreen mini-player and full player;
   route all transport commands through a single controller.
2. Redesign 800×480 navigation with safe touch hit targets.
3. Stabilize YouTube cinema, seek/minimize/restore and remote control.
4. Improve LAN guest media, phone remote and optional screen mirroring.
5. Enhance Photo Frame and screensaver without stopping audio.
6. Polish Tamil Bible, Radio, Bluetooth and weather.
7. Run Raspberry Pi Trixie acceptance tests before release.

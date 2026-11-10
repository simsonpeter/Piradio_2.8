# PiRadio 7 — Smart Photo Frame

This feature lives on the separate branch
`feature/7inch-smart-photo-frame` and preserves the current
Radio / Bible / YouTube / Guest Cast / Live Mirror / clock screensaver.

## On the 7-inch Raspberry Pi

1. Tap **PHOTO** in the top bar (beside CAST).
2. Photo Frame fills the entire **800 × 480** display.
3. The first time, it shows a QR code and a 6-digit PIN.
4. Scan the QR code on your phone, enter the PIN and choose your photos.
5. The slideshow starts automatically after images arrive.

Once photographs are playing, tap anywhere to reveal temporary controls:
**PREV**, **PLAY / PAUSE**, **NEXT**, **FIT / FILL**, **ADD PHOTOS**,
and **EXIT**. A top-right EXIT also works in an empty gallery.

## From the phone

The photo portal is `http://<PI-LAN-IP>:8080/frame` (or port 8081 if
PiRadio is using its fallback web port). The phone and Pi must be on
the **same accessible and trusted Wi-Fi**, without AP/client isolation.

Enter the PIN visible on the Pi, then:
- Upload up to **20 JPEG, PNG, WebP or GIF photos** at once.
- Change the slideshow interval: 5, 8, 12, 20 or 30 seconds.
- Select full-screen crop (Fill) or show the entire image (Fit).
- Turn shuffle, clock and local cached weather on or off.
- Enable **Use as idle screensaver** if desired.
- Use previous, next, pause/resume, and open/close commands.

The Gallery is stored locally at
`~/Pictures/PiRadio-Frame/`; you can also copy compatible images
into that folder using SSH or a file manager. Settings are saved at
`~/.config/piradio-photo-frame.json`.

The normal PiRadio clock screensaver is **unchanged by default**.
Photo Frame only replaces it if you enable idle slideshow in the phone
settings. Audio streams do not stop when Photo Frame opens.

## Limits, privacy and compatibility

- Maximum **300 pictures**, **20 MB per picture**, **128 MB per
  upload**, up to **1 GB** total gallery storage.
- Pairing must be explicitly opened on the physical Pi. The PIN
  expires after 10 minutes; phone access lasts up to 1 hour. Leaving
  Photo Frame revokes access.
- The phone portal uses **HTTP** on the LAN, not end-to-end encryption.
  Use only on a trusted network and never expose the port publicly.
- GIF uses its **first frame** in the slideshow.
- Media files remain on the Pi until you delete them from its gallery
  folder; sending them is not a Google Photos cloud sync.
- The 7-inch screen decoder resizes each image in a background worker
  to avoid blocking Pygame touch/audio.
- Display and security tests pass in GitHub Actions, but testing with
  actual smartphone uploads and the Pi's touchscreen is still required.

## Updating

From your Pi terminal:

```sh
cd ~/tcradio
git fetch origin
git switch --track origin/feature/7inch-smart-photo-frame
sudo reboot
```

If that branch is already checked out, instead use
`git pull --ff-only` before rebooting. There is no need to rerun the
full kiosk installer.

# PiRadio 7 — Guest Cast (experimental)

This feature is **not** an official Google Chromecast / Google Cast receiver.
It is a local-network, PIN-protected **browser receiver** for guests. Android
and iPhone guests can use a web browser without installing the PiRadio remote.

## What is working in the code

- Tap **CAST** at the top right of the 7-inch PiRadio screen.
- A six-digit code appears, plus a QR code pointing to the Pi's LAN webpage,
  normally `http://<PI-LAN-IP>:8080/cast`.
- Guests connect to the **same Wi-Fi** as the Pi, scan the QR code and type PIN.
- After pairing, guests can:
  - Upload a video, one audio file, or up to 20 photos.
  - Watch photos as an 8-second-per-image looping slideshow.
  - Paste a YouTube video link (resolved by the installed MPV/yt-dlp backend).
  - Pause, stop, change volume, seek, change photos, minimize or restore.
- No second PiRadio player: guest media reuses the MPV playback process.
- Guest casting is opt-in; tapping **Close guest access** on the Pi revokes all
  guest pairing tokens. A PIN expires after ten minutes. Paired browser tokens
  expire after one hour.
- Normal PiRadio Radio/Bible, Live Mirror, YouTube remote and screensaver stay
  on the pre-existing feature branches.

## Installation

The app's existing `python3-flask`, `python3-qrcode`, Python networking and
`mpv` packages are reused. As with fullscreen YouTube playback, MPV must be
installed on the Pi:

```sh
sudo apt install mpv
```

Get the GitHub branch using your usual Git workflow and reboot/restart PiRadio.
Do **not** run the full PiRadio kiosk installer just to add Guest Cast.

## Android screen mirror (RTSP sender required)

Native Android/Google Cast screen sharing **cannot** be received automatically
by this Python server. ScreenStream (Android) can transmit its captured screen
(and supported audio) in **RTSP Server** mode.

On the Android phone:
1. Install [ScreenStream](https://github.com/dkrivoruchko/ScreenStream).
2. Join the *same Wi-Fi* as the Pi.
3. Choose **RTSP** → **Server**, configure port **8554**, and start sharing.
4. The guest opens the PiRadio Cast webpage and pairs using the screen PIN.
5. Tap **Android screen mirror**, then paste the RTSP address shown by
   ScreenStream. It should resemble `rtsp://PHONE-LAN-IP:8554/PATH`; the
   exact path comes from ScreenStream, not PiRadio.
6. Tap **Show phone screen on PiRadio**.

Screen mirroring supports only RTSP sources with numeric IPv4 addresses in
the Pi's local /24 network, on port 554, 8554, or 8555. Most DRM-protected apps
and some internal-audio captures cannot be mirrored.

## Limits and privacy

- Guests need an accessible private/local Wi-Fi connection. **Guest isolation**
  (AP/client isolation) may block this even on the same SSID.
- The guest web page is ordinary **HTTP on the LAN**. Use only on networks you
  trust; pairing and phone commands are not encrypted end-to-end on that local
  connection. Do not port-forward 8080/8081 to the public internet or enable
  Tailscale Funnel for guest casting.
- Supported photo formats: JPEG, PNG, WebP, GIF. Audio formats: MP3, AAC, M4A,
  OGG/Opus, FLAC, WAV. Video formats: MP4, M4V, MOV, WebM, MKV, depending on
  codecs MPV/FFmpeg can decode.
- 256 MB per upload, up to 20 photos (20 MB each). Files are stored in a
  private cache under `~/.cache/piradio-guest-cast`. Previously cast upload
  files are deleted when a new upload replaces them or Stop is pressed.
- Casting a YouTube URL needs working `yt-dlp` and internet access.
- Guest media playback was validated in GitHub CI using mocked MPV; actual
  touchscreen, SD-card space, Wi-Fi throughput, codecs and RTSP must still be
  tested on the Raspberry Pi.
- The YouTube app's built-in **Cast device list** is not implemented by this
  feature. This is not AirPlay or Miracast either.

If the webpage cannot load, confirm which PiRadio port is running (8080 or
8081), and that the phone and Pi can reach each other over the local Wi-Fi.

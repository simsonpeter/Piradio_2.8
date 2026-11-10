# PiRadio 7 — Dedicated TCRADIOS Receiver

This branch separates **TCRADIOS live radio**, **YouTube audio**, **fullscreen YouTube video/guest media**, and **Tamil Bible** without adding YouTube audio links to the radio station list.

### Player ownership

| Source | Playback engine | Stored station list |
|---|---|---|
| TCRADIOS live stations | Dedicated VLC `player` | `stations` (the radio list) |
| YouTube audio | Independent VLC `youtube_audio_player` | `youtube_queue` (separate track queue) |
| YouTube video, guests' uploaded media, screen stream | MPV `youtube_video` | MPV playlist / stream |
| Tamil Bible | Dedicated `BiblePlayer` VLC instance | Bible book/chapter state |

Only one of these four sources is intended to be audible at any time. Starting a new source stops the other active source, preserving the previously selected live radio station.

### Return to TCRADIOS

- On the physical Pi, tap **RADIO** from any page. The previous live station resumes. The radio page's large artwork, name, previous/next and play/pause target **TCRADIOS**, never YouTube.
- On the remote app, tap **Radio** or the **Back to TCRADIOS** button on the YouTube page. The phone sends `POST /api/radio/activate`.
- The radio station grid now contains only actual station entries; YouTube tracks are not appended.
- Selecting a live station on the remote uses the existing `/api/play/<index>` endpoint, which explicitly rejects non-radio YouTube entries.
- When YouTube audio is active, the Home mini-player and remote Now Playing reflect the YouTube title. YouTube previous/next remain inside its own queue.
- Launching Bible or Guest Cast stops both VLC sources before starting their own media.

### Verification

GitHub Actions runs `tests/test_dedicated_tcradios.py` with simulated VLC players. It verifies independent station selection, switching from YouTube back to radio, previous/next isolation, remote activation and shared audio ownership.

Actual Raspberry Pi testing is still required. No new dependencies or kiosk installer are needed; update the GitHub branch and reboot to load the new Python files.

The original `feature/7inch-guest-cast` branch is unchanged and can serve as a rollback point.

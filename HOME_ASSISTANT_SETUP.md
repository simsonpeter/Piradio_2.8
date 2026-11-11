# PiRadio 7 — Optional Home Assistant integration

**Status:** Home Assistant client, touchscreen device page and Home shortcut are
implemented in `feature/7inch-smart-media-hub-v2`. The integration is inactive
until you connect your own Home Assistant installation on the Raspberry Pi.

## Supported features

- Up to eight manually selected `light.*` and `switch.*` entities, including
  smart plugs represented as Home Assistant switches
- Status polling every 20 seconds in a background worker
- Tap a physical device tile on the 800×480 screen to turn it on or off
- Errors, offline devices and unknown states are shown without freezing media
- Does not open locks, doors, blinds, garages or other higher-risk devices
- Does not introduce any new unauthenticated Flask control endpoint
- Radio, Tamil Bible, YouTube, Cast, Photo Frame and existing remote are unchanged

Home Assistant itself is **not** installed by this feature. You must already
have a Home Assistant server with suitable smart devices paired to it.

## 1. Find your Home Assistant server address

On another phone or PC connected to your home network, open the existing
Home Assistant dashboard, e.g. `http://homeassistant.local:8123`, or the
private IP of the Home Assistant server. Do not use PiRadio's remote address.

In Home Assistant, go to **Developer tools → States** to find the exact entity
IDs, such as `light.living_room` or `switch.table_lamp`. Those are only
examples, not a claim that your devices have these names.

## 2. Create a long-lived access token

In Home Assistant open your **User profile → Security → Long-lived access
tokens** and create a token for PiRadio. Prefer an account restricted to the
devices this project needs, if your Home Assistant permissions allow that.

**Never paste the token into ChatGPT, GitHub, an issue, or the phone remote.**
The file below stays only on your Raspberry Pi.

## 3. Create the private config on your Raspberry Pi

Run this in PiRadio's SSH shell:

```bash
umask 077
mkdir -p ~/.config/piradio7
nano ~/.config/piradio7/home_assistant.json
```

Insert JSON in this exact format, replacing the example URL, entity IDs and
token with your own:

```json
{
  "url": "http://homeassistant.local:8123",
  "token": "PASTE_TOKEN_LOCALLY",
  "entities": [
    "light.living_room",
    "switch.table_lamp"
  ]
}
```

Save with Ctrl+O, Enter, Ctrl+X. Then run:

```bash
chmod 700 ~/.config/piradio7
chmod 600 ~/.config/piradio7/home_assistant.json
```

If Home Assistant is outside your private LAN, use a valid **HTTPS** address
with a trusted certificate. The integration rejects public plaintext HTTP and
does not disable TLS certificate verification. It also rejects redirects.

## 4. Verify and activate

```bash
cd ~/tcradio
python3 -m unittest discover -s tests -p 'test_home_assistant.py' -v
python3 -m py_compile home_assistant_bridge.py landscape_home_assistant.py touch_radio.py
```

Restart the PiRadio Python app using your existing launcher (or reboot if you
normally use kiosk auto-start). On the PiRadio **Home** dashboard, tap
**SMART HOME**. It should show the selected entities, their ON/OFF state, or
a helpful connection/error message. Tap a tile to control the device.

If you edit the JSON later, restart PiRadio to reload it.

## Security and privacy

The configuration file must have `0600` permissions or the integration
refuses to load the token. Authentication is sent only from the Pi to the
configured Home Assistant server. The phone remote and Guest Cast do not
receive the token, and Home Assistant controls are deliberately **not**
exposed through an unprotected PiRadio web endpoint.

Do not commit `~/.config/piradio7/home_assistant.json` to GitHub or place
it inside `~/tcradio`. The client uses short timeouts, no HTTP redirects,
verified certificates for HTTPS, and a small explicit entity allowlist.

## Troubleshooting

- **Not configured:** create and save the file, then restart PiRadio
- **Secure config permissions:** run `chmod 600` on the JSON file
- **Access token rejected:** generate a new token in Home Assistant
- **Home Assistant unavailable:** verify the Pi can reach the HA server URL,
  that the server is running, and that the entity IDs are correct
- **Unavailable device:** check the device in Home Assistant Developer tools
- **Nothing changes when tapping:** check the entity status is ON or OFF;
  disabled/unknown devices cannot be toggled

This integration is optional. If you do not have Home Assistant yet, you may
keep using PiRadio as before.

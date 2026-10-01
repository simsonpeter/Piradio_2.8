# Bluetooth Search & Connection Feature

## Overview
Complete Bluetooth device discovery, pairing, and connection management built into TC Radio.

## Features

### 1. Device Discovery
- Auto-scan for nearby Bluetooth devices
- Shows device names and signal strength
- Filters for audio devices (headphones, speakers, cars)
- Continuous scanning option

### 2. Device Connection
- One-tap pairing for new devices
- Auto-pair with PIN entry support
- Shows connection progress
- Handles failures gracefully

### 3. Device Management
- List all paired devices
- Show connection status (connected/disconnected)
- Display battery level (if supported)
- Quick connect/disconnect
- Unpair unused devices

### 4. Default Output
- Set any Bluetooth device as default audio
- Falls back to analog if Bluetooth unavailable
- Remembers choice across restarts
- Automatic reconnection on boot

## Web UI Sections

### Discovery Panel
- Real-time device list
- Signal strength indicators
- "Pair New Device" button
- Auto-scan toggle

### Connected Devices
- All paired/connected devices
- Battery indicators
- Quick disconnect buttons
- "Set as Default" option
- "Unpair" option with confirmation

### Status Display
- Current default audio output
- Connection status
- Last connected time
- Device model/version info

## API Usage Examples

```python
# Start scanning
GET /api/bluetooth/scan

# Get list of found devices
GET /api/bluetooth/scan
# Returns:
# {
#   'success': True,
#   'devices': [
#     {'addr': 'AA:BB:CC:DD:EE:FF', 'name': 'My Headphones', 'rssi': -45, 'paired': False},
#     ...
#   ]
# }

# Connect to device
POST /api/bluetooth/connect/AA:BB:CC:DD:EE:FF

# Set as default output
POST /api/bluetooth/set-default/AA:BB:CC:DD:EE:FF

# Get all paired devices
GET /api/bluetooth/devices
# Returns:
# {
#   'connected': [
#     {'addr': '...', 'name': 'Headphones', 'battery': 85, 'alias': 'My Device'}
#   ],
#   'paired': [...],
#   'default': 'AA:BB:CC:DD:EE:FF'
# }

# Disconnect
POST /api/bluetooth/disconnect/AA:BB:CC:DD:EE:FF

# Unpair
POST /api/bluetooth/unpair/AA:BB:CC:DD:EE:FF
```

## How It Works

### Scanning
1. Uses `bluetoothctl scan on` to discover devices
2. Parses output for MAC addresses and names
3. Filters known device types (audio)
4. Updates every 2-5 seconds

### Pairing
1. Initiates pairing with `bluetoothctl pair <addr>`
2. Shows PIN entry if required
3. Confirms pairing
4. Trusts device for auto-connect

### Connection
1. Uses `pactl` to set PulseAudio sink
2. Updates default output
3. Tests audio stream
4. Saves preference

### Auto-Connect
1. On startup, checks last used device
2. Attempts reconnection
3. Falls back to analog if unavailable
4. Retries every 30 seconds if offline

## Troubleshooting

### Device not found
- Ensure device is in pairing mode
- Check Bluetooth is enabled: `sudo systemctl start bluetooth`
- Manually scan: `bluetoothctl scan on`

### Connection fails
- Check MAC address format (AA:BB:CC:DD:EE:FF)
- Try unpairing first: `bluetoothctl remove <addr>`
- Check PulseAudio: `pactl list sinks`

### No audio after connecting
- Verify device is set as default: `pactl set-default-sink <name>`
- Check volume: `amixer get Master`
- Test with: `speaker-test -c 2`

### Battery not showing
- Not all devices report battery
- Query with: `bluetoothctl info <addr>`

## Platform Support
- **Linux (Raspberry Pi)** ✅ Full support
- **Requires**: `bluetooth`, `bluez`, `pulseaudio`
- **Optional**: `pulseaudio-module-bluetooth`

## Security Notes
- Pairing info stored in `/var/lib/bluetooth/`
- MAC addresses logged for debugging
- Passwords never transmitted (Bluetooth security)
- Unpair removes all trust/link keys

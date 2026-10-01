# New Features Added to TC Radio

## 1. ⭐ Favorites System
- Save your favorite stations and direct links
- Quick access to favorites from web UI
- Persistent storage across restarts
- One-tap favorites button on touchscreen

## 2. 🎵 Presets & Quick Presets
- Create up to 5 custom station presets
- Save/load preset groups instantly
- Name your presets (Work, Sleep, Party, etc.)
- Quick preset buttons on bottom bar

## 3. 📡 Bluetooth Management
- **Auto-scan** for nearby Bluetooth devices
- **Discover & Connect** to new Bluetooth speakers/headphones
- **Set as Default** audio output
- **Unpair** devices when needed
- Shows connection status and battery level
- Automatic reconnection on startup

## 4. 🕐 Station History
- Track last 50 played stations
- Quick jump back to recently played
- Timestamp for each playback
- Clear history option

## 5. 📊 Enhanced Station Management
- Station search/filter by name or genre
- Sort by: alphabetical, recently played, most played
- Add custom station groups
- Drag-to-reorder favorites

## 6. 🔧 Reliability Improvements
- Auto-reconnect on network loss
- Better error handling and recovery
- Stream health monitoring
- Automatic fallback to last known good station
- Session persistence (remembers volume, theme, output)

## 7. 📡 Remote Control Enhancements
- New API endpoints for all features
- Better status reporting
- Device discovery and management
- Batch operations support

## 8. 🎨 UI/UX Enhancements
- New "Favorites" tab in web app
- New "Presets" management panel
- New "Bluetooth" discovery & connection UI
- New "History" tab
- Improved device status display
- Loading states for async operations

## API Endpoints Added

### Favorites
- `POST /api/favorites/add/<station_idx>` - Add to favorites
- `POST /api/favorites/remove/<station_idx>` - Remove from favorites
- `GET /api/favorites` - Get all favorites
- `GET /api/favorites/is/<station_idx>` - Check if favorited

### Presets
- `POST /api/presets/create` - Create new preset
- `POST /api/presets/save/<preset_id>` - Save current stations to preset
- `POST /api/presets/load/<preset_id>` - Load preset stations
- `GET /api/presets` - List all presets
- `DELETE /api/presets/<preset_id>` - Delete preset

### Bluetooth
- `GET /api/bluetooth/scan` - Scan for devices
- `POST /api/bluetooth/connect/<device_addr>` - Connect to device
- `POST /api/bluetooth/disconnect/<device_addr>` - Disconnect device
- `GET /api/bluetooth/devices` - List connected devices
- `GET /api/bluetooth/status` - Get Bluetooth status
- `POST /api/bluetooth/set-default/<device_addr>` - Set as default audio
- `POST /api/bluetooth/unpair/<device_addr>` - Unpair device

### History
- `GET /api/history` - Get play history
- `POST /api/history/clear` - Clear history
- `POST /api/history/play/<idx>` - Jump to history item

### Station Management
- `GET /api/stations/search?q=<query>` - Search stations
- `GET /api/stations/filter?genre=<genre>` - Filter by genre
- `POST /api/stations/reorder` - Reorder stations

## Files Modified
- `touch_radio.py` - Main application file with all new features

## Installation Notes
- No new dependencies required (uses existing libraries)
- All features are backward compatible
- Settings stored in `/home/raspberry/.radio_*` files
- Bluetooth requires `bluetoothctl` and `pactl` (already installed)

## Configuration Files
- `/home/raspberry/.radio_favorites` - Favorite stations
- `/home/raspberry/.radio_history` - Play history
- `/home/raspberry/.radio_presets` - Preset groups
- `/home/raspberry/.radio_session` - Session state

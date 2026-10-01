#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pygame, vlc, requests, time, os, io, math, socket, sys, threading, qrcode, json, base64, random, re
from urllib.request import urlopen
from urllib.parse import urlparse
from datetime import datetime, timedelta
from flask import Flask, render_template_string, Response, jsonify, request
import subprocess

try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# --- DYNAMIC IP FUNCTIONS ---
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        try:
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
            if result.stdout:
                return result.stdout.strip().split()[0]
        except:
            pass
    return "192.168.1.100"

# --- REMOTE ACCESS / TUNNEL SETUP ---
def setup_remote_tunnel():
    """Setup cloudflare tunnel or similar for remote access"""
    try:
        # Check if cloudflared is installed
        result = subprocess.run(['which', 'cloudflared'], capture_output=True, text=True)
        if result.returncode != 0:
            print("⚠️  For remote access, install cloudflared:")
            print("   wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm")
            print("   sudo mv cloudflared-linux-arm /usr/local/bin/cloudflared")
            print("   sudo chmod +x /usr/local/bin/cloudflared")
            print("   cloudflared tunnel --url http://localhost:8080")
            return None
        
        # Try to start tunnel automatically
        tunnel_process = subprocess.Popen(
            ['cloudflared', 'tunnel', '--url', 'http://localhost:8080'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a moment and extract URL from stderr
        time.sleep(3)
        return tunnel_process
    except Exception as e:
        print(f"Tunnel setup error: {e}")
        return None

current_ip = get_local_ip()
server_url = f"http://{current_ip}:8080"
tunnel_url = None

print(f"\n{'='*50}")
print(f"🚀 TC RADIO STARTED SUCCESSFULLY!")
print(f"{'='*50}")
print(f"📱 LOCAL URL (same WiFi):")
print(f"   \033[96mhttp://{current_ip}:8080\033[0m")
print(f"\n🌍 REMOTE ACCESS (anywhere in world):")
print(f"   Option 1: Install cloudflared (free):")
print(f"   wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm")
print(f"   sudo mv cloudflared-linux-arm /usr/local/bin/cloudflared && sudo chmod +x /usr/local/bin/cloudflared")
print(f"   cloudflared tunnel --url http://localhost:8080")
print(f"\n   Option 2: Use ngrok:")
print(f"   sudo apt install ngrok")
print(f"   ngrok http 8080")
print(f"\n   Option 3: Use Tailscale (mesh VPN):")
print(f"   curl -fsSL https://tailscale.com/install.sh | sh")
print(f"   sudo tailscale up")
print(f"{'='*50}\n")

# --- AUDIO OUTPUT MANAGER ---
class AudioOutputManager:
    def __init__(self):
        self.outputs = {}
        self.current_output = 'auto'
        self.multi_mode = False
        self.scan_outputs()
    
    def scan_outputs(self):
        self.outputs = {
            'auto': {'name': 'Auto (System Default)', 'available': True, 'type': 'auto'},
            'analog': {'name': '3.5mm Jack (Analog)', 'available': False, 'type': 'alsa'},
            'hdmi': {'name': 'HDMI Audio', 'available': False, 'type': 'alsa'},
            'bluetooth': {'name': 'Bluetooth', 'available': False, 'type': 'bluez'}
        }
        
        try:
            result = subprocess.run(['aplay', '-l'], capture_output=True, text=True)
            output = result.stdout.lower()
            if 'bcm2835' in output or 'headphones' in output or 'analog' in output:
                self.outputs['analog']['available'] = True
            if 'hdmi' in output:
                self.outputs['hdmi']['available'] = True
        except Exception as e:
            print(f"Error scanning ALSA: {e}")
        
        try:
            result = subprocess.run(['pactl', 'list', 'sinks', 'short'], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'bluez' in line.lower() or 'bluetooth' in line.lower():
                        self.outputs['bluetooth']['available'] = True
                        parts = line.split()
                        if len(parts) >= 2:
                            self.outputs['bluetooth']['device'] = parts[1]
        except:
            pass
        
        try:
            result = subprocess.run(['bluetoothctl', 'devices', 'Connected'], capture_output=True, text=True)
            if result.stdout.strip():
                self.outputs['bluetooth']['available'] = True
                self.outputs['bluetooth']['connected_device'] = result.stdout.strip().split('\n')[0]
        except:
            pass
        
        print(f"Audio outputs detected: {[(k, v['available']) for k, v in self.outputs.items()]}")

    def set_output(self, output_name):
        if output_name not in self.outputs:
            return False
        
        self.current_output = output_name
        
        if output_name == 'auto':
            os.system("amixer cset numid=3 0")
            return True
        elif output_name == 'analog':
            os.system("amixer cset numid=3 1")
            return True
        elif output_name == 'hdmi':
            os.system("amixer cset numid=3 2")
            return True
        elif output_name == 'bluetooth':
            try:
                result = subprocess.run(['pactl', 'list', 'sinks', 'short'], capture_output=True, text=True)
                for line in result.stdout.split('\n'):
                    if 'bluez' in line:
                        sink_name = line.split()[1]
                        subprocess.run(['pactl', 'set-default-sink', sink_name])
                        return True
            except Exception as e:
                print(f"Bluetooth switch error: {e}")
                return False
        return False
    
    def enable_multi_output(self, outputs_list):
        if not outputs_list or len(outputs_list) < 2:
            self.multi_mode = False
            return False
        
        try:
            sinks = []
            result = subprocess.run(['pactl', 'list', 'sinks', 'short'], capture_output=True, text=True)
            
            for output in outputs_list:
                if output == 'analog' and 'alsa_output' in result.stdout:
                    for line in result.stdout.split('\n'):
                        if 'analog' in line.lower() or 'bcm2835' in line.lower():
                            sinks.append(line.split()[1])
                            break
                elif output == 'hdmi' and 'hdmi' in result.stdout.lower():
                    for line in result.stdout.split('\n'):
                        if 'hdmi' in line.lower():
                            sinks.append(line.split()[1])
                            break
                elif output == 'bluetooth' and 'bluez' in result.stdout.lower():
                    for line in result.stdout.split('\n'):
                        if 'bluez' in line.lower():
                            sinks.append(line.split()[1])
                            break
            
            if len(sinks) >= 2:
                sink_names = ','.join(sinks)
                subprocess.run(['pactl', 'load-module', 'module-combine-sink', f'sinks={sink_names}', 'sink_name=combined'])
                subprocess.run(['pactl', 'set-default-sink', 'combined'])
                self.multi_mode = True
                return True
                
        except Exception as e:
            print(f"Multi-output error: {e}")
        
        self.multi_mode = False
        return False
    
    def set_volume(self, volume):
        try:
            subprocess.run(['amixer', 'set', 'PCM', f'{volume}%'], capture_output=True)
            if self.current_output == 'bluetooth':
                subprocess.run(['pactl', 'set-sink-volume', '@DEFAULT_SINK@', f'{volume}%'])
            return True
        except Exception as e:
            print(f"Volume error: {e}")
            return False

audio_manager = AudioOutputManager()

# --- ALARM & SLEEP TIMER SYSTEM ---
class SmartAlarm:
    def __init__(self):
        self.alarm_enabled = False
        self.alarm_time = "07:00"
        self.alarm_station_idx = 0
        self.alarm_volume_start = 20
        self.alarm_volume_end = 60
        self.alarm_fade_duration = 300
        self.alarm_days = [True, True, True, True, True, False, False]
        
        self.sleep_timer_enabled = False
        self.sleep_duration = 1800
        self.sleep_start_time = 0
        self.sleep_volume_fade = True
        self.sleep_stop_method = "pause"
        
        self.alarm_file = "/home/raspberry/.radio_alarm"
        self.sleep_file = "/home/raspberry/.radio_sleep"
        self.load_settings()
    
    def load_settings(self):
        try:
            if os.path.exists(self.alarm_file):
                with open(self.alarm_file, 'r') as f:
                    data = json.load(f)
                    self.alarm_enabled = data.get('enabled', False)
                    self.alarm_time = data.get('time', "07:00")
                    self.alarm_station_idx = data.get('station_idx', 0)
                    self.alarm_volume_start = data.get('volume_start', 20)
                    self.alarm_volume_end = data.get('volume_end', 60)
                    self.alarm_fade_duration = data.get('fade_duration', 300)
                    self.alarm_days = data.get('days', [True, True, True, True, True, False, False])
        except:
            pass
        
        try:
            if os.path.exists(self.sleep_file):
                with open(self.sleep_file, 'r') as f:
                    data = json.load(f)
                    self.sleep_duration = data.get('duration', 1800)
                    self.sleep_volume_fade = data.get('volume_fade', True)
                    self.sleep_stop_method = data.get('stop_method', "pause")
        except:
            pass
    
    def save_alarm_settings(self):
        try:
            data = {
                'enabled': self.alarm_enabled,
                'time': self.alarm_time,
                'station_idx': self.alarm_station_idx,
                'volume_start': self.alarm_volume_start,
                'volume_end': self.alarm_volume_end,
                'fade_duration': self.alarm_fade_duration,
                'days': self.alarm_days
            }
            with open(self.alarm_file, 'w') as f:
                json.dump(data, f)
        except:
            pass
    
    def save_sleep_settings(self):
        try:
            data = {
                'duration': self.sleep_duration,
                'volume_fade': self.sleep_volume_fade,
                'stop_method': self.sleep_stop_method
            }
            with open(self.sleep_file, 'w') as f:
                json.dump(data, f)
        except:
            pass
    
    def check_alarm(self):
        if not self.alarm_enabled:
            return False
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_weekday = now.weekday()
        if (current_time == self.alarm_time and 
            self.alarm_days[current_weekday] and
            not self.sleep_timer_enabled):
            return True
        return False
    
    def start_sleep_timer(self, duration_minutes=None):
        if duration_minutes:
            self.sleep_duration = duration_minutes * 60
        self.sleep_timer_enabled = True
        self.sleep_start_time = time.time()
        print(f"Sleep timer started for {self.sleep_duration//60} minutes")
    
    def stop_sleep_timer(self):
        self.sleep_timer_enabled = False
        print("Sleep timer stopped")
    
    def check_sleep_timer(self):
        if not self.sleep_timer_enabled:
            return False
        elapsed = time.time() - self.sleep_start_time
        if elapsed >= self.sleep_duration:
            self.sleep_timer_enabled = False
            return True
        return False
    
    def get_sleep_remaining(self):
        if not self.sleep_timer_enabled:
            return 0
        elapsed = time.time() - self.sleep_start_time
        remaining = max(0, self.sleep_duration - elapsed)
        return int(remaining // 60)
    
    def trigger_alarm(self, player, stations, current_idx, vol_level):
        print(f"ALARM TRIGGERED! Playing {stations[self.alarm_station_idx]['name']}")
        original_station = current_idx
        original_volume = vol_level
        was_playing = player.is_playing()
        player.stop()
        fade_start_time = time.time()
        player.audio_set_volume(self.alarm_volume_start)
        volume_range = self.alarm_volume_end - self.alarm_volume_start
        return {
            'active': True,
            'start_time': fade_start_time,
            'duration': self.alarm_fade_duration,
            'start_volume': self.alarm_volume_start,
            'end_volume': self.alarm_volume_end,
            'volume_range': volume_range,
            'original_station': original_station,
            'original_volume': original_volume,
            'was_playing': was_playing,
            'new_station_idx': self.alarm_station_idx,
            'alarm_station_idx': self.alarm_station_idx
        }

alarm_system = SmartAlarm()

# --- DIRECT LINKS MANAGER ---
class DirectLinksManager:
    def __init__(self):
        self.links = []
        self.links_file = "/home/raspberry/.radio_direct_links"
        self.load_links()
    
    def load_links(self):
        try:
            if os.path.exists(self.links_file):
                with open(self.links_file, 'r') as f:
                    self.links = json.load(f)
        except:
            self.links = []
    
    def save_links(self):
        try:
            with open(self.links_file, 'w') as f:
                json.dump(self.links, f)
        except:
            pass
    
    def add_link(self, url, title=None):
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False, "Invalid URL"
            
            ext = os.path.splitext(parsed.path)[1].lower()
            audio_types = {
                '.mp3': 'MP3 Audio',
                '.wav': 'WAV Audio',
                '.flac': 'FLAC Audio',
                '.aac': 'AAC Audio',
                '.ogg': 'OGG Audio',
                '.m4a': 'M4A Audio',
                '.wma': 'WMA Audio',
                '.opus': 'OPUS Audio'
            }
            
            file_type = audio_types.get(ext, 'Audio Stream')
            
            if not title:
                title = os.path.basename(parsed.path) or "Direct Stream"
                title = os.path.splitext(title)[0]
                title = requests.utils.unquote(title)
                title = title.replace('_', ' ').replace('-', ' ')
                title = title.title()
            
            link_entry = {
                'url': url,
                'title': title,
                'type': file_type,
                'added': datetime.now().isoformat(),
                'id': hash(url + str(time.time())) % 10000000
            }
            
            self.links.insert(0, link_entry)
            self.save_links()
            return True, link_entry
        except Exception as e:
            return False, str(e)
    
    def remove_link(self, link_id):
        self.links = [l for l in self.links if l['id'] != link_id]
        self.save_links()
        return True
    
    def get_links(self):
        return self.links

direct_links = DirectLinksManager()

# --- THEME SYSTEM ---
class Theme:
    def __init__(self, name, colors):
        self.name = name
        self.colors = colors
        self.background = colors.get('background', '#000000')
        self.primary = colors.get('primary', '#00d2ff')
        self.secondary = colors.get('secondary', '#9d50bb')
        self.accent = colors.get('accent', '#ffcc00')
        self.text = colors.get('text', '#ffffff')
        self.card = colors.get('card', 'rgba(20,20,20,0.95)')
        self.button = colors.get('button', 'rgba(30,30,30,0.95)')
        self.button_hover = colors.get('button_hover', 'rgba(50,50,50,0.95)')
        self.gradient_start = colors.get('gradient_start', '#000000')
        self.gradient_end = colors.get('gradient_end', '#000000')
        self.pygame_primary = self.hex_to_rgb(self.primary)
        self.pygame_secondary = self.hex_to_rgb(self.secondary)
        self.pygame_accent = self.hex_to_rgb(self.accent)
        self.pygame_text = self.hex_to_rgb(self.text)
        self.pygame_background = self.hex_to_rgb(self.background)
    
    def hex_to_rgb(self, hex_color):
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6 or not all(c in '0123456789abcdefABCDEF' for c in hex_color):
            return (255, 255, 255)
        try:
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        except ValueError:
            return (255, 255, 255)

THEMES = {
    'true_black': Theme('True Black', {
        'name': 'True Black',
        'background': '#000000',
        'primary': '#00d2ff',
        'secondary': '#9d50bb',
        'accent': '#ffcc00',
        'text': '#ffffff',
        'card': 'rgba(20,20,20,0.95)',
        'button': 'rgba(30,30,30,0.95)',
        'button_hover': 'rgba(50,50,50,0.95)',
        'gradient_start': '#000000',
        'gradient_end': '#000000'
    }),
    'midnight_black': Theme('Midnight Black', {
        'name': 'Midnight Black',
        'background': '#0a0a0a',
        'primary': '#00d2ff',
        'secondary': '#9d50bb',
        'accent': '#ffcc00',
        'text': '#ffffff',
        'gradient_start': '#0a0a0a',
        'gradient_end': '#1a1a1a'
    }),
    'pure_white': Theme('Pure White', {
        'name': 'Pure White',
        'background': '#ffffff',
        'primary': '#2c3e50',
        'secondary': '#3498db',
        'accent': '#e74c3c',
        'text': '#2c3e50',
        'gradient_start': '#f8f9fa',
        'gradient_end': '#e9ecef'
    }),
    'ocean_blue': Theme('Ocean Blue', {
        'name': 'Ocean Blue',
        'background': '#0f3460',
        'primary': '#00d2ff',
        'secondary': '#1e90ff',
        'accent': '#ff6b6b',
        'text': '#ffffff',
        'gradient_start': '#0f3460',
        'gradient_end': '#16213e'
    }),
    'sunset_orange': Theme('Sunset Orange', {
        'name': 'Sunset Orange',
        'background': '#ff7e5f',
        'primary': '#feb47b',
        'secondary': '#ff6b6b',
        'accent': '#2c3e50',
        'text': '#ffffff',
        'gradient_start': '#ff7e5f',
        'gradient_end': '#feb47b'
    }),
    'forest_green': Theme('Forest Green', {
        'name': 'Forest Green',
        'background': '#1a472a',
        'primary': '#2ecc71',
        'secondary': '#27ae60',
        'accent': '#f39c12',
        'text': '#ffffff',
        'gradient_start': '#1a472a',
        'gradient_end': '#2d5a27'
    }),
    'purple_haze': Theme('Purple Haze', {
        'name': 'Purple Haze',
        'background': '#6a11cb',
        'primary': '#2575fc',
        'secondary': '#8a2be2',
        'accent': '#ff416c',
        'text': '#ffffff',
        'gradient_start': '#6a11cb',
        'gradient_end': '#2575fc'
    }),
    'cyberpunk': Theme('Cyberpunk', {
        'name': 'Cyberpunk',
        'background': '#0d0221',
        'primary': '#ff00ff',
        'secondary': '#00ffff',
        'accent': '#ff6b00',
        'text': '#ffffff',
        'gradient_start': '#0d0221',
        'gradient_end': '#2d00aa'
    }),
    'golden_hour': Theme('Golden Hour', {
        'name': 'Golden Hour',
        'background': '#f39c12',
        'primary': '#e74c3c',
        'secondary': '#d35400',
        'accent': '#2c3e50',
        'text': '#ffffff',
        'gradient_start': '#f39c12',
        'gradient_end': '#e74c3c'
    }),
    'mint_fresh': Theme('Mint Fresh', {
        'name': 'Mint Fresh',
        'background': '#00b894',
        'primary': '#00cec9',
        'secondary': '#81ecec',
        'accent': '#fd79a8',
        'text': '#2d3436',
        'gradient_start': '#00b894',
        'gradient_end': '#00cec9'
    }),
    'crimson_red': Theme('Crimson Red', {
        'name': 'Crimson Red',
        'background': '#c0392b',
        'primary': '#e74c3c',
        'secondary': '#ff7675',
        'accent': '#fdcb6e',
        'text': '#ffffff',
        'gradient_start': '#c0392b',
        'gradient_end': '#e74c3c'
    })
}

current_theme = THEMES['true_black']
theme_names = list(THEMES.keys())
THEME_FILE = "/home/raspberry/.radio_theme"

def load_theme():
    global current_theme
    try:
        if os.path.exists(THEME_FILE):
            with open(THEME_FILE, 'r') as f:
                theme_name = f.read().strip()
                if theme_name in THEMES:
                    current_theme = THEMES[theme_name]
                    print(f"Loaded theme: {theme_name}")
                else:
                    current_theme = THEMES['true_black']
    except:
        current_theme = THEMES['true_black']

def save_theme(theme_name):
    try:
        with open(THEME_FILE, 'w') as f:
            f.write(theme_name)
    except:
        pass

load_theme()

CYAN = current_theme.pygame_primary
PURPLE = current_theme.pygame_secondary
GOLD = current_theme.pygame_accent
WHITE = current_theme.pygame_text
RED = (255, 50, 50)
GREEN = (50, 255, 50)
GRAY = (100, 100, 100)
BLACK = (0, 0, 0)
BACKGROUND = current_theme.pygame_background

# --- WEB REMOTE APP ---
app = Flask(__name__)

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

youtube_results_cache = []

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="theme-color" content="{{ theme.background }}">
    <title>TC Radio</title>
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="https://cdn-icons-png.flaticon.com/512/3011/3011244.png">
    <script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
    <style>
        :root {
            --bg: {{ theme.background }};
            --primary: {{ theme.primary }};
            --secondary: {{ theme.secondary }};
            --accent: {{ theme.accent }};
            --text: {{ theme.text }};
            --card: {{ theme.card }};
            --button: {{ theme.button }};
            --button-hover: {{ theme.button_hover }};
            --gradient-start: {{ theme.gradient_start }};
            --gradient-end: {{ theme.gradient_end }};
            --safe-top: env(safe-area-inset-top);
            --safe-bottom: env(safe-area-inset-bottom);
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        }
        
        html, body {
            height: 100%;
            background: var(--bg);
            color: var(--text);
            overflow: hidden;
            position: fixed;
            width: 100%;
        }
        
        .app-container {
            height: 100vh;
            height: 100dvh;
            display: flex;
            flex-direction: column;
            background: var(--bg);
            padding-top: var(--safe-top);
            padding-bottom: var(--safe-bottom);
        }
        
        .app-header {
            background: linear-gradient(180deg, rgba(0,0,0,0.8) 0%, transparent 100%);
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(10px);
        }
        
        .app-title {
            font-size: 24px;
            font-weight: 700;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .header-actions {
            display: flex;
            gap: 10px;
        }
        
        .icon-btn {
            width: 40px;
            height: 40px;
            border-radius: 12px;
            background: var(--card);
            border: 1px solid rgba(255,255,255,0.1);
            color: var(--text);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .icon-btn:hover {
            background: var(--button-hover);
            transform: scale(1.05);
        }
        
        .now-playing-bar {
            background: linear-gradient(135deg, var(--card) 0%, rgba(30,30,30,0.98) 100%);
            border-top: 1px solid rgba(255,255,255,0.1);
            padding: 12px 20px;
            display: flex;
            align-items: center;
            gap: 15px;
            position: sticky;
            bottom: 0;
            z-index: 100;
        }
        
        .np-artwork {
            width: 50px;
            height: 50px;
            border-radius: 8px;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            flex-shrink: 0;
            overflow: hidden;
        }
        
        .np-artwork img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .np-info {
            flex: 1;
            min-width: 0;
        }
        
        .np-title {
            font-size: 14px;
            font-weight: 600;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            color: var(--text);
        }
        
        .np-subtitle {
            font-size: 12px;
            color: rgba(255,255,255,0.6);
            margin-top: 2px;
        }
        
        .np-controls {
            display: flex;
            gap: 10px;
        }
        
        .np-btn {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: var(--primary);
            border: none;
            color: #000;
            font-size: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        .np-btn:active {
            transform: scale(0.95);
        }
        
        .content {
            flex: 1;
            overflow-y: auto;
            overflow-x: hidden;
            padding: 0 20px 20px;
            -webkit-overflow-scrolling: touch;
        }
        
        .content::-webkit-scrollbar {
            display: none;
        }
        
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 20px 0 15px;
        }
        
        .section-title {
            font-size: 22px;
            font-weight: 700;
        }
        
        .section-action {
            font-size: 14px;
            color: var(--primary);
            cursor: pointer;
        }
        
        .card {
            background: var(--card);
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 12px;
            border: 1px solid rgba(255,255,255,0.05);
        }
        
        .player-card {
            background: linear-gradient(135deg, var(--card) 0%, rgba(30,30,30,0.95) 100%);
            border-radius: 24px;
            padding: 30px 20px;
            text-align: center;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .big-artwork {
            width: 200px;
            height: 200px;
            margin: 0 auto 25px;
            border-radius: 20px;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 80px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.4);
            position: relative;
            overflow: hidden;
        }
        
        .big-artwork::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: linear-gradient(45deg, transparent, rgba(255,255,255,0.1), transparent);
            animation: shimmer 3s infinite;
        }
        
        @keyframes shimmer {
            0% { transform: translateX(-100%) translateY(-100%) rotate(45deg); }
            100% { transform: translateX(100%) translateY(100%) rotate(45deg); }
        }
        
        .big-title {
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 8px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .big-subtitle {
            font-size: 16px;
            color: rgba(255,255,255,0.6);
        }
        
        .controls-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-top: 25px;
        }
        
        .control-btn {
            background: var(--button);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 20px;
            color: var(--text);
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .control-btn:active {
            transform: scale(0.96);
            background: var(--button-hover);
        }
        
        .control-btn.primary {
            background: var(--primary);
            color: #000;
        }
        
        .control-icon {
            font-size: 28px;
        }
        
        .control-label {
            font-size: 12px;
            font-weight: 600;
        }
        
        .volume-section {
            margin-top: 20px;
        }
        
        .volume-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-size: 14px;
            font-weight: 600;
        }
        
        .volume-slider {
            width: 100%;
            height: 6px;
            border-radius: 3px;
            background: rgba(255,255,255,0.1);
            position: relative;
            cursor: pointer;
        }
        
        .volume-fill {
            height: 100%;
            border-radius: 3px;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
            position: relative;
        }
        
        .volume-handle {
            width: 20px;
            height: 20px;
            background: var(--text);
            border-radius: 50%;
            position: absolute;
            right: -10px;
            top: 50%;
            transform: translateY(-50%);
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }
        
        .station-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }
        
        .station-card {
            background: var(--card);
            border-radius: 16px;
            padding: 16px;
            cursor: pointer;
            transition: all 0.2s;
            border: 2px solid transparent;
            text-align: center;
            position: relative;
            overflow: hidden;
        }
        
        .station-card:active {
            transform: scale(0.96);
        }
        
        .station-card.active {
            border-color: var(--primary);
            background: linear-gradient(135deg, var(--card) 0%, rgba(0,210,255,0.1) 100%);
        }
        
        .station-card.playing::after {
            content: '▶';
            position: absolute;
            top: 8px;
            right: 8px;
            width: 24px;
            height: 24px;
            background: var(--primary);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            color: #000;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.8; transform: scale(1.1); }
        }
        
        .station-logo {
            width: 70px;
            height: 70px;
            border-radius: 50%;
            margin: 0 auto 12px;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            font-weight: 700;
            overflow: hidden;
            border: 3px solid rgba(255,255,255,0.1);
        }
        
        .station-logo img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .station-name {
            font-weight: 600;
            font-size: 14px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-bottom: 4px;
        }
        
        .station-genre {
            font-size: 12px;
            color: rgba(255,255,255,0.6);
        }
        
        .input-group {
            margin-bottom: 15px;
        }
        
        .input-label {
            display: block;
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 8px;
            color: rgba(255,255,255,0.8);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .text-input, .select-input {
            width: 100%;
            padding: 16px;
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.1);
            background: rgba(0,0,0,0.3);
            color: var(--text);
            font-size: 16px;
            transition: all 0.2s;
        }
        
        .text-input:focus, .select-input:focus {
            outline: none;
            border-color: var(--primary);
            background: rgba(0,0,0,0.5);
        }
        
        .btn-primary {
            width: 100%;
            padding: 16px;
            border-radius: 12px;
            border: none;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            color: #000;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        .btn-primary:active {
            transform: scale(0.98);
        }
        
        .quick-actions {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-top: 15px;
        }
        
        .quick-btn {
            background: var(--button);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 15px;
            color: var(--text);
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .quick-btn:active {
            background: var(--button-hover);
        }
        
        .quick-btn.danger {
            background: rgba(255,50,50,0.2);
            border-color: rgba(255,50,50,0.3);
            color: #ff6b6b;
        }
        
        .alarm-settings {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .days-selector {
            display: flex;
            justify-content: space-between;
            gap: 8px;
        }
        
        .day-btn {
            flex: 1;
            height: 44px;
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.1);
            background: rgba(0,0,0,0.3);
            color: var(--text);
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .day-btn.active {
            background: var(--primary);
            color: #000;
            border-color: var(--primary);
        }
        
        .setting-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        
        .setting-label {
            font-size: 15px;
        }
        
        .setting-value {
            font-size: 15px;
            color: var(--primary);
            font-weight: 600;
        }
        
        .link-item {
            background: var(--card);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 12px;
            cursor: pointer;
            transition: all 0.2s;
            position: relative;
        }
        
        .link-item:active {
            transform: scale(0.98);
        }
        
        .link-icon {
            width: 48px;
            height: 48px;
            border-radius: 10px;
            background: linear-gradient(135deg, var(--accent), var(--secondary));
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            flex-shrink: 0;
        }
        
        .link-info {
            flex: 1;
            min-width: 0;
        }
        
        .link-title {
            font-weight: 600;
            font-size: 15px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .link-url {
            font-size: 12px;
            color: rgba(255,255,255,0.5);
            margin-top: 2px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .link-delete {
            width: 32px;
            height: 32px;
            border-radius: 8px;
            background: rgba(255,50,50,0.1);
            border: none;
            color: #ff6b6b;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .bottom-nav {
            display: flex;
            justify-content: space-around;
            padding: 10px 0 calc(10px + var(--safe-bottom));
            background: rgba(0,0,0,0.9);
            border-top: 1px solid rgba(255,255,255,0.1);
            position: sticky;
            bottom: 0;
        }
        
        .nav-item {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
            padding: 8px;
            color: rgba(255,255,255,0.5);
            cursor: pointer;
            transition: all 0.2s;
            border: none;
            background: none;
            font-size: 12px;
        }
        
        .nav-item.active {
            color: var(--primary);
        }
        
        .nav-icon {
            font-size: 24px;
        }
        
        .view {
            display: none;
            flex: 1;
            overflow-y: auto;
            padding: 0 20px 20px;
        }
        
        .view.active {
            display: block;
        }
        
        .connection-screen {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: var(--bg);
            z-index: 1000;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 40px;
            text-align: center;
        }
        
        .connection-logo {
            width: 120px;
            height: 120px;
            border-radius: 30px;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 60px;
            margin-bottom: 30px;
            box-shadow: 0 20px 40px rgba(0,210,255,0.3);
        }
        
        .connection-title {
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 10px;
        }
        
        .connection-subtitle {
            color: rgba(255,255,255,0.6);
            margin-bottom: 40px;
            font-size: 16px;
        }
        
        .connection-btn {
            width: 100%;
            max-width: 300px;
            padding: 18px;
            margin-bottom: 12px;
            border-radius: 14px;
            border: 1px solid rgba(255,255,255,0.1);
            background: var(--card);
            color: var(--text);
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            transition: all 0.2s;
        }
        
        .connection-btn.primary {
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            color: #000;
            border: none;
        }
        
        .connection-btn:active {
            transform: scale(0.98);
        }
        
        .qr-container {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: #000;
            z-index: 1001;
            flex-direction: column;
        }
        
        .qr-header {
            padding: 20px;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .qr-back {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: rgba(255,255,255,0.1);
            border: none;
            color: var(--text);
            font-size: 20px;
            cursor: pointer;
        }
        
        #qr-reader {
            flex: 1;
            width: 100% !important;
            border: none !important;
        }
        
        .toast {
            position: fixed;
            top: 100px;
            left: 50%;
            transform: translateX(-50%) translateY(-100px);
            background: rgba(0,0,0,0.9);
            color: var(--text);
            padding: 12px 24px;
            border-radius: 25px;
            font-size: 14px;
            font-weight: 500;
            z-index: 2000;
            opacity: 0;
            transition: all 0.3s;
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .toast.show {
            transform: translateX(-50%) translateY(0);
            opacity: 1;
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: rgba(255,255,255,0.5);
        }
        
        .empty-icon {
            font-size: 64px;
            margin-bottom: 20px;
            opacity: 0.5;
        }
        
        .empty-text {
            font-size: 16px;
        }
        
        .loading {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 40px;
        }
        
        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid rgba(255,255,255,0.1);
            border-top-color: var(--primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .theme-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }
        
        .theme-card {
            background: var(--card);
            border-radius: 16px;
            padding: 16px;
            cursor: pointer;
            border: 2px solid transparent;
            transition: all 0.2s;
        }
        
        .theme-card.active {
            border-color: var(--primary);
        }
        
        .theme-preview {
            height: 80px;
            border-radius: 12px;
            margin-bottom: 12px;
            background: linear-gradient(135deg, var(--gradient-start), var(--gradient-end));
        }
        
        .theme-name {
            font-weight: 600;
            font-size: 14px;
        }
        
        .output-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }
        
        .output-btn {
            background: var(--button);
            border: 2px solid transparent;
            border-radius: 12px;
            padding: 16px;
            color: var(--text);
            cursor: pointer;
            transition: all 0.2s;
            text-align: center;
        }
        
        .output-btn.active {
            border-color: var(--primary);
            background: rgba(0,210,255,0.1);
        }
        
        .output-btn.disabled {
            opacity: 0.4;
            cursor: not-allowed;
        }
        
        .output-icon {
            font-size: 24px;
            margin-bottom: 8px;
        }
        
        .output-label {
            font-size: 13px;
            font-weight: 600;
        }
        
        .output-sub {
            font-size: 11px;
            color: rgba(255,255,255,0.5);
            margin-top: 2px;
        }
        
        .toggle-switch {
            width: 50px;
            height: 28px;
            background: rgba(255,255,255,0.2);
            border-radius: 14px;
            position: relative;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .toggle-switch.active {
            background: var(--primary);
        }
        
        .toggle-switch::after {
            content: '';
            width: 24px;
            height: 24px;
            background: white;
            border-radius: 50%;
            position: absolute;
            top: 2px;
            left: 2px;
            transition: all 0.2s;
        }
        
        .toggle-switch.active::after {
            left: 24px;
        }
        
        /* YouTube specific styles */
        .youtube-item {
            background: var(--card);
            border-radius: 12px;
            padding: 12px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 12px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .youtube-item:active {
            transform: scale(0.98);
        }
        
        .youtube-thumb {
            width: 100px;
            height: 56px;
            border-radius: 8px;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            flex-shrink: 0;
            overflow: hidden;
        }
        
        .youtube-thumb img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .youtube-info {
            flex: 1;
            min-width: 0;
        }
        
        .youtube-title {
            font-weight: 600;
            font-size: 14px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-bottom: 4px;
        }
        
        .youtube-meta {
            font-size: 12px;
            color: rgba(255,255,255,0.5);
        }
        
        .search-container {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }
        
        .search-input {
            flex: 1;
        }
        
        .search-btn {
            width: 50px;
            height: 50px;
            border-radius: 12px;
            background: var(--primary);
            border: none;
            color: #000;
            font-size: 20px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        /* Remote access info */
        .remote-info {
            background: linear-gradient(135deg, rgba(0,210,255,0.1), rgba(157,80,187,0.1));
            border: 1px solid rgba(0,210,255,0.3);
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 15px;
            font-size: 13px;
        }
        
        .remote-info-title {
            font-weight: 700;
            color: var(--primary);
            margin-bottom: 8px;
        }
    </style>
</head>
<body>
    <div class="connection-screen" id="connection-screen">
        <div class="connection-logo">📻</div>
        <div class="connection-title">TC Radio</div>
        <div class="connection-subtitle">Connect to your Raspberry Pi radio</div>
        
        <div class="remote-info" style="width: 100%; max-width: 300px; margin-bottom: 20px; text-align: left;">
            <div class="remote-info-title">🌍 Remote Access Options:</div>
            <div style="color: rgba(255,255,255,0.8); line-height: 1.5;">
                • <b>Same WiFi:</b> Use local IP<br>
                • <b>Anywhere:</b> Install cloudflared<br>
                • <b>VPN:</b> Use Tailscale/ZeroTier
            </div>
        </div>
        
        <button class="connection-btn primary" onclick="startScan()">
            <span>📷</span> Scan QR Code
        </button>
        <button class="connection-btn" onclick="showManual()">
            <span>🔗</span> Enter URL Manually
        </button>
        
        <div id="manual-input" style="display: none; width: 100%; max-width: 300px; margin-top: 20px;">
            <input type="text" id="server-url" class="text-input" placeholder="http://192.168.1.100:8080" style="margin-bottom: 12px;">
            <button class="connection-btn primary" onclick="connectManual()">Connect</button>
            <button class="connection-btn" onclick="hideManual()" style="margin-top: 8px;">Cancel</button>
        </div>
    </div>
    
    <div class="qr-container" id="qr-container">
        <div class="qr-header">
            <button class="qr-back" onclick="stopScan()">←</button>
            <span style="font-size: 18px; font-weight: 600;">Scan QR Code</span>
        </div>
        <div id="qr-reader"></div>
    </div>
    
    <div class="app-container" id="app-container" style="display: none;">
        <div class="app-header">
            <div class="app-title">🎵 TC Radio</div>
            <div class="header-actions">
                <button class="icon-btn" onclick="refreshStatus()" title="Refresh">🔄</button>
                <button class="icon-btn" onclick="showThemeModal()" title="Theme">🎨</button>
            </div>
        </div>
        
        <div class="content" id="main-content">
            <div class="view active" id="view-home">
                <div class="player-card">
                    <div class="big-artwork" id="big-artwork">📻</div>
                    <div class="big-title" id="now-playing-title">Loading...</div>
                    <div class="big-subtitle" id="now-playing-subtitle">Select a station</div>
                    
                    <div class="controls-grid">
                        <button class="control-btn" onclick="sendCmd('prev')">
                            <span class="control-icon">⏮</span>
                            <span class="control-label">Prev</span>
                        </button>
                        <button class="control-btn primary" id="play-pause-btn" onclick="togglePlay()">
                            <span class="control-icon">▶</span>
                            <span class="control-label">Play</span>
                        </button>
                        <button class="control-btn" onclick="sendCmd('next')">
                            <span class="control-icon">⏭</span>
                            <span class="control-label">Next</span>
                        </button>
                    </div>
                    
                    <div class="volume-section">
                        <div class="volume-header">
                            <span>Volume</span>
                            <span id="volume-text">80%</span>
                        </div>
                        <div class="volume-slider" onclick="setVolume(event)">
                            <div class="volume-fill" id="volume-fill" style="width: 80%;">
                                <div class="volume-handle"></div>
                            </div>
                        </div>
                        <div class="quick-actions">
                            <button class="quick-btn" onclick="adjustVolume(-10)">🔉 -10</button>
                            <button class="quick-btn" onclick="adjustVolume(+10)">🔊 +10</button>
                        </div>
                    </div>
                </div>
                
                <div class="section-header">
                    <span class="section-title">Quick Timer</span>
                </div>
                <div class="card">
                    <div class="quick-actions">
                        <button class="quick-btn" onclick="startSleep(15)">😴 15m</button>
                        <button class="quick-btn" onclick="startSleep(30)">😴 30m</button>
                        <button class="quick-btn" onclick="startSleep(60)">😴 60m</button>
                        <button class="quick-btn danger" onclick="cancelSleep()">✕ Cancel</button>
                    </div>
                    <div id="sleep-status" style="text-align: center; margin-top: 12px; font-size: 14px; color: var(--primary);"></div>
                </div>
            </div>
            
            <div class="view" id="view-stations">
                <div class="section-header">
                    <span class="section-title">Radio Stations</span>
                    <span class="section-action">{{ stations|length }} stations</span>
                </div>
                <div class="station-grid" id="station-grid">
                    {% for s in stations %}
                    <div class="station-card {% if loop.index0 == current_idx %}active playing{% endif %}" data-idx="{{ loop.index0 }}" onclick="playStation({{ loop.index0 }})">
                        <div class="station-logo">
                            {% if s.logo_data_url %}
                            <img src="{{ s.logo_data_url }}" alt="{{ s.name }}">
                            {% else %}
                            {{ s.name[:2] }}
                            {% endif %}
                        </div>
                        <div class="station-name">{{ s.name }}</div>
                        <div class="station-genre">{{ s.genre or 'Radio' }}</div>
                    </div>
                    {% endfor %}
                </div>
            </div>
            
            <div class="view" id="view-youtube">
                <div class="section-header">
                    <span class="section-title">YouTube</span>
                </div>
                
                <div class="card">
                    <div class="search-container">
                        <input type="text" id="youtube-search" class="text-input search-input" placeholder="Search YouTube or paste URL...">
                        <button class="search-btn" onclick="searchYouTube()">🔍</button>
                    </div>
                    <div id="youtube-results"></div>
                </div>
                
                <div class="section-header">
                    <span class="section-title">Now Playing</span>
                </div>
                <div class="card" id="youtube-now-playing" style="display: none;">
                    <div class="youtube-item" style="margin-bottom: 0;">
                        <div class="youtube-thumb" id="yt-current-thumb">
                            <img src="" alt="" id="yt-current-img">
                        </div>
                        <div class="youtube-info">
                            <div class="youtube-title" id="yt-current-title">Not playing</div>
                            <div class="youtube-meta" id="yt-current-meta">-</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="view" id="view-links">
                <div class="section-header">
                    <span class="section-title">Direct Links</span>
                </div>
                
                <div class="card">
                    <div class="input-group">
                        <label class="input-label">Audio URL</label>
                        <input type="text" id="link-url" class="text-input" placeholder="https://example.com/audio.mp3">
                    </div>
                    <div class="input-group">
                        <label class="input-label">Title (optional)</label>
                        <input type="text" id="link-title" class="text-input" placeholder="My Audio File">
                    </div>
                    <button class="btn-primary" onclick="addLink()">➕ Add & Play</button>
                </div>
                
                <div class="section-header">
                    <span class="section-title">Saved Links</span>
                    <span class="section-action" onclick="clearAllLinks()" style="color: #ff6b6b;">Clear All</span>
                </div>
                <div id="links-list"></div>
            </div>
            
            <div class="view" id="view-alarm">
                <div class="section-header">
                    <span class="section-title">Alarm Clock</span>
                </div>
                
                <div class="card">
                    <div class="setting-row">
                        <span class="setting-label">Enable Alarm</span>
                        <div class="toggle-switch {% if alarm_settings.enabled %}active{% endif %}" id="alarm-toggle" onclick="toggleAlarm()"></div>
                    </div>
                    
                    <div class="input-group" style="margin-top: 15px;">
                        <label class="input-label">Alarm Time</label>
                        <input type="time" id="alarm-time" class="text-input" value="{{ alarm_settings.time }}" onchange="updateAlarmTime()">
                    </div>
                    
                    <div class="input-group">
                        <label class="input-label">Wake Up To</label>
                        <select id="alarm-station" class="select-input" onchange="updateAlarmStation()">
                            {% for s in stations %}
                            <option value="{{ loop.index0 }}" {% if loop.index0 == alarm_settings.station_idx %}selected{% endif %}>{{ s.name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    
                    <div class="input-group">
                        <label class="input-label">Repeat Days</label>
                        <div class="days-selector">
                            {% set days = ['M', 'T', 'W', 'T', 'F', 'S', 'S'] %}
                            {% for i in range(7) %}
                            <button class="day-btn {% if alarm_settings.days[i] %}active{% endif %}" data-day="{{ i }}" onclick="toggleAlarmDay({{ i }})">{{ days[i] }}</button>
                            {% endfor %}
                        </div>
                    </div>
                    
                    <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
                        <div class="setting-row">
                            <span class="setting-label">Start Volume</span>
                            <span class="setting-value" id="vol-start-val">{{ alarm_settings.volume_start }}%</span>
                        </div>
                        <input type="range" min="0" max="100" value="{{ alarm_settings.volume_start }}" class="text-input" style="margin-top: 8px;" onchange="updateAlarmVolStart(this.value)">
                        
                        <div class="setting-row" style="margin-top: 10px;">
                            <span class="setting-label">End Volume</span>
                            <span class="setting-value" id="vol-end-val">{{ alarm_settings.volume_end }}%</span>
                        </div>
                        <input type="range" min="0" max="100" value="{{ alarm_settings.volume_end }}" class="text-input" style="margin-top: 8px;" onchange="updateAlarmVolEnd(this.value)">
                        
                        <div class="setting-row" style="margin-top: 10px;">
                            <span class="setting-label">Fade Duration</span>
                            <span class="setting-value" id="fade-dur-val">{{ alarm_settings.fade_duration // 60 }} min</span>
                        </div>
                        <input type="range" min="1" max="30" value="{{ alarm_settings.fade_duration // 60 }}" class="text-input" style="margin-top: 8px;" onchange="updateAlarmFade(this.value)">
                    </div>
                </div>
            </div>
            
            <div class="view" id="view-audio">
                <div class="section-header">
                    <span class="section-title">Audio Output</span>
                </div>
                
                <div class="card">
                    <div class="output-grid">
                        <button class="output-btn {% if current_output == 'auto' %}active{% endif %}" id="out-auto" onclick="setOutput('auto')">
                            <div class="output-icon">🔄</div>
                            <div class="output-label">Auto</div>
                            <div class="output-sub">System Default</div>
                        </button>
                        <button class="output-btn {% if current_output == 'analog' %}active{% endif %} {% if not outputs.analog.available %}disabled{% endif %}" id="out-analog" onclick="setOutput('analog')">
                            <div class="output-icon">🎧</div>
                            <div class="output-label">3.5mm Jack</div>
                            <div class="output-sub">Headphones</div>
                        </button>
                        <button class="output-btn {% if current_output == 'hdmi' %}active{% endif %} {% if not outputs.hdmi.available %}disabled{% endif %}" id="out-hdmi" onclick="setOutput('hdmi')">
                            <div class="output-icon">📺</div>
                            <div class="output-label">HDMI</div>
                            <div class="output-sub">TV/Monitor</div>
                        </button>
                        <button class="output-btn {% if current_output == 'bluetooth' %}active{% endif %} {% if not outputs.bluetooth.available %}disabled{% endif %}" id="out-bluetooth" onclick="setOutput('bluetooth')">
                            <div class="output-icon">📡</div>
                            <div class="output-label">Bluetooth</div>
                            <div class="output-sub">Wireless</div>
                        </button>
                    </div>
                    
                    <button class="btn-primary" onclick="enableMultiOutput()" style="margin-top: 15px;">
                        🔊 Enable Multi-Output
                    </button>
                </div>
                
                <div class="section-header">
                    <span class="section-title">Remote Access</span>
                </div>
                <div class="card">
                    <div class="remote-info">
                        <div class="remote-info-title">🌍 Access From Anywhere</div>
                        <div style="color: rgba(255,255,255,0.8); line-height: 1.6; font-size: 13px;">
                            <b>Option 1 - Cloudflare (Free):</b><br>
                            1. Install: <code>wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm</code><br>
                            2. Run: <code>cloudflared tunnel --url http://localhost:8080</code><br>
                            3. Use the URL provided<br><br>
                            
                            <b>Option 2 - Tailscale (VPN):</b><br>
                            1. Install: <code>curl -fsSL https://tailscale.com/install.sh | sh</code><br>
                            2. Auth: <code>sudo tailscale up</code><br>
                            3. Use Tailscale IP from anywhere<br><br>
                            
                            <b>Option 3 - ngrok:</b><br>
                            1. Install: <code>sudo apt install ngrok</code><br>
                            2. Run: <code>ngrok http 8080</code><br>
                            3. Use the https URL provided
                        </div>
                    </div>
                </div>
                
                <div class="section-header">
                    <span class="section-title">Theme</span>
                </div>
                <div class="theme-grid" id="theme-grid">
                    {% for theme_key, theme_obj in all_themes.items() %}
                    <div class="theme-card {% if theme_key == current_theme_key %}active{% endif %}" onclick="setTheme('{{ theme_key }}')">
                        <div class="theme-preview" style="background: linear-gradient(135deg, {{ theme_obj.gradient_start }}, {{ theme_obj.gradient_end }});"></div>
                        <div class="theme-name">{{ theme_obj.name }}</div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
        
        <div class="now-playing-bar" id="np-bar" style="display: none;">
            <div class="np-artwork" id="np-artwork">📻</div>
            <div class="np-info">
                <div class="np-title" id="np-title">Not Playing</div>
                <div class="np-subtitle" id="np-subtitle">Select a station</div>
            </div>
            <div class="np-controls">
                <button class="np-btn" onclick="togglePlay()" id="np-play-btn">▶</button>
            </div>
        </div>
        
        <div class="bottom-nav">
            <button class="nav-item active" onclick="switchView('home')">
                <span class="nav-icon">🏠</span>
                <span>Home</span>
            </button>
            <button class="nav-item" onclick="switchView('stations')">
                <span class="nav-icon">📻</span>
                <span>Radio</span>
            </button>
            <button class="nav-item" onclick="switchView('youtube')">
                <span class="nav-icon">📺</span>
                <span>YouTube</span>
            </button>
            <button class="nav-item" onclick="switchView('links')">
                <span class="nav-icon">🔗</span>
                <span>Links</span>
            </button>
            <button class="nav-item" onclick="switchView('alarm')">
                <span class="nav-icon">⏰</span>
                <span>Alarm</span>
            </button>
        </div>
    </div>
    
    <div class="toast" id="toast"></div>
    
    <script>
        // Theme definitions for instant switching without reload
        const themes = {
            'true_black': { bg: '#000000', primary: '#00d2ff', secondary: '#9d50bb', accent: '#ffcc00', text: '#ffffff', card: 'rgba(20,20,20,0.95)', button: 'rgba(30,30,30,0.95)', buttonHover: 'rgba(50,50,50,0.95)', gradientStart: '#000000', gradientEnd: '#000000' },
            'midnight_black': { bg: '#0a0a0a', primary: '#00d2ff', secondary: '#9d50bb', accent: '#ffcc00', text: '#ffffff', card: 'rgba(20,20,20,0.95)', button: 'rgba(30,30,30,0.95)', buttonHover: 'rgba(50,50,50,0.95)', gradientStart: '#0a0a0a', gradientEnd: '#1a1a1a' },
            'pure_white': { bg: '#ffffff', primary: '#2c3e50', secondary: '#3498db', accent: '#e74c3c', text: '#2c3e50', card: 'rgba(240,240,240,0.95)', button: 'rgba(220,220,220,0.95)', buttonHover: 'rgba(200,200,200,0.95)', gradientStart: '#f8f9fa', gradientEnd: '#e9ecef' },
            'ocean_blue': { bg: '#0f3460', primary: '#00d2ff', secondary: '#1e90ff', accent: '#ff6b6b', text: '#ffffff', card: 'rgba(15,52,96,0.95)', button: 'rgba(20,60,100,0.95)', buttonHover: 'rgba(25,70,120,0.95)', gradientStart: '#0f3460', gradientEnd: '#16213e' },
            'sunset_orange': { bg: '#ff7e5f', primary: '#feb47b', secondary: '#ff6b6b', accent: '#2c3e50', text: '#ffffff', card: 'rgba(255,126,95,0.95)', button: 'rgba(255,140,100,0.95)', buttonHover: 'rgba(255,160,120,0.95)', gradientStart: '#ff7e5f', gradientEnd: '#feb47b' },
            'forest_green': { bg: '#1a472a', primary: '#2ecc71', secondary: '#27ae60', accent: '#f39c12', text: '#ffffff', card: 'rgba(26,71,42,0.95)', button: 'rgba(30,80,50,0.95)', buttonHover: 'rgba(40,100,60,0.95)', gradientStart: '#1a472a', gradientEnd: '#2d5a27' },
            'purple_haze': { bg: '#6a11cb', primary: '#2575fc', secondary: '#8a2be2', accent: '#ff416c', text: '#ffffff', card: 'rgba(106,17,203,0.95)', button: 'rgba(120,30,220,0.95)', buttonHover: 'rgba(140,50,240,0.95)', gradientStart: '#6a11cb', gradientEnd: '#2575fc' },
            'cyberpunk': { bg: '#0d0221', primary: '#ff00ff', secondary: '#00ffff', accent: '#ff6b00', text: '#ffffff', card: 'rgba(13,2,33,0.95)', button: 'rgba(30,5,60,0.95)', buttonHover: 'rgba(50,10,100,0.95)', gradientStart: '#0d0221', gradientEnd: '#2d00aa' },
            'golden_hour': { bg: '#f39c12', primary: '#e74c3c', secondary: '#d35400', accent: '#2c3e50', text: '#ffffff', card: 'rgba(243,156,18,0.95)', button: 'rgba(255,170,30,0.95)', buttonHover: 'rgba(255,190,50,0.95)', gradientStart: '#f39c12', gradientEnd: '#e74c3c' },
            'mint_fresh': { bg: '#00b894', primary: '#00cec9', secondary: '#81ecec', accent: '#fd79a8', text: '#2d3436', card: 'rgba(0,184,148,0.95)', button: 'rgba(0,200,160,0.95)', buttonHover: 'rgba(0,220,180,0.95)', gradientStart: '#00b894', gradientEnd: '#00cec9' },
            'crimson_red': { bg: '#c0392b', primary: '#e74c3c', secondary: '#ff7675', accent: '#fdcb6e', text: '#ffffff', card: 'rgba(192,57,43,0.95)', button: 'rgba(220,70,50,0.95)', buttonHover: 'rgba(240,90,70,0.95)', gradientStart: '#c0392b', gradientEnd: '#e74c3c' }
        };
        
        function applyTheme(themeKey) {
            const t = themes[themeKey] || themes['true_black'];
            const root = document.documentElement;
            root.style.setProperty('--bg', t.bg);
            root.style.setProperty('--primary', t.primary);
            root.style.setProperty('--secondary', t.secondary);
            root.style.setProperty('--accent', t.accent);
            root.style.setProperty('--text', t.text);
            root.style.setProperty('--card', t.card);
            root.style.setProperty('--button', t.button);
            root.style.setProperty('--button-hover', t.buttonHover);
            root.style.setProperty('--gradient-start', t.gradientStart);
            root.style.setProperty('--gradient-end', t.gradientEnd);
            localStorage.setItem('tc_radio_theme', themeKey);
            
            // Update active state in UI
            document.querySelectorAll('.theme-card').forEach(card => {
                card.classList.remove('active');
            });
            const activeCard = document.querySelector(`.theme-card[onclick*="'${themeKey}'"]`);
            if (activeCard) activeCard.classList.add('active');
        }
        
        // Load saved theme on start
        const savedTheme = localStorage.getItem('tc_radio_theme') || 'true_black';
        
        let apiBase = '';
        let currentStationIdx = {{ current_idx }};
        let isPlaying = false;
        let currentVolume = {{ vol_level }};
        let alarmEnabled = {{ alarm_settings.enabled|tojson }};
        let alarmDays = {{ alarm_settings.days|tojson }};
        let html5QrCode = null;
        let youtubeResults = [];
        
        function startScan() {
            document.getElementById('qr-container').style.display = 'flex';
            html5QrCode = new Html5Qrcode('qr-reader');
            html5QrCode.start(
                { facingMode: 'environment' },
                { fps: 10, qrbox: 250 },
                (decodedText) => {
                    stopScan();
                    connectTo(decodedText);
                },
                () => {}
            ).catch(err => {
                showToast('Camera error: ' + err);
            });
        }
        
        function stopScan() {
            if (html5QrCode) {
                html5QrCode.stop().then(() => {
                    html5QrCode = null;
                }).catch(() => {});
            }
            document.getElementById('qr-container').style.display = 'none';
        }
        
        function showManual() {
            document.getElementById('manual-input').style.display = 'block';
        }
        
        function hideManual() {
            document.getElementById('manual-input').style.display = 'none';
        }
        
        function connectManual() {
            const url = document.getElementById('server-url').value.trim();
            if (url) connectTo(url);
        }
        
        function connectTo(url) {
            if (!url.startsWith('http')) url = 'http://' + url;
            if (!url.includes(':8080')) url += ':8080';
            apiBase = url;
            localStorage.setItem('tc_radio_url', url);
            
            fetch(apiBase + '/api/nowplaying')
                .then(() => {
                    document.getElementById('connection-screen').style.display = 'none';
                    document.getElementById('app-container').style.display = 'flex';
                    document.getElementById('np-bar').style.display = 'flex';
                    applyTheme(savedTheme);
                    startPolling();
                    loadLinks();
                    showToast('Connected!');
                })
                .catch(() => {
                    showToast('Connection failed');
                });
        }
        
        function switchView(view) {
            document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            document.getElementById('view-' + view).classList.add('active');
            event.currentTarget.classList.add('active');
        }
        
        function sendCmd(cmd) {
            fetch(apiBase + '/api/' + cmd).then(() => refreshStatus());
        }
        
        function togglePlay() {
            sendCmd('toggle');
        }
        
        function playStation(idx) {
            fetch(apiBase + '/api/play/' + idx).then(() => {
                currentStationIdx = idx;
                refreshStatus();
                updateStationGrid();
                showToast('Playing station');
            });
        }
        
        function updateStationGrid() {
            document.querySelectorAll('.station-card').forEach((card, i) => {
                card.classList.remove('active', 'playing');
                if (i === currentStationIdx) {
                    card.classList.add('active', 'playing');
                }
            });
        }
        
        function adjustVolume(delta) {
            const newVol = Math.max(0, Math.min(100, currentVolume + delta));
            fetch(apiBase + '/api/volume/set/' + newVol).then(() => {
                currentVolume = newVol;
                updateVolumeUI();
            });
        }
        
        function setVolume(e) {
            const rect = e.currentTarget.getBoundingClientRect();
            const pct = (e.clientX - rect.left) / rect.width;
            const newVol = Math.round(pct * 100);
            fetch(apiBase + '/api/volume/set/' + newVol).then(() => {
                currentVolume = newVol;
                updateVolumeUI();
            });
        }
        
        function updateVolumeUI() {
            document.getElementById('volume-fill').style.width = currentVolume + '%';
            document.getElementById('volume-text').textContent = currentVolume + '%';
        }
        
        function startSleep(minutes) {
            fetch(apiBase + '/api/sleep/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({minutes: minutes})
            }).then(() => {
                showToast(`Sleep timer: ${minutes} min`);
                updateSleepStatus();
            });
        }
        
        function cancelSleep() {
            fetch(apiBase + '/api/sleep/cancel', {method: 'POST'}).then(() => {
                showToast('Sleep timer cancelled');
                updateSleepStatus();
            });
        }
        
        function updateSleepStatus() {
            fetch(apiBase + '/api/sleep/status').then(r => r.json()).then(data => {
                const el = document.getElementById('sleep-status');
                if (data.enabled) {
                    el.textContent = `⏰ Sleep: ${data.remaining} min remaining`;
                } else {
                    el.textContent = '';
                }
            });
        }
        
        // YouTube functions
        function searchYouTube() {
            const query = document.getElementById('youtube-search').value.trim();
            if (!query) {
                showToast('Please enter a search term');
                return;
            }
            
            const resultsDiv = document.getElementById('youtube-results');
            resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            
            fetch(apiBase + '/api/youtube/search', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({query: query})
            }).then(r => r.json()).then(data => {
                if (data.success) {
                    youtubeResults = data.results;
                    displayYouTubeResults(data.results);
                } else {
                    resultsDiv.innerHTML = '<div class="empty-state"><div class="empty-text">Error: ' + (data.error || 'Unknown error') + '</div></div>';
                }
            }).catch(err => {
                resultsDiv.innerHTML = '<div class="empty-state"><div class="empty-text">Search failed</div></div>';
            });
        }
        
        function displayYouTubeResults(results) {
            const container = document.getElementById('youtube-results');
            if (results.length === 0) {
                container.innerHTML = '<div class="empty-state"><div class="empty-icon">📺</div><div class="empty-text">No results found</div></div>';
                return;
            }
            
            container.innerHTML = results.map((video, idx) => `
                <div class="youtube-item" onclick="playYouTube(${idx})">
                    <div class="youtube-thumb">
                        <img src="${video.thumbnail || 'https://via.placeholder.com/100x56'}" alt="${escapeHtml(video.title)}">
                    </div>
                    <div class="youtube-info">
                        <div class="youtube-title">${escapeHtml(video.title)}</div>
                        <div class="youtube-meta">${escapeHtml(video.uploader)} • ${video.duration}</div>
                    </div>
                </div>
            `).join('');
        }
        
        function playYouTube(idx) {
            const video = youtubeResults[idx];
            if (!video) return;
            
            showToast('Loading YouTube audio...');
            
            fetch(apiBase + '/api/youtube/play', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({video_id: video.id, title: video.title})
            }).then(r => r.json()).then(data => {
                if (data.success) {
                    showToast('Now playing: ' + video.title.substring(0, 30) + '...');
                    document.getElementById('youtube-now-playing').style.display = 'block';
                    document.getElementById('yt-current-title').textContent = video.title;
                    document.getElementById('yt-current-meta').textContent = video.uploader + ' • ' + video.duration;
                    document.getElementById('yt-current-img').src = video.thumbnail || '';
                    refreshStatus();
                } else {
                    showToast('Error: ' + (data.error || 'Failed to play'));
                }
            }).catch(() => {
                showToast('Failed to play YouTube video');
            });
        }
        
        function addLink() {
            const url = document.getElementById('link-url').value.trim();
            const title = document.getElementById('link-title').value.trim();
            
            if (!url) {
                showToast('Please enter a URL');
                return;
            }
            
            fetch(apiBase + '/api/links/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url: url, title: title})
            }).then(r => r.json()).then(data => {
                if (data.success) {
                    showToast('Added and playing!');
                    document.getElementById('link-url').value = '';
                    document.getElementById('link-title').value = '';
                    loadLinks();
                    refreshStatus();
                } else {
                    showToast('Error: ' + data.error);
                }
            });
        }
        
        function loadLinks() {
            fetch(apiBase + '/api/links').then(r => r.json()).then(data => {
                const container = document.getElementById('links-list');
                if (data.links.length === 0) {
                    container.innerHTML = '<div class="empty-state"><div class="empty-icon">🔗</div><div class="empty-text">No saved links</div></div>';
                    return;
                }
                
                container.innerHTML = data.links.map(link => `
                    <div class="link-item" onclick="playLink(${link.id})">
                        <div class="link-icon">🎵</div>
                        <div class="link-info">
                            <div class="link-title">${escapeHtml(link.title)}</div>
                            <div class="link-url">${escapeHtml(link.url.substring(0, 50))}...</div>
                        </div>
                        <button class="link-delete" onclick="event.stopPropagation(); deleteLink(${link.id})">🗑</button>
                    </div>
                `).join('');
            });
        }
        
        function playLink(id) {
            fetch(apiBase + '/api/links/play/' + id, {method: 'POST'}).then(() => {
                showToast('Playing link');
                refreshStatus();
            });
        }
        
        function deleteLink(id) {
            fetch(apiBase + '/api/links/delete/' + id, {method: 'POST'}).then(() => {
                loadLinks();
                showToast('Link deleted');
            });
        }
        
        function clearAllLinks() {
            if (!confirm('Clear all saved links?')) return;
            fetch(apiBase + '/api/links/clear', {method: 'POST'}).then(() => {
                loadLinks();
                showToast('All links cleared');
            });
        }
        
        function setOutput(output) {
            fetch(apiBase + '/api/audio/output/' + output, {method: 'POST'}).then(() => {
                document.querySelectorAll('.output-btn').forEach(b => b.classList.remove('active'));
                document.getElementById('out-' + output).classList.add('active');
                showToast('Output: ' + output);
            });
        }
        
        function enableMultiOutput() {
            fetch(apiBase + '/api/audio/multi', {method: 'POST'}).then(() => {
                showToast('Multi-output enabled');
            });
        }
        
        function setTheme(themeName) {
            applyTheme(themeName);
            fetch(apiBase + '/api/theme/' + themeName).then(() => {
                showToast('Theme updated');
            });
        }
        
        function showThemeModal() {
            switchView('audio');
            document.querySelectorAll('.nav-item')[4].classList.add('active');
        }
        
        // Alarm functions
        function toggleAlarm() {
            alarmEnabled = !alarmEnabled;
            fetch(apiBase + '/api/alarm/toggle', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({enabled: alarmEnabled})
            }).then(() => {
                const toggle = document.getElementById('alarm-toggle');
                if (alarmEnabled) toggle.classList.add('active');
                else toggle.classList.remove('active');
                showToast(alarmEnabled ? 'Alarm enabled' : 'Alarm disabled');
            });
        }
        
        function updateAlarmTime() {
            const time = document.getElementById('alarm-time').value;
            fetch(apiBase + '/api/alarm/update', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({time: time, days: alarmDays})
            });
        }
        
        function updateAlarmStation() {
            const stationIdx = document.getElementById('alarm-station').value;
            fetch(apiBase + '/api/alarm/update', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({stationIdx: parseInt(stationIdx), days: alarmDays})
            });
        }
        
        function toggleAlarmDay(dayIndex) {
            alarmDays[dayIndex] = !alarmDays[dayIndex];
            const btn = document.querySelector(`.day-btn[data-day="${dayIndex}"]`);
            if (alarmDays[dayIndex]) btn.classList.add('active');
            else btn.classList.remove('active');
            
            fetch(apiBase + '/api/alarm/update', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({days: alarmDays})
            });
        }
        
        function updateAlarmVolStart(val) {
            document.getElementById('vol-start-val').textContent = val + '%';
            fetch(apiBase + '/api/alarm/update', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({volumeStart: parseInt(val), days: alarmDays})
            });
        }
        
        function updateAlarmVolEnd(val) {
            document.getElementById('vol-end-val').textContent = val + '%';
            fetch(apiBase + '/api/alarm/update', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({volumeEnd: parseInt(val), days: alarmDays})
            });
        }
        
        function updateAlarmFade(val) {
            document.getElementById('fade-dur-val').textContent = val + ' min';
            fetch(apiBase + '/api/alarm/update', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({fadeDuration: parseInt(val) * 60, days: alarmDays})
            });
        }
        
        function refreshStatus() {
            fetch(apiBase + '/api/nowplaying').then(r => r.json()).then(data => {
                const text = data.text || 'Unknown';
                document.getElementById('now-playing-title').textContent = text;
                document.getElementById('np-title').textContent = text;
                document.getElementById('big-artwork').textContent = text.substring(0, 2).toUpperCase();
                document.getElementById('np-artwork').textContent = text.substring(0, 2).toUpperCase();
            });
            
            fetch(apiBase + '/api/status').then(r => r.json()).then(data => {
                isPlaying = data.playing;
                currentVolume = data.volume;
                currentStationIdx = data.station;
                updateVolumeUI();
                updateStationGrid();
                
                const playBtn = document.getElementById('play-pause-btn');
                const npPlayBtn = document.getElementById('np-play-btn');
                if (isPlaying) {
                    playBtn.innerHTML = '<span class="control-icon">⏸</span><span class="control-label">Pause</span>';
                    npPlayBtn.textContent = '⏸';
                } else {
                    playBtn.innerHTML = '<span class="control-icon">▶</span><span class="control-label">Play</span>';
                    npPlayBtn.textContent = '▶';
                }
            });
        }
        
        function startPolling() {
            refreshStatus();
            setInterval(refreshStatus, 2000);
            setInterval(updateSleepStatus, 10000);
        }
        
        function showToast(msg) {
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3000);
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Auto-connect if URL saved
        const savedUrl = localStorage.getItem('tc_radio_url');
        if (savedUrl) {
            document.getElementById('server-url').value = savedUrl;
            connectTo(savedUrl);
        }
        
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js').catch(() => {});
        }
        
        // Enter key for YouTube search
        document.getElementById('youtube-search')?.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') searchYouTube();
        });
    </script>
</body>
</html>
"""

logo_cache = {}

def get_logo_data_url(logo_url, station_name):
    if not logo_url:
        return None
    cache_key = f"{logo_url}_{station_name}"
    if cache_key in logo_cache:
        return logo_cache[cache_key]
    try:
        if logo_url.startswith('data:image'):
            return logo_url
        response = requests.get(logo_url, timeout=3)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', 'image/png')
            if 'image' in content_type:
                base64_data = base64.b64encode(response.content).decode('utf-8')
                data_url = f"data:{content_type};base64,{base64_data}"
                logo_cache[cache_key] = data_url
                return data_url
    except:
        pass
    return None

@app.route('/')
def home():
    global meta_text, stations, current_theme, THEMES, alarm_system, current_idx, vol_level, audio_manager
    
    stations_with_logos = []
    for station in stations:
        s = station.copy()
        s['logo_data_url'] = get_logo_data_url(s.get('logo', ''), s['name'])
        stations_with_logos.append(s)
    
    try:
        current_theme_key = next(k for k, t in THEMES.items() if t.name == current_theme.name)
    except:
        current_theme_key = 'true_black'
    
    alarm_settings = {
        'enabled': alarm_system.alarm_enabled,
        'time': alarm_system.alarm_time,
        'station_idx': alarm_system.alarm_station_idx,
        'volume_start': alarm_system.alarm_volume_start,
        'volume_end': alarm_system.alarm_volume_end,
        'fade_duration': alarm_system.alarm_fade_duration,
        'days': alarm_system.alarm_days
    }
    
    sleep_timer_settings = {
        'enabled': alarm_system.sleep_timer_enabled,
        'duration': alarm_system.sleep_duration,
        'remaining': alarm_system.get_sleep_remaining(),
        'volume_fade': alarm_system.sleep_volume_fade,
        'stop_method': alarm_system.sleep_stop_method
    }
    
    outputs_data = {}
    for key, val in audio_manager.outputs.items():
        outputs_data[key] = {
            'available': val['available'],
            'name': val['name']
        }
    
    return render_template_string(
        HTML_TEMPLATE,
        stations=stations_with_logos,
        ip_address=current_ip,
        vol_level=vol_level,
        current_idx=current_idx,
        now_playing=meta_text if meta_text else stations[current_idx]['name'],
        theme=current_theme,
        current_theme_key=current_theme_key,
        all_themes=THEMES,
        alarm_settings=alarm_settings,
        sleep_timer_settings=sleep_timer_settings,
        outputs=outputs_data,
        current_output=audio_manager.current_output
    )

@app.route('/manifest.json')
def manifest():
    return Response(json.dumps({
        "short_name": "TC Radio",
        "name": "TC Radio Remote",
        "icons": [{
            "src": "https://cdn-icons-png.flaticon.com/512/3011/3011244.png",
            "sizes": "512x512",
            "type": "image/png"
        }],
        "start_url": "/",
        "display": "standalone",
        "theme_color": current_theme.background,
        "background_color": current_theme.background
    }), mimetype='application/json')

@app.route('/sw.js')
def sw():
    return Response("""
    self.addEventListener('install', e => e.waitUntil(self.skipWaiting()));
    self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
    self.addEventListener('fetch', e => e.respondWith(fetch(e.request)));
    """, mimetype='application/javascript')

@app.route('/api/<action>')
def remote_action(action):
    global current_idx, vol_level
    try:
        if action == 'next':
            current_idx = (current_idx + 1) % len(stations)
            play()
        elif action == 'prev':
            current_idx = (current_idx - 1) % len(stations)
            play()
        elif action == 'volup':
            vol_level = min(vol_level + 10, 100)
            player.audio_set_volume(vol_level)
            audio_manager.set_volume(vol_level)
        elif action == 'voldown':
            vol_level = max(vol_level - 10, 0)
            player.audio_set_volume(vol_level)
            audio_manager.set_volume(vol_level)
        elif action == 'toggle':
            player.pause()
        elif action == 'mute':
            vol_level = 0 if vol_level > 0 else 80
            player.audio_set_volume(vol_level)
            audio_manager.set_volume(vol_level)
        return "OK"
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/api/play/<int:idx>')
def play_index(idx):
    global current_idx
    try:
        current_idx = idx % len(stations)
        play()
        return "OK"
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/api/volume/set/<int:level>')
def set_volume_level(level):
    global vol_level
    try:
        vol_level = max(0, min(100, level))
        player.audio_set_volume(vol_level)
        audio_manager.set_volume(vol_level)
        return jsonify({"volume": vol_level})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/theme/<theme_name>')
def set_theme(theme_name):
    global current_theme, CYAN, PURPLE, GOLD, WHITE, BACKGROUND
    if theme_name in THEMES:
        current_theme = THEMES[theme_name]
        save_theme(theme_name)
        CYAN = current_theme.pygame_primary
        PURPLE = current_theme.pygame_secondary
        GOLD = current_theme.pygame_accent
        WHITE = current_theme.pygame_text
        BACKGROUND = current_theme.pygame_background
        return "OK"
    return "Theme not found", 404

@app.route('/api/volume')
def get_volume():
    return jsonify({"volume": vol_level})

@app.route('/api/nowplaying')
def get_now_playing():
    return jsonify({"text": meta_text if meta_text else stations[current_idx]['name']})

@app.route('/api/status')
def get_status():
    try:
        is_playing = player.get_state() == vlc.State.Playing
    except:
        is_playing = False
    return jsonify({
        "playing": is_playing,
        "volume": vol_level,
        "station": current_idx
    })

@app.route('/api/stations')
def get_stations():
    return jsonify(stations)

# Direct Links API
@app.route('/api/links', methods=['GET'])
def get_links():
    return jsonify({"links": direct_links.get_links()})

@app.route('/api/links/add', methods=['POST'])
def add_link():
    global current_idx
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        title = data.get('title', '').strip()
        
        success, result = direct_links.add_link(url, title)
        if success:
            # Add to stations and play
            station = {
                'name': result['title'],
                'url': result['url'],
                'genre': result['type'],
                'logo': '',
                'direct_link_id': result['id']
            }
            stations.append(station)
            current_idx = len(stations) - 1
            play()
            return jsonify({"success": True, "link": result})
        else:
            return jsonify({"success": False, "error": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/links/play/<int:link_id>', methods=['POST'])
def play_link(link_id):
    global current_idx
    try:
        links = direct_links.get_links()
        link = next((l for l in links if l['id'] == link_id), None)
        if link:
            # Check if already in stations
            for i, s in enumerate(stations):
                if s.get('direct_link_id') == link_id:
                    current_idx = i
                    play()
                    return jsonify({"success": True})
            
            # Add new
            station = {
                'name': link['title'],
                'url': link['url'],
                'genre': link['type'],
                'logo': '',
                'direct_link_id': link_id
            }
            stations.append(station)
            current_idx = len(stations) - 1
            play()
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Link not found"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/links/delete/<int:link_id>', methods=['POST'])
def delete_link(link_id):
    try:
        direct_links.remove_link(link_id)
        # Remove from stations if present
        global stations, current_idx
        for i, s in enumerate(stations[:]):
            if s.get('direct_link_id') == link_id:
                stations.pop(i)
                if current_idx >= i:
                    current_idx = max(0, current_idx - 1)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/links/clear', methods=['POST'])
def clear_links():
    try:
        global stations, current_idx
        # Remove all direct link stations
        stations = [s for s in stations if not s.get('direct_link_id')]
        current_idx = 0
        direct_links.links = []
        direct_links.save_links()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/speak', methods=['POST'])
def remote_speak():
    try:
        data = request.get_json()
        text = data.get('text', '')
        if text:
            def run_speak():
                orig_vol = vol_level
                player.audio_set_volume(int(orig_vol * 0.3))
                os.system(f'espeak -v en-uk "{text}"')
                player.audio_set_volume(orig_vol)
            threading.Thread(target=run_speak).start()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/alarm/toggle', methods=['POST'])
def toggle_alarm():
    try:
        data = request.get_json()
        alarm_system.alarm_enabled = data.get('enabled', not alarm_system.alarm_enabled)
        alarm_system.save_alarm_settings()
        return jsonify({'success': True, 'enabled': alarm_system.alarm_enabled})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/alarm/update', methods=['POST'])
def update_alarm():
    try:
        data = request.get_json()
        alarm_system.alarm_time = data.get('time', alarm_system.alarm_time)
        alarm_system.alarm_station_idx = data.get('stationIdx', alarm_system.alarm_station_idx)
        alarm_system.alarm_volume_start = data.get('volumeStart', alarm_system.alarm_volume_start)
        alarm_system.alarm_volume_end = data.get('volumeEnd', alarm_system.alarm_volume_end)
        alarm_system.alarm_fade_duration = data.get('fadeDuration', alarm_system.alarm_fade_duration)
        alarm_system.alarm_days = data.get('days', alarm_system.alarm_days)
        alarm_system.save_alarm_settings()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sleep/start', methods=['POST'])
def start_sleep():
    try:
        data = request.get_json()
        minutes = data.get('minutes', 30)
        alarm_system.start_sleep_timer(minutes)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sleep/cancel', methods=['POST'])
def cancel_sleep():
    try:
        alarm_system.stop_sleep_timer()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sleep/status')
def sleep_status():
    return jsonify({
        'enabled': alarm_system.sleep_timer_enabled,
        'remaining': alarm_system.get_sleep_remaining()
    })

# Audio Output API Routes
@app.route('/api/audio/output/<output_name>', methods=['POST'])
def set_audio_output(output_name):
    try:
        success = audio_manager.set_output(output_name)
        if success:
            return jsonify({'success': True, 'output': output_name})
        else:
            return jsonify({'success': False, 'error': 'Failed to set output'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/audio/multi', methods=['POST'])
def enable_multi_audio():
    try:
        available = [k for k, v in audio_manager.outputs.items() if v['available'] and k != 'auto']
        if len(available) >= 2:
            success = audio_manager.enable_multi_output(available)
            return jsonify({'success': success})
        else:
            return jsonify({'success': False, 'error': 'Need at least 2 audio devices'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/audio/scan', methods=['POST'])
def scan_audio():
    try:
        audio_manager.scan_outputs()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# YouTube API Routes
@app.route('/api/youtube/search', methods=['POST'])
def youtube_search():
    global youtube_results_cache
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        if not query:
            return jsonify({'success': False, 'error': 'Empty query'})
        
        # Check if it's a URL
        if 'youtube.com' in query or 'youtu.be' in query:
            # Extract video ID from URL
            video_id = None
            if 'v=' in query:
                video_id = query.split('v=')[1].split('&')[0]
            elif 'youtu.be/' in query:
                video_id = query.split('youtu.be/')[1].split('?')[0]
            
            if video_id:
                # Get video info
                cmd = ['yt-dlp', '--dump-json', '--no-playlist', f'https://youtube.com/watch?v={video_id}']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.stdout:
                    video = json.loads(result.stdout.strip().split('\n')[0])
                    return jsonify({
                        'success': True,
                        'results': [{
                            'id': video.get('id', video_id),
                            'title': video.get('title', 'Unknown'),
                            'uploader': video.get('uploader', 'Unknown'),
                            'duration': video.get('duration_string', '0:00'),
                            'thumbnail': video.get('thumbnail', f'https://img.youtube.com/vi/{video_id}/mqdefault.jpg')
                        }]
                    })
        
        # Regular search
        cmd = ['yt-dlp', '--dump-json', '--no-playlist', f'ytsearch8:{query}', '--extract-audio', '--audio-format', 'mp3']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        videos = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    video = json.loads(line)
                    videos.append({
                        'id': video.get('id', ''),
                        'title': video.get('title', 'Unknown'),
                        'uploader': video.get('uploader', 'Unknown'),
                        'duration': video.get('duration_string', '0:00'),
                        'thumbnail': video.get('thumbnail', '')
                    })
                except:
                    continue
        
        youtube_results_cache = videos
        return jsonify({'success': True, 'results': videos})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/youtube/play', methods=['POST'])
def youtube_play():
    global current_idx
    try:
        data = request.get_json()
        video_id = data.get('video_id', '')
        title = data.get('title', 'YouTube Audio')
        
        if not video_id:
            return jsonify({'success': False, 'error': 'No video ID'})
        
        cmd = ['yt-dlp', '-f', 'bestaudio', '--get-url', f'https://youtube.com/watch?v={video_id}']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        audio_url = result.stdout.strip()
        
        if audio_url and audio_url.startswith('http'):
            youtube_station = {
                'name': f'YT: {title[:40]}',
                'url': audio_url,
                'genre': 'YouTube',
                'logo': f'https://img.youtube.com/vi/{video_id}/mqdefault.jpg',
                'youtube_id': video_id
            }
            stations.append(youtube_station)
            current_idx = len(stations) - 1
            play()
            return jsonify({'success': True, 'message': f'Playing: {title}'})
        else:
            return jsonify({'success': False, 'error': 'Could not extract audio URL'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/static/<path:filename>')
def serve_static(filename):
    if filename == 'radio.png' and PIL_AVAILABLE:
        try:
            img = Image.new('RGBA', (100, 100), (0,0,0,0))
            draw = ImageDraw.Draw(img)
            rgb = current_theme.pygame_primary
            draw.ellipse([10,10,90,90], fill=rgb)
            draw.ellipse([20,20,80,80], fill=(0,0,0,255))
            draw.ellipse([30,30,70,70], fill=rgb)
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            return Response(img_bytes.getvalue(), mimetype='image/png')
        except:
            return Response(b'', mimetype='image/png')
    return "Not found", 404

def run_flask():
    try:
        app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False, threaded=True)
    except:
        try:
            app.run(host='0.0.0.0', port=8081, debug=False, use_reloader=False, threaded=True)
        except:
            pass

threading.Thread(target=run_flask, daemon=True).start()

# --- PYGAME SETUP ---
os.environ['DISPLAY'] = ':0'
pygame.init()

# --- UNICODE FONT SETUP (Tamil Support) ---
def get_unicode_font(size, bold=False):
    """Load font with Unicode/Tamil support"""
    font_paths = [
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
        '/usr/share/fonts/truetype/noto/NotoSansTamil-Regular.ttf',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc',
        '/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf',
        '/usr/share/fonts/truetype/noto/NotoSansTamil-Bold.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
    ]
    
    if bold:
        font_paths = [p for p in font_paths if 'Bold' in p] + font_paths
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                return pygame.font.Font(font_path, size)
            except:
                continue
    
    return pygame.font.Font(None, size)

# Load Unicode fonts
try:
    f_lg = get_unicode_font(24, bold=True)
    f_sm = get_unicode_font(16, bold=True)
    f_xl = get_unicode_font(80, bold=True)
    f_med = get_unicode_font(24, bold=True)
    f_tiny = get_unicode_font(12, bold=True)
    print("Unicode fonts loaded successfully")
except Exception as e:
    print(f"Font error: {e}, using defaults")
    f_lg = pygame.font.Font(None, 24)
    f_sm = pygame.font.Font(None, 16)
    f_xl = pygame.font.Font(None, 80)
    f_med = pygame.font.Font(None, 24)
    f_tiny = pygame.font.Font(None, 12)

try:
    screen = pygame.display.set_mode((320, 480), pygame.FULLSCREEN | pygame.NOFRAME)
except:
    screen = pygame.display.set_mode((320, 480))

instance = vlc.Instance('--no-video')
player = instance.media_player_new()

URL = "https://raw.githubusercontent.com/simsonpeter/Tcradios/refs/heads/main/stations.json"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast?latitude=50.83&longitude=-0.17&current_weather=true"
LAST_STATION_FILE = "/home/raspberry/.last_station"

try:
    stations = requests.get(URL, timeout=5).json()
    print(f"Loaded {len(stations)} stations")
except:
    stations = [
        {"name": "BBC Radio 1", "url": "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_one", "genre": "Pop"},
        {"name": "BBC Radio 2", "url": "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_two", "genre": "Adult Contemporary"},
        {"name": "Classic FM", "url": "http://media-ice.musicradio.com/ClassicFMMP3", "genre": "Classical"},
    ]

current_idx = 0
if os.path.exists(LAST_STATION_FILE):
    try:
        with open(LAST_STATION_FILE, "r") as f:
            saved = int(f.read())
            if 0 <= saved < len(stations):
                current_idx = saved
    except:
        pass

vol_level = 80
last_weather_update = 0
saver_mode = False
show_qr = False
weather_str = "HOVE: --C"
current_temp = 0
weather_type = "clear"
meta_text = ""
scroll_x = 320
saver_scroll_x = 320
alarm_fade_active = False
alarm_fade_data = {}
saver_active = False

# Logo setup
logo = pygame.Surface((140, 140), pygame.SRCALPHA)
logo.fill((0, 0, 0, 0))
pygame.draw.circle(logo, (40, 40, 40), (70, 70), 70)
pygame.draw.circle(logo, CYAN, (70, 70), 70, 2)
initials = stations[current_idx]['name'][:2].upper()
text = f_lg.render(initials, True, CYAN)
text_rect = text.get_rect(center=(70, 70))
logo.blit(text, text_rect)

try:
    qr_img = qrcode.make(f"http://{current_ip}:8080").convert('RGB')
    qr_surface = pygame.image.fromstring(qr_img.tobytes(), qr_img.size, 'RGB')
    qr_surface = pygame.transform.scale(qr_surface, (240, 240))
except:
    qr_surface = pygame.Surface((240, 240))
    qr_surface.fill((0, 0, 0))

last_ip_check = time.time()

def update_qr_code():
    global qr_surface, current_ip, last_ip_check
    now = time.time()
    if now - last_ip_check > 30:
        new_ip = get_local_ip()
        if new_ip != current_ip:
            current_ip = new_ip
            try:
                qr_img = qrcode.make(f"http://{current_ip}:8080").convert('RGB')
                qr_surface = pygame.image.fromstring(qr_img.tobytes(), qr_img.size, 'RGB')
                qr_surface = pygame.transform.scale(qr_surface, (240, 240))
            except:
                pass
        last_ip_check = now

def update_logo(url):
    global logo
    try:
        if not url:
            raise ValueError("No logo URL")
        raw = urlopen(url, timeout=2).read()
        img = pygame.image.load(io.BytesIO(raw)).convert_alpha()
        img = pygame.transform.scale(img, (140, 140))
        
        mask = pygame.Surface((140, 140), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 0))
        pygame.draw.circle(mask, (255, 255, 255, 255), (70, 70), 70)
        
        circular_logo = pygame.Surface((140, 140), pygame.SRCALPHA)
        circular_logo.blit(img, (0, 0))
        circular_logo.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        pygame.draw.circle(circular_logo, CYAN, (70, 70), 70, 2)
        logo = circular_logo
    except Exception as e:
        logo = pygame.Surface((140, 140), pygame.SRCALPHA)
        logo.fill((0, 0, 0, 0))
        pygame.draw.circle(logo, (40, 40, 40), (70, 70), 70)
        pygame.draw.circle(logo, CYAN, (70, 70), 70, 2)
        if stations[current_idx]['name']:
            initials = stations[current_idx]['name'][:2].upper()
            text = f_lg.render(initials, True, CYAN)
            text_rect = text.get_rect(center=(70, 70))
            logo.blit(text, text_rect)

def sanitize_text(text):
    """Clean text for display - keeps Unicode characters including Tamil"""
    if not text:
        return "Unknown"
    text = str(text)
    # Remove control characters except newline
    text = ''.join(char for char in text if ord(char) >= 32 or char == '\n')
    return text.strip()

def play():
    global meta_text, scroll_x, saver_scroll_x
    scroll_x = 320
    saver_scroll_x = 320
    station = stations[current_idx]
    try:
        player.set_media(instance.media_new(station['url']))
        player.play()
        player.audio_set_volume(vol_level)
        update_logo(station.get('logo', ''))
        with open(LAST_STATION_FILE, "w") as f:
            f.write(str(current_idx))
    except:
        pass

play()
ip_display_time = time.time() + 10
show_startup_ip = True

def handle_alarm_fade():
    global vol_level, alarm_fade_active, alarm_fade_data, current_idx
    if not alarm_fade_active or not alarm_fade_data:
        return
    now = time.time()
    elapsed = now - alarm_fade_data['start_time']
    if elapsed < alarm_fade_data['duration']:
        progress = elapsed / alarm_fade_data['duration']
        current_vol = int(alarm_fade_data['start_volume'] + alarm_fade_data['volume_range'] * progress)
        vol_level = current_vol
        player.audio_set_volume(vol_level)
        if current_idx != alarm_fade_data['alarm_station_idx']:
            current_idx = alarm_fade_data['alarm_station_idx']
            play()
    else:
        vol_level = alarm_fade_data['end_volume']
        player.audio_set_volume(vol_level)
        alarm_fade_active = False
        alarm_fade_data = {}

def handle_sleep_timer():
    if alarm_system.check_sleep_timer():
        if alarm_system.sleep_volume_fade:
            for i in range(10, 0, -1):
                player.audio_set_volume(vol_level * i // 10)
                time.sleep(0.5)
        if alarm_system.sleep_stop_method == "pause":
            player.pause()
        elif alarm_system.sleep_stop_method == "stop":
            player.stop()

def draw_weather_icon(surface, x, y, type):
    if type == "clear":
        pygame.draw.circle(surface, GOLD, (x, y), 15)
        for i in range(8):
            angle = i * (math.pi / 4)
            x2 = x + math.cos(angle) * 22
            y2 = y + math.sin(angle) * 22
            pygame.draw.line(surface, GOLD, (x, y), (x2, y2), 2)
    elif type == "cloud":
        pygame.draw.circle(surface, GRAY, (x-8, y+5), 10)
        pygame.draw.circle(surface, WHITE, (x, y), 12)
        pygame.draw.circle(surface, GRAY, (x+8, y+5), 10)
    elif type == "rain":
        pygame.draw.circle(surface, (70,70,70), (x, y), 12)
        for i in range(3):
            rx = x - 10 + (i * 10)
            pygame.draw.line(surface, CYAN, (rx, y+15), (rx-2, y+22), 2)

def draw_screensaver():
    global saver_scroll_x
    # COMPLETELY BLACK BACKGROUND - no brightness
    screen.fill((0, 0, 0))
    
    # Dim the time display (not too bright)
    time_now = datetime.now().strftime("%H:%M")
    # Use darker gray for time (not pure white)
    time_surf = f_xl.render(time_now, True, (100, 100, 100))
    time_rect = time_surf.get_rect(center=(160, 150))
    screen.blit(time_surf, time_rect)
    
    # Scrolling station name - dim cyan
    station_name = f"RADIO: {sanitize_text(stations[current_idx]['name']).upper()}"
    # Darker cyan for less brightness
    station_surf = f_med.render(station_name, True, (0, 100, 100))
    
    saver_scroll_x -= 1  # Slower scroll
    if saver_scroll_x < -station_surf.get_width():
        saver_scroll_x = 320
    screen.blit(station_surf, (saver_scroll_x, 250))
    
    y_pos = 320
    if alarm_system.sleep_timer_enabled:
        remaining = alarm_system.get_sleep_remaining()
        # Dark green/red
        sleep_color = (0, 80, 0) if remaining > 10 else (80, 0, 0)
        sleep_text = f_tiny.render(f"Sleep: {remaining} min", True, sleep_color)
        screen.blit(sleep_text, (160 - sleep_text.get_width()//2, y_pos))
        y_pos += 25
    
    if alarm_system.alarm_enabled:
        # Dark gold
        alarm_text = f_tiny.render(f"ALARM {alarm_system.alarm_time}", True, (100, 80, 0))
        screen.blit(alarm_text, (160 - alarm_text.get_width()//2, y_pos))
        y_pos += 20
    
    # Weather - dim
    draw_weather_icon(screen, 160, y_pos + 10, weather_type)
    temp_surf = f_sm.render(f"{current_temp}°C", True, (80, 80, 80))
    screen.blit(temp_surf, (160 - temp_surf.get_width()//2, y_pos + 30))
    
    # Volume - very dim
    vol_surf = f_sm.render(f"Vol: {vol_level}%", True, (60, 60, 60))
    screen.blit(vol_surf, (160 - vol_surf.get_width()//2, 420))
    
    # Exit hint - very dim
    hint_surf = f_tiny.render("Tap to exit", True, (40, 40, 40))
    screen.blit(hint_surf, (160 - hint_surf.get_width()//2, 460))

adjusting_volume = False
show_volume_bar = False
volume_bar_timer = 0
touch_start_pos = (0,0)
touch_start_time = 0

while True:
    now = time.time()
    update_qr_code()
    
    if alarm_system.check_alarm() and not alarm_fade_active:
        alarm_fade_data = alarm_system.trigger_alarm(player, stations, current_idx, vol_level)
        alarm_fade_active = True
    
    handle_alarm_fade()
    handle_sleep_timer()
    
    if now - last_weather_update > 1200:
        try:
            r = requests.get(WEATHER_URL, timeout=5)
            if r.status_code == 200:
                data = r.json()['current_weather']
                current_temp = int(data['temperature'])
                code = data['weathercode']
                if code == 0: weather_type = "clear"
                elif code < 50: weather_type = "cloud"
                else: weather_type = "rain"
        except: pass
        last_weather_update = now
    
    try:
        media = player.get_media()
        if media:
            try:
                m = media.get_meta(vlc.Meta.NowPlaying)
                if m:
                    meta_text = sanitize_text(m).upper()
                else:
                    meta_text = sanitize_text(stations[current_idx]['name']).upper()
            except: 
                meta_text = sanitize_text(stations[current_idx]['name']).upper()
    except: 
        meta_text = sanitize_text(stations[current_idx]['name']).upper()
    
    if show_volume_bar and now - volume_bar_timer > 3:
        show_volume_bar = False
        adjusting_volume = False
    
    if saver_active:
        pygame.mouse.set_visible(False)
        draw_screensaver()
    else:
        pygame.mouse.set_visible(True)
        screen.fill(BLACK)
        pygame.draw.rect(screen, CYAN, (0, 0, 320, 60))
        screen.blit(f_lg.render("TC RADIO", True, BLACK), (100, 15))
        
        if show_startup_ip and now < ip_display_time:
            screen.blit(f_sm.render(f"IP: {current_ip}:8080", True, GOLD), (180, 20))
        
        btn_qr = pygame.draw.rect(screen, (30,30,30), (10,10,45,40), border_radius=5)
        screen.blit(f_sm.render("QR", True, CYAN), (22,22))
        
        btn_exit = pygame.draw.rect(screen, RED, (275,10,40,40), border_radius=8)
        pygame.draw.line(screen, WHITE, (285,20), (305,40), 4)
        pygame.draw.line(screen, WHITE, (305,20), (285,40), 4)
        
        try: is_playing = player.get_state() == vlc.State.Playing
        except: is_playing = False
        
        logo_rect = pygame.Rect(90, 95, 140, 140)
        screen.blit(logo, (90, 95))
        
        if is_playing:
            pulse = (math.sin(time.time() * 3) + 1) / 2
            pulse_color = (int(CYAN[0] * 0.7), int(CYAN[1] * 0.7), int(CYAN[2] * 0.7))
            pygame.draw.circle(screen, pulse_color, (160, 165), 75 + int(pulse * 5), 2)
        else:
            pygame.draw.circle(screen, GRAY, (160, 165), 75, 2)
        
        # Display text with Unicode support (Tamil will show correctly)
        display_text = sanitize_text(meta_text)
        name_render = f_lg.render(display_text, True, CYAN)
        scroll_x -= 2
        if scroll_x < -name_render.get_width():
            scroll_x = 320
        screen.blit(name_render, (scroll_x, 248))
        
        # Alarm / sleep row — below now-playing scroll, above volume strip
        alarm_sleep_y = 278
        if alarm_system.alarm_enabled:
            screen.blit(f_tiny.render(f"ALARM {alarm_system.alarm_time}", True, GOLD), (10, alarm_sleep_y))
        if alarm_system.sleep_timer_enabled:
            rem = alarm_system.get_sleep_remaining()
            sleep_text = f_tiny.render(f"SLEEP {rem}min", True, GREEN if rem > 5 else RED)
            screen.blit(sleep_text, (310 - sleep_text.get_width(), alarm_sleep_y))

        # Hit targets under alarm row; middle stays visually empty until slider shows briefly
        vol_minus_rect = pygame.Rect(10, 296, 44, 34)
        vol_plus_rect = pygame.Rect(266, 296, 44, 34)
        vol_bar_rect = pygame.Rect(58, 300, 204, 26)

        # Slider + label only while adjusting or shortly after (+/- tap, bottom %, logo swipe)
        if show_volume_bar or adjusting_volume:
            pygame.draw.rect(screen, (40, 40, 40), vol_bar_rect, border_radius=12)
            fill_width = int(vol_bar_rect.width * vol_level / 100)
            if fill_width > 0:
                pygame.draw.rect(screen, CYAN, (vol_bar_rect.x, vol_bar_rect.y, fill_width, vol_bar_rect.height), border_radius=12)
            pygame.draw.rect(screen, WHITE, vol_bar_rect, 2, border_radius=12)

            knob_x = vol_bar_rect.x + int(vol_bar_rect.width * vol_level / 100)
            knob_x = max(vol_bar_rect.x + 8, min(vol_bar_rect.right - 8, knob_x))
            pygame.draw.circle(screen, WHITE, (knob_x, vol_bar_rect.centery), 8)
            vol_pct_surf = f_tiny.render(f"VOL {vol_level}%", True, WHITE)
            screen.blit(vol_pct_surf, (160 - vol_pct_surf.get_width() // 2, 330))

        # Draw + / − on top so they stay visible when the bar is shown
        pygame.draw.rect(screen, GOLD, vol_minus_rect, border_radius=8)
        pygame.draw.rect(screen, BLACK, vol_minus_rect, 2, border_radius=8)
        mc = vol_minus_rect.center
        pygame.draw.line(screen, BLACK, (mc[0] - 10, mc[1]), (mc[0] + 10, mc[1]), 4)

        pygame.draw.rect(screen, GOLD, vol_plus_rect, border_radius=8)
        pygame.draw.rect(screen, BLACK, vol_plus_rect, 2, border_radius=8)
        pc = vol_plus_rect.center
        pygame.draw.line(screen, BLACK, (pc[0], pc[1] - 10), (pc[0], pc[1] + 10), 4)
        pygame.draw.line(screen, BLACK, (pc[0] - 10, pc[1]), (pc[0] + 10, pc[1]), 4)
        
        # English UI buttons (NOT translated to Tamil) — y lowered so volume strip + label clear
        btn_prev = pygame.draw.rect(screen, (30,30,30), (10,352,95,55), border_radius=15)
        pygame.draw.rect(screen, CYAN, (10,352,95,55), 2, border_radius=15)
        screen.blit(f_sm.render("PREV", True, WHITE), (35,369))
        
        btn_toggle = pygame.draw.rect(screen, (30,30,30), (112,352,95,55), border_radius=15)
        pygame.draw.rect(screen, GOLD, (112,352,95,55), 2, border_radius=15)
        screen.blit(f_sm.render("PAUSE" if is_playing else "PLAY", True, GOLD), (135,369))
        
        btn_next = pygame.draw.rect(screen, (30,30,30), (215,352,95,55), border_radius=15)
        pygame.draw.rect(screen, PURPLE, (215,352,95,55), 2, border_radius=15)
        screen.blit(f_sm.render("NEXT", True, WHITE), (240,369))
        
        pygame.draw.rect(screen, (20,20,20), (0,430,320,50))
        btn_sleep = pygame.draw.rect(screen, PURPLE, (5, 435, 70, 40), border_radius=5)
        screen.blit(f_sm.render("SLEEP", True, WHITE), (13, 445))
        btn_saver = pygame.draw.rect(screen, (50,50,50), (80, 435, 70, 40), border_radius=5)
        screen.blit(f_sm.render("MOON", True, WHITE), (95, 445))
        btn_alarm = pygame.draw.rect(screen, GOLD if alarm_system.alarm_enabled else GRAY, (155, 435, 70, 40), border_radius=5)
        screen.blit(f_sm.render("ALARM", True, BLACK if alarm_system.alarm_enabled else WHITE), (163, 445))

        vol_rect = pygame.Rect(230, 435, 40, 40)
        screen.blit(f_sm.render(f"{vol_level}%", True, WHITE), (230, 445))
        btn_mute = pygame.draw.rect(screen, (30,30,30), (275, 435, 40, 40), border_radius=5)
        screen.blit(f_sm.render("M", True, CYAN if vol_level > 0 else RED), (288, 445))
        
        if show_qr:
            pygame.draw.rect(screen, BLACK, (35,95,250,250), border_radius=10)
            pygame.draw.rect(screen, CYAN, (35,95,250,250), 2, border_radius=10)
            screen.blit(qr_surface, (40,100))
    
    for event in pygame.event.get():
        if event.type == pygame.MOUSEBUTTONDOWN:
            touch_start_pos = event.pos
            touch_start_time = time.time()
            if saver_active:
                saver_active = False
                continue
            if show_qr:
                show_qr = False
                continue
            if btn_exit.collidepoint(event.pos):
                pygame.quit()
                sys.exit()
            if btn_qr.collidepoint(event.pos):
                show_qr = True
            if btn_prev.collidepoint(event.pos):
                current_idx = (current_idx - 1) % len(stations)
                play()
            if btn_next.collidepoint(event.pos):
                current_idx = (current_idx + 1) % len(stations)
                play()
            if btn_toggle.collidepoint(event.pos):
                player.pause()
            if btn_mute.collidepoint(event.pos):
                vol_level = 0 if vol_level > 0 else 80
                player.audio_set_volume(vol_level)
                audio_manager.set_volume(vol_level)
            if btn_sleep.collidepoint(event.pos):
                if alarm_system.sleep_timer_enabled:
                    alarm_system.stop_sleep_timer()
                else:
                    alarm_system.start_sleep_timer(30)
            if btn_saver.collidepoint(event.pos):
                saver_active = not saver_active
            if btn_alarm.collidepoint(event.pos):
                alarm_system.alarm_enabled = not alarm_system.alarm_enabled
                alarm_system.save_alarm_settings()
            if vol_minus_rect.collidepoint(event.pos):
                vol_level = max(0, vol_level - 5)
                player.audio_set_volume(vol_level)
                audio_manager.set_volume(vol_level)
                show_volume_bar = True
                volume_bar_timer = time.time()
            if vol_plus_rect.collidepoint(event.pos):
                vol_level = min(100, vol_level + 5)
                player.audio_set_volume(vol_level)
                audio_manager.set_volume(vol_level)
                show_volume_bar = True
                volume_bar_timer = time.time()
            if vol_bar_rect.collidepoint(event.pos):
                adjusting_volume = True
                vol_level = int((event.pos[0] - vol_bar_rect.x) * 100 / vol_bar_rect.width)
                vol_level = max(0, min(100, vol_level))
                player.audio_set_volume(vol_level)
                audio_manager.set_volume(vol_level)
                show_volume_bar = True
                volume_bar_timer = time.time()
            if vol_rect.collidepoint(event.pos):
                show_volume_bar = True
                adjusting_volume = True
                volume_bar_timer = time.time()
        
        elif event.type == pygame.MOUSEBUTTONUP:
            if logo_rect.collidepoint(touch_start_pos):
                dy = touch_start_pos[1] - event.pos[1]
                dt = time.time() - touch_start_time
                if dt > 1.0:
                    if alarm_system.sleep_timer_enabled:
                        alarm_system.stop_sleep_timer()
                    else:
                        alarm_system.start_sleep_timer(30)
                elif abs(dy) > 30:
                    if dy > 0:
                        vol_level = min(100, vol_level + 5)
                    else:
                        vol_level = max(0, vol_level - 5)
                    player.audio_set_volume(vol_level)
                    audio_manager.set_volume(vol_level)
                    show_volume_bar = True
                    volume_bar_timer = time.time()
            adjusting_volume = False
        
        elif event.type == pygame.MOUSEMOTION and adjusting_volume:
            if event.pos[0] >= vol_bar_rect.x and event.pos[0] <= vol_bar_rect.right:
                vol_level = int((event.pos[0] - vol_bar_rect.x) * 100 / vol_bar_rect.width)
                vol_level = max(0, min(100, vol_level))
                player.audio_set_volume(vol_level)
                audio_manager.set_volume(vol_level)
                volume_bar_timer = time.time()
    
    pygame.display.flip()
    time.sleep(0.05)

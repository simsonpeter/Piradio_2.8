#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pygame, vlc, requests, time, os, io, math, socket, sys, threading, qrcode, json, base64, random, re, shutil, signal, traceback
from urllib.request import urlopen
from urllib.parse import urlparse
from datetime import datetime, timedelta
from flask import Flask, render_template_string, Response, jsonify, request
import subprocess

try:
    from PIL import Image, ImageDraw, ImageFont
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
print(f"🚀 TC RADIOS STARTED SUCCESSFULLY!")
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

def log_uncaught_exception(exc_type, exc, tb):
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    print(f"TC RADIOS crash:\n{text}", flush=True)
    try:
        with open(os.path.expanduser("~/.tcradios-crash.log"), "a") as handle:
            handle.write(f"{datetime.now().isoformat()}\n{text}\n")
    except OSError:
        pass

sys.excepthook = log_uncaught_exception

# --- AUDIO OUTPUT MANAGER ---
class AudioOutputManager:
    def __init__(self):
        self.outputs = {}
        self.current_output = 'auto'
        self.multi_mode = False
        self.bluetooth_lock = threading.Lock()
        self.settings_file = os.path.expanduser('~/.radio_audio')
        self.default_bluetooth_address = None
        self.load_settings()
        self.scan_outputs()
        if self.default_bluetooth_address:
            threading.Thread(
                target=self._restore_bluetooth_default,
                daemon=True
            ).start()

    def _run(self, command, timeout=15, input_text=None):
        try:
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                input=input_text,
                timeout=timeout
            )
        except FileNotFoundError:
            raise RuntimeError(f"{command[0]} is not installed")
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"{command[0]} timed out")

    def load_settings(self):
        try:
            with open(self.settings_file, 'r') as settings:
                data = json.load(settings)
                address = data.get('default_bluetooth_address')
                if address and self._valid_bluetooth_address(address):
                    self.default_bluetooth_address = address.upper()
        except (OSError, ValueError, TypeError):
            pass

    def save_settings(self):
        try:
            with open(self.settings_file, 'w') as settings:
                json.dump({
                    'default_bluetooth_address': self.default_bluetooth_address
                }, settings)
        except OSError as e:
            print(f"Audio settings save error: {e}")

    @staticmethod
    def _valid_bluetooth_address(address):
        return isinstance(address, str) and bool(
            re.fullmatch(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', address)
        )

    @staticmethod
    def _parse_bluetooth_devices(output):
        devices = {}
        for line in output.splitlines():
            match = re.match(r'^Device ((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})\s+(.+)$', line.strip())
            if match:
                address = match.group(1).upper()
                devices[address] = {
                    'address': address,
                    'name': match.group(2).strip()
                }
        return devices

    def _bluetooth_device_sets(self):
        all_result = self._run(['bluetoothctl', 'devices'])
        if all_result.returncode != 0:
            error = all_result.stderr.strip() or all_result.stdout.strip()
            raise RuntimeError(error or 'Bluetooth service is unavailable')

        devices = self._parse_bluetooth_devices(all_result.stdout)
        paired_result = self._run(['bluetoothctl', 'devices', 'Paired'])
        connected_result = self._run(['bluetoothctl', 'devices', 'Connected'])
        paired = set(self._parse_bluetooth_devices(paired_result.stdout))
        connected = set(self._parse_bluetooth_devices(connected_result.stdout))

        # Older bluetoothctl versions use "paired-devices".
        paired_output = (paired_result.stdout + paired_result.stderr).lower()
        if paired_result.returncode != 0 or 'invalid command' in paired_output:
            paired_result = self._run(['bluetoothctl', 'paired-devices'])
            paired = set(self._parse_bluetooth_devices(paired_result.stdout))

        connected_output = (connected_result.stdout + connected_result.stderr).lower()
        if connected_result.returncode != 0 or 'invalid command' in connected_output:
            for address in devices:
                info_result = self._run(['bluetoothctl', 'info', address])
                if re.search(r'^\s*Connected:\s+yes\s*$', info_result.stdout, re.MULTILINE | re.IGNORECASE):
                    connected.add(address)

        for address in paired | connected:
            devices.setdefault(address, {'address': address, 'name': address})
        return devices, paired, connected

    def _bluetooth_info_flag(self, address, flag):
        result = self._run(['bluetoothctl', 'info', address])
        if result.returncode != 0:
            return False
        return bool(re.search(
            rf'^\s*{re.escape(flag)}:\s+yes\s*$',
            result.stdout,
            re.MULTILINE | re.IGNORECASE
        ))

    def _restart_bluetooth_audio_profile(self):
        # WirePlumber registers the A2DP profile with BlueZ. It can be late to
        # start in a desktop session, leaving paired devices unable to connect.
        self._run(
            ['systemctl', '--user', 'restart', 'wireplumber.service'],
            timeout=20
        )
        # On older Raspberry Pi OS releases PulseAudio supplies the profile.
        # Loading an existing module is harmless; errors are handled by retry.
        self._run(
            ['pactl', 'load-module', 'module-bluetooth-discover'],
            timeout=10
        )
        time.sleep(2)

    def get_bluetooth_devices(self):
        devices, paired, connected = self._bluetooth_device_sets()
        result = []
        for address, device in devices.items():
            result.append({
                **device,
                'paired': address in paired,
                'connected': address in connected,
                'default': address == self.default_bluetooth_address
            })
        return sorted(
            result,
            key=lambda device: (
                not device['connected'],
                not device['paired'],
                device['name'].lower()
            )
        )

    def _discovered_bluetooth_devices(self, output):
        discovered = []
        seen = set()
        for line in output.splitlines():
            match = re.search(
                r'\[NEW\] Device ((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})\s+(.+)$',
                line.strip()
            )
            if not match:
                continue
            address = match.group(1).upper()
            if address in seen:
                continue
            seen.add(address)
            discovered.append({
                'address': address,
                'name': match.group(2).strip()
            })
        return discovered

    def _merge_bluetooth_scan(self, discovered):
        known = {device['address']: device for device in self.get_bluetooth_devices()}
        ordered = []
        seen = set()

        def add(address, fallback_name=None):
            if address in seen:
                return
            seen.add(address)
            device = known.get(address)
            if device is None:
                device = {
                    'address': address,
                    'name': fallback_name or address,
                    'paired': False,
                    'connected': False,
                    'default': address == self.default_bluetooth_address
                }
            elif fallback_name and device['name'] == device['address']:
                device = {**device, 'name': fallback_name}
            ordered.append(device)

        for device in known.values():
            if device.get('connected'):
                add(device['address'])
        for device in known.values():
            if device.get('paired'):
                add(device['address'])
        for item in discovered:
            add(item['address'], item.get('name'))
        for device in known.values():
            add(device['address'])
        return ordered

    def scan_bluetooth(self):
        with self.bluetooth_lock:
            power_result = self._run(['bluetoothctl', 'power', 'on'])
            if power_result.returncode != 0:
                error = power_result.stderr.strip() or power_result.stdout.strip()
                raise RuntimeError(error or 'Could not power on Bluetooth')
            # bluetoothctl performs discovery until its timeout expires.
            scan_result = self._run(
                ['bluetoothctl', '--timeout', '8', 'scan', 'on'],
                timeout=12
            )
            discovered = self._discovered_bluetooth_devices(
                scan_result.stdout + '\n' + scan_result.stderr
            )
            return self._merge_bluetooth_scan(discovered)

    def _find_bluetooth_sink(self, address):
        result = self._run(['pactl', 'list', 'sinks', 'short'])
        address_token = address.replace(':', '_').lower()
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and address_token in parts[1].lower():
                return parts[1]
        return None

    def _make_sink_default(self, address):
        sink_name = None
        for _ in range(12):
            sink_name = self._find_bluetooth_sink(address)
            if sink_name:
                break
            time.sleep(0.5)
        if not sink_name:
            raise RuntimeError('Connected, but no Bluetooth audio output appeared')

        result = self._run(['pactl', 'set-default-sink', sink_name])
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or 'Could not set the default audio output')

        # Move audio that was already playing to the newly selected speaker.
        inputs = self._run(['pactl', 'list', 'sink-inputs', 'short'])
        for line in inputs.stdout.splitlines():
            parts = line.split()
            if parts and parts[0].isdigit():
                self._run(['pactl', 'move-sink-input', parts[0], sink_name])
        return sink_name

    def connect_bluetooth(self, address):
        if not self._valid_bluetooth_address(address):
            raise ValueError('Invalid Bluetooth address')
        address = address.upper()

        with self.bluetooth_lock:
            power_result = self._run(['bluetoothctl', 'power', 'on'])
            if power_result.returncode != 0:
                raise RuntimeError(
                    power_result.stderr.strip()
                    or power_result.stdout.strip()
                    or 'Could not power on Bluetooth'
                )
            _, paired, _ = self._bluetooth_device_sets()

            if address not in paired:
                pair_result = self._run(
                    [
                        'bluetoothctl', '--timeout', '35',
                        '--agent', 'NoInputNoOutput',
                        'pair', address
                    ],
                    timeout=40,
                )
                pair_output = (pair_result.stdout + pair_result.stderr).lower()
                if (
                    pair_result.returncode != 0
                    or 'failed' in pair_output
                    or not self._bluetooth_info_flag(address, 'Paired')
                ):
                    raise RuntimeError(
                        pair_result.stderr.strip()
                        or pair_result.stdout.strip()
                        or 'Bluetooth pairing failed'
                    )

            trust_result = self._run(['bluetoothctl', 'trust', address])
            trust_output = (trust_result.stdout + trust_result.stderr).lower()
            if trust_result.returncode != 0 or 'failed' in trust_output:
                raise RuntimeError(
                    trust_result.stderr.strip()
                    or trust_result.stdout.strip()
                    or 'Could not trust the Bluetooth device'
                )

            # Pairing an audio device commonly connects it as well. Query its
            # current state instead of using the snapshot from before pairing;
            # otherwise a second connect reports AlreadyConnected as a failure.
            if not self._bluetooth_info_flag(address, 'Connected'):
                connect_result = self._run(
                    ['bluetoothctl', '--timeout', '20', 'connect', address],
                    timeout=25
                )
                connect_output = (connect_result.stdout + connect_result.stderr).lower()
                if 'br-connection-profile-unavailable' in connect_output:
                    self._restart_bluetooth_audio_profile()
                    connect_result = self._run(
                        ['bluetoothctl', '--timeout', '20', 'connect', address],
                        timeout=25
                    )
                    connect_output = (
                        connect_result.stdout + connect_result.stderr
                    ).lower()
                if (
                    connect_result.returncode != 0
                    or 'failed' in connect_output
                    or not self._bluetooth_info_flag(address, 'Connected')
                ):
                    if 'br-connection-profile-unavailable' in connect_output:
                        raise RuntimeError(
                            'Bluetooth audio profile unavailable. Re-run the '
                            'TCRADIOS installer, reboot, and try again.'
                        )
                    raise RuntimeError(
                        connect_result.stderr.strip()
                        or connect_result.stdout.strip()
                        or 'Bluetooth connection failed'
                    )

            sink_name = self._make_sink_default(address)
            self.default_bluetooth_address = address
            self.current_output = 'bluetooth'
            self.save_settings()
            self.scan_outputs()
            self.current_output = 'bluetooth'
            return sink_name

    def _restore_bluetooth_default(self):
        try:
            self.connect_bluetooth(self.default_bluetooth_address)
            print(f"Restored Bluetooth default: {self.default_bluetooth_address}")
        except Exception as e:
            print(f"Bluetooth restore error: {e}")
    
    def scan_outputs(self):
        self.outputs = {
            'auto': {'name': 'Auto (System Default)', 'available': True, 'type': 'auto'},
            'analog': {'name': '3.5mm Jack (Analog)', 'available': False, 'type': 'alsa'},
            'hdmi': {'name': 'HDMI Audio', 'available': False, 'type': 'alsa'},
            'bluetooth': {'name': 'Bluetooth', 'available': False, 'type': 'bluez'}
        }
        
        try:
            result = subprocess.run(
                ['aplay', '-l'], capture_output=True, text=True, timeout=3
            )
            output = result.stdout.lower()
            if 'bcm2835' in output or 'headphones' in output or 'analog' in output:
                self.outputs['analog']['available'] = True
            if 'hdmi' in output:
                self.outputs['hdmi']['available'] = True
        except Exception as e:
            print(f"Error scanning ALSA: {e}")
        
        try:
            result = subprocess.run(
                ['pactl', 'list', 'sinks', 'short'],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'bluez' in line.lower() or 'bluetooth' in line.lower():
                        self.outputs['bluetooth']['available'] = True
                        parts = line.split()
                        if len(parts) >= 2:
                            self.outputs['bluetooth']['device'] = parts[1]
        except Exception:
            pass
        
        try:
            result = subprocess.run(
                ['bluetoothctl', 'devices', 'Connected'],
                capture_output=True, text=True, timeout=3,
            )
            if result.stdout.strip():
                self.outputs['bluetooth']['available'] = True
                self.outputs['bluetooth']['connected_device'] = result.stdout.strip().split('\n')[0]
        except Exception:
            pass
        
        print(f"Audio outputs detected: {[(k, v['available']) for k, v in self.outputs.items()]}")

    def set_output(self, output_name):
        if output_name not in self.outputs:
            return False

        if output_name == 'auto':
            os.system("amixer cset numid=3 0")
            self.current_output = output_name
            return True
        elif output_name == 'analog':
            os.system("amixer cset numid=3 1")
            self.current_output = output_name
            return True
        elif output_name == 'hdmi':
            os.system("amixer cset numid=3 2")
            self.current_output = output_name
            return True
        elif output_name == 'bluetooth':
            try:
                if self.default_bluetooth_address:
                    self._make_sink_default(self.default_bluetooth_address)
                    self.current_output = output_name
                    return True
                result = self._run(['pactl', 'list', 'sinks', 'short'])
                for line in result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and 'bluez' in parts[1].lower():
                        self._run(['pactl', 'set-default-sink', parts[1]])
                        self.current_output = output_name
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
vol_level = 80
last_unmuted_volume = 80

def apply_live_volume(level):
    global vol_level, last_unmuted_volume
    vol_level = max(0, min(100, int(level)))
    if vol_level > 0:
        last_unmuted_volume = vol_level
    try:
        player.audio_set_volume(vol_level)
    except Exception:
        pass
    try:
        audio_manager.set_volume(vol_level)
    except Exception as error:
        print(f"Volume error: {error}")
    try:
        save_playback_state()
    except NameError:
        pass

def skip_playback(step):
    global current_idx
    try:
        if current_youtube_id() and continue_youtube_queue(step, user=True):
            return
    except NameError:
        pass
    try:
        if stations:
            current_idx = (current_idx + step) % len(stations)
            play()
    except (NameError, ZeroDivisionError):
        pass

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
        self.card = colors.get('card', 'rgba(8,10,14,0.96)')
        self.button = colors.get('button', colors.get('primary', '#2ee6ff'))
        self.button_hover = colors.get('button_hover', colors.get('secondary', '#c86bff'))
        self.gradient_start = colors.get('gradient_start', '#000000')
        self.gradient_end = colors.get('gradient_end', colors.get('primary', '#2ee6ff'))
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

def dark_theme(name, primary, secondary, accent):
    return Theme(name, {
        'background': '#000000',
        'primary': primary,
        'secondary': secondary,
        'accent': accent,
        'text': '#f6f7ff',
        'card': 'rgba(8,10,14,0.96)',
        'button': primary,
        'button_hover': secondary,
        'gradient_start': '#000000',
        'gradient_end': primary,
    })

THEMES = {
    'true_black': dark_theme('True Black', '#2ee6c7', '#5ba8ff', '#f0c45a'),
    'midnight_black': dark_theme('Midnight Black', '#8ea2ff', '#d4a4ff', '#f0c45a'),
    'pure_white': dark_theme('Ice Night', '#7ed4ff', '#9bb0ff', '#f4d27a'),
    'ocean_blue': dark_theme('Ocean Blue', '#33d6ff', '#4f8cff', '#5ee0b8'),
    'sunset_orange': dark_theme('Sunset Orange', '#ff8a3d', '#ff6b9d', '#ffd166'),
    'forest_green': dark_theme('Forest Green', '#3ee6a0', '#7ae08a', '#f0c45a'),
    'purple_haze': dark_theme('Purple Haze', '#c9a0ff', '#8b85ff', '#ff9ec8'),
    'cyberpunk': dark_theme('Cyberpunk', '#ff4ec8', '#2ee6e0', '#ffb347'),
    'golden_hour': dark_theme('Golden Hour', '#f0c03a', '#ff9a3d', '#3ee6c7'),
    'mint_fresh': dark_theme('Mint Fresh', '#3ee6c7', '#7ae0e8', '#8bb4ff'),
    'crimson_red': dark_theme('Crimson Red', '#ff5a73', '#f0c45a', '#3ee6c7'),
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

# --- WEATHER, DISPLAY & POWER SETTINGS ---
HOME_CARD_KINDS = (
    "now_playing",
    "weather",
    "forecast",
    "alarm",
    "system",
    "bluetooth",
)
HOME_CARD_LABELS = {
    "now_playing": "NOW PLAYING",
    "weather": "WEATHER",
    "forecast": "FORECAST",
    "alarm": "ALARM",
    "system": "SYSTEM",
    "bluetooth": "BLUETOOTH",
}
DEFAULT_HOME_CARDS = ["now_playing", "weather"]
HOME_CARD_LAYOUTS = ("single", "bubble")
DEFAULT_HOME_CARD_LAYOUT = "bubble"
# Title bar and PAGES stay outside this band. Cards fill it, no middle gap.
HOME_CARD_TOP = 64
HOME_CARD_HEIGHT = 352
HOME_CARD_INSET = 8
HOME_CARD_FULL_W = 304
HOME_CARD_HALF_W = 152


def normalize_home_cards(raw):
    cards = []
    if isinstance(raw, (list, tuple)):
        for item in raw:
            if item in HOME_CARD_LABELS and item not in cards:
                cards.append(item)
    for kind in DEFAULT_HOME_CARDS:
        if len(cards) >= 2:
            break
        if kind not in cards:
            cards.append(kind)
    for kind in HOME_CARD_KINDS:
        if len(cards) >= 2:
            break
        if kind not in cards:
            cards.append(kind)
    return cards[:2]


def normalize_home_card_layout(raw):
    if raw in HOME_CARD_LAYOUTS:
        return raw
    return DEFAULT_HOME_CARD_LAYOUT


class DeviceSettingsManager:
    def __init__(self):
        self.settings_file = os.path.expanduser("~/.radio_device_settings")
        self.weather_name = "Hove"
        self.weather_country = "United Kingdom"
        self.weather_latitude = 50.83
        self.weather_longitude = -0.17
        self.brightness = 100
        self.auto_dim_enabled = False
        self.auto_dim_minutes = 5
        self.dim_brightness = 25
        self.home_cards = list(DEFAULT_HOME_CARDS)
        self.home_card_layout = DEFAULT_HOME_CARD_LAYOUT
        self.applied_brightness = None
        self.hardware_brightness_available = False
        self.load()

    def load(self):
        try:
            with open(self.settings_file, "r", encoding="utf-8") as settings:
                data = json.load(settings)
            self.weather_name = str(
                data.get("weather_name", self.weather_name)
            )[:60]
            self.weather_country = str(
                data.get("weather_country", self.weather_country)
            )[:60]
            self.weather_latitude = float(
                data.get("weather_latitude", self.weather_latitude)
            )
            self.weather_longitude = float(
                data.get("weather_longitude", self.weather_longitude)
            )
            self.brightness = max(
                10, min(100, int(data.get("brightness", self.brightness)))
            )
            self.auto_dim_enabled = bool(
                data.get("auto_dim_enabled", self.auto_dim_enabled)
            )
            self.auto_dim_minutes = max(
                1, min(60, int(
                    data.get("auto_dim_minutes", self.auto_dim_minutes)
                ))
            )
            self.dim_brightness = max(
                5, min(50, int(
                    data.get("dim_brightness", self.dim_brightness)
                ))
            )
            self.home_cards = normalize_home_cards(data.get("home_cards"))
            self.home_card_layout = normalize_home_card_layout(
                data.get("home_card_layout")
            )
        except (OSError, ValueError, TypeError):
            pass

    def save(self):
        data = {
            "weather_name": self.weather_name,
            "weather_country": self.weather_country,
            "weather_latitude": self.weather_latitude,
            "weather_longitude": self.weather_longitude,
            "brightness": self.brightness,
            "auto_dim_enabled": self.auto_dim_enabled,
            "auto_dim_minutes": self.auto_dim_minutes,
            "dim_brightness": self.dim_brightness,
            "home_cards": list(self.home_cards),
            "home_card_layout": self.home_card_layout
        }
        try:
            with open(self.settings_file, "w", encoding="utf-8") as settings:
                json.dump(data, settings, indent=2)
        except OSError as error:
            print(f"Device settings save error: {error}")

    def weather_url(self):
        return (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={self.weather_latitude}"
            f"&longitude={self.weather_longitude}"
            "&current_weather=true"
            "&daily=weather_code,temperature_2m_max,temperature_2m_min"
            "&forecast_days=5&timezone=auto"
        )

    def set_hardware_brightness(self, level):
        level = max(5, min(100, int(level)))
        if self.applied_brightness == level:
            return
        self.applied_brightness = level
        self.hardware_brightness_available = False

        backlight_root = "/sys/class/backlight"
        try:
            for device in os.listdir(backlight_root):
                device_path = os.path.join(backlight_root, device)
                with open(
                    os.path.join(device_path, "max_brightness"), "r"
                ) as maximum_file:
                    maximum = int(maximum_file.read().strip())
                value = max(1, round(maximum * level / 100))
                with open(
                    os.path.join(device_path, "brightness"), "w"
                ) as brightness_file:
                    brightness_file.write(str(value))
                self.hardware_brightness_available = True
                return
        except (OSError, ValueError):
            pass

        try:
            query = subprocess.run(
                ["xrandr", "--query"],
                capture_output=True,
                text=True,
                timeout=3,
                env={**os.environ, "DISPLAY": ":0"}
            )
            output = next(
                (
                    line.split()[0]
                    for line in query.stdout.splitlines()
                    if " connected" in line
                ),
                None
            )
            if output:
                result = subprocess.run(
                    [
                        "xrandr", "--output", output,
                        "--brightness", f"{level / 100:.2f}"
                    ],
                    capture_output=True,
                    timeout=3,
                    env={**os.environ, "DISPLAY": ":0"}
                )
                self.hardware_brightness_available = result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            pass

    def as_dict(self):
        return {
            "weather_name": self.weather_name,
            "weather_country": self.weather_country,
            "weather_latitude": self.weather_latitude,
            "weather_longitude": self.weather_longitude,
            "brightness": self.brightness,
            "auto_dim_enabled": self.auto_dim_enabled,
            "auto_dim_minutes": self.auto_dim_minutes,
            "dim_brightness": self.dim_brightness,
            "home_cards": list(self.home_cards),
            "home_card_layout": self.home_card_layout
        }

device_settings = DeviceSettingsManager()
last_interaction_time = time.time()

# --- WEB REMOTE APP ---
app = Flask(__name__)

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

youtube_results_cache = []
youtube_queue = []
youtube_queue_index = -1
youtube_skip_ids = set()
youtube_touch_offset = 0
_youtube_was_playing = False
_youtube_ended_handled = False
_youtube_play_started_at = 0
YOUTUBE_SEARCH_COUNT = 24

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="theme-color" content="{{ theme.background }}">
    <title>TC RADIOS</title>
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
            --muted: #e6ebf6;
            --safe-top: env(safe-area-inset-top);
            --safe-bottom: env(safe-area-inset-bottom);
        }

        @font-face {
            font-family: 'TCRTamil';
            src: url('/static/NotoSansTamil-Regular.ttf') format('truetype');
            unicode-range: U+0B80-0BFF;
            font-display: swap;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
            font-family: 'TCRTamil', 'Noto Sans Tamil', 'Lohit Tamil', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        }
        
        html, body {
            height: 100%;
            background: #000;
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
            background: #000;
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
            background: color-mix(in srgb, var(--primary) 22%, #08080c);
            border: 2px solid var(--primary);
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
            color: var(--muted);
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
            background: #0a0c10;
            color: var(--text);
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 12px;
            border: 1px solid color-mix(in srgb, var(--primary) 40%, transparent);
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
            color: var(--muted);
        }
        
        .controls-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-top: 25px;
        }
        
        .control-btn {
            background: color-mix(in srgb, var(--button) 28%, #08080c);
            border: 2px solid var(--primary);
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
            color: var(--muted);
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
            color: var(--muted);
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
            color: var(--muted);
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
            color: var(--muted);
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
            color: var(--muted);
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
            color: var(--muted);
            margin-top: 2px;
        }

        .bluetooth-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 12px;
        }

        .bluetooth-status {
            color: var(--muted);
            font-size: 12px;
            line-height: 1.4;
        }

        .bluetooth-device {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 13px 0;
            border-top: 1px solid rgba(255,255,255,0.1);
        }

        .bluetooth-device:first-child {
            border-top: none;
        }

        .bluetooth-device-icon {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: rgba(0,210,255,0.12);
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }

        .bluetooth-device-info {
            flex: 1;
            min-width: 0;
        }

        .bluetooth-device-name {
            font-size: 14px;
            font-weight: 600;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .bluetooth-device-meta {
            color: var(--muted);
            font-size: 11px;
            margin-top: 3px;
        }

        .bluetooth-connect {
            border: 1px solid var(--primary);
            border-radius: 9px;
            padding: 8px 11px;
            background: transparent;
            color: var(--primary);
            font-size: 12px;
            font-weight: 700;
            cursor: pointer;
        }

        .bluetooth-connect:disabled {
            cursor: default;
            opacity: 0.65;
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
            color: var(--muted);
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
        <div class="connection-title">TC RADIOS</div>
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
            <div class="app-title">🎵 TC RADIOS</div>
            <div class="header-actions">
                <button class="icon-btn" onclick="window.open('/simulator', '_blank')" title="Touchscreen Simulator">📱</button>
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
                    <span class="section-title">Bluetooth Devices</span>
                </div>
                <div class="card">
                    <div class="bluetooth-header">
                        <div class="bluetooth-status" id="bluetooth-status">
                            Search for nearby speakers and headphones.
                        </div>
                        <button class="bluetooth-connect" id="bluetooth-scan-btn" onclick="scanBluetooth()">
                            Search
                        </button>
                    </div>
                    <div id="bluetooth-devices">
                        <div class="empty-state" style="padding: 24px 10px;">
                            <div class="empty-text">Tap Search to find Bluetooth devices</div>
                        </div>
                    </div>
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

                <div class="section-header">
                    <span class="section-title">Weather Location</span>
                </div>
                <div class="card">
                    <div class="input-group">
                        <label class="input-label">Town, city, or postcode</label>
                        <input type="text" id="weather-location" class="text-input" value="{{ device_settings.weather_name }}" placeholder="Hove">
                    </div>
                    <div id="weather-location-current" style="font-size: 13px; color: var(--muted); margin-bottom: 12px;">
                        {{ device_settings.weather_name }}{% if device_settings.weather_country %}, {{ device_settings.weather_country }}{% endif %}
                    </div>
                    <button class="btn-primary" onclick="saveWeatherLocation()">📍 Update Weather</button>
                </div>

                <div class="section-header">
                    <span class="section-title">Screen Brightness</span>
                </div>
                <div class="card">
                    <div class="setting-row">
                        <span class="setting-label">Brightness</span>
                        <span class="setting-value" id="brightness-value">{{ device_settings.brightness }}%</span>
                    </div>
                    <input type="range" id="brightness-slider" min="10" max="100" value="{{ device_settings.brightness }}" class="text-input" oninput="previewBrightness(this.value)" onchange="saveDisplaySettings()">

                    <div class="setting-row" style="margin-top: 18px;">
                        <span class="setting-label">Automatic dimming</span>
                        <div class="toggle-switch {% if device_settings.auto_dim_enabled %}active{% endif %}" id="auto-dim-toggle" onclick="toggleAutoDim()"></div>
                    </div>

                    <div class="input-group" style="margin-top: 15px;">
                        <label class="input-label">Dim after</label>
                        <select id="auto-dim-minutes" class="select-input" onchange="saveDisplaySettings()">
                            {% for minutes in [1, 2, 5, 10, 15, 30, 60] %}
                            <option value="{{ minutes }}" {% if minutes == device_settings.auto_dim_minutes %}selected{% endif %}>{{ minutes }} minute{% if minutes != 1 %}s{% endif %}</option>
                            {% endfor %}
                        </select>
                    </div>

                    <div class="setting-row">
                        <span class="setting-label">Dimmed level</span>
                        <span class="setting-value" id="dim-brightness-value">{{ device_settings.dim_brightness }}%</span>
                    </div>
                    <input type="range" id="dim-brightness-slider" min="5" max="50" value="{{ device_settings.dim_brightness }}" class="text-input" oninput="document.getElementById('dim-brightness-value').textContent = this.value + '%'" onchange="saveDisplaySettings()">
                </div>

                <div class="section-header">
                    <span class="section-title">Power</span>
                </div>
                <div class="card">
                    <div style="font-size: 13px; color: var(--muted); margin-bottom: 12px;">
                        Safely stop playback and shut down before removing power.
                    </div>
                    <button class="btn-primary" onclick="requestSafeShutdown()" style="background: #c0392b; color: #fff;">⏻ Safe Shutdown</button>
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
            'true_black': { bg: '#000000', primary: '#2ee6c7', secondary: '#5ba8ff', accent: '#f0c45a', text: '#ffffff', muted: '#e6ebf6', card: 'rgba(8,10,14,0.96)', button: '#2ee6c7', buttonHover: '#5ba8ff', gradientStart: '#000000', gradientEnd: '#2ee6c7' },
            'midnight_black': { bg: '#000000', primary: '#8ea2ff', secondary: '#d4a4ff', accent: '#f0c45a', text: '#ffffff', muted: '#e6ebf6', card: 'rgba(8,10,14,0.96)', button: '#8ea2ff', buttonHover: '#d4a4ff', gradientStart: '#000000', gradientEnd: '#8ea2ff' },
            'pure_white': { bg: '#000000', primary: '#7ed4ff', secondary: '#9bb0ff', accent: '#f4d27a', text: '#ffffff', muted: '#e6ebf6', card: 'rgba(8,10,14,0.96)', button: '#7ed4ff', buttonHover: '#9bb0ff', gradientStart: '#000000', gradientEnd: '#7ed4ff' },
            'ocean_blue': { bg: '#000000', primary: '#33d6ff', secondary: '#4f8cff', accent: '#5ee0b8', text: '#ffffff', muted: '#e6ebf6', card: 'rgba(8,10,14,0.96)', button: '#33d6ff', buttonHover: '#4f8cff', gradientStart: '#000000', gradientEnd: '#33d6ff' },
            'sunset_orange': { bg: '#000000', primary: '#ff8a3d', secondary: '#ff6b9d', accent: '#ffd166', text: '#ffffff', muted: '#e6ebf6', card: 'rgba(8,10,14,0.96)', button: '#ff8a3d', buttonHover: '#ff6b9d', gradientStart: '#000000', gradientEnd: '#ff8a3d' },
            'forest_green': { bg: '#000000', primary: '#3ee6a0', secondary: '#7ae08a', accent: '#f0c45a', text: '#ffffff', muted: '#e6ebf6', card: 'rgba(8,10,14,0.96)', button: '#3ee6a0', buttonHover: '#7ae08a', gradientStart: '#000000', gradientEnd: '#3ee6a0' },
            'purple_haze': { bg: '#000000', primary: '#c9a0ff', secondary: '#8b85ff', accent: '#ff9ec8', text: '#ffffff', muted: '#e6ebf6', card: 'rgba(8,10,14,0.96)', button: '#c9a0ff', buttonHover: '#8b85ff', gradientStart: '#000000', gradientEnd: '#c9a0ff' },
            'cyberpunk': { bg: '#000000', primary: '#ff4ec8', secondary: '#2ee6e0', accent: '#ffb347', text: '#ffffff', muted: '#e6ebf6', card: 'rgba(8,10,14,0.96)', button: '#ff4ec8', buttonHover: '#2ee6e0', gradientStart: '#000000', gradientEnd: '#ff4ec8' },
            'golden_hour': { bg: '#000000', primary: '#f0c03a', secondary: '#ff9a3d', accent: '#3ee6c7', text: '#ffffff', muted: '#e6ebf6', card: 'rgba(8,10,14,0.96)', button: '#f0c03a', buttonHover: '#ff9a3d', gradientStart: '#000000', gradientEnd: '#f0c03a' },
            'mint_fresh': { bg: '#000000', primary: '#3ee6c7', secondary: '#7ae0e8', accent: '#8bb4ff', text: '#ffffff', muted: '#e6ebf6', card: 'rgba(8,10,14,0.96)', button: '#3ee6c7', buttonHover: '#7ae0e8', gradientStart: '#000000', gradientEnd: '#3ee6c7' },
            'crimson_red': { bg: '#000000', primary: '#ff5a73', secondary: '#f0c45a', accent: '#3ee6c7', text: '#ffffff', muted: '#e6ebf6', card: 'rgba(8,10,14,0.96)', button: '#ff5a73', buttonHover: '#f0c45a', gradientStart: '#000000', gradientEnd: '#ff5a73' }
        };
        
        function applyTheme(themeKey) {
            const t = themes[themeKey] || themes['true_black'];
            const root = document.documentElement;
            root.style.setProperty('--bg', t.bg);
            root.style.setProperty('--primary', t.primary);
            root.style.setProperty('--secondary', t.secondary);
            root.style.setProperty('--accent', t.accent);
            root.style.setProperty('--text', t.text);
            root.style.setProperty('--muted', t.muted || '#e6ebf6');
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
        let autoDimEnabled = {{ device_settings.auto_dim_enabled|tojson }};
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
            }).then(r => r.text()).then(text => {
                let data;
                try {
                    data = JSON.parse(text);
                } catch (e) {
                    throw new Error('Search failed');
                }
                if (data.success) {
                    youtubeResults = data.results || [];
                    displayYouTubeResults(youtubeResults);
                } else {
                    resultsDiv.innerHTML = '<div class="empty-state"><div class="empty-text">' + escapeHtml(data.error || 'Search failed') + '</div></div>';
                }
            }).catch(err => {
                resultsDiv.innerHTML = '<div class="empty-state"><div class="empty-text">' + escapeHtml(err.message || 'Search failed') + '</div></div>';
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
            fetch(apiBase + '/api/audio/output/' + output, {method: 'POST'})
                .then(r => r.json())
                .then(data => {
                    if (!data.success) throw new Error(data.error || 'Could not change output');
                    document.querySelectorAll('.output-btn').forEach(b => b.classList.remove('active'));
                    document.getElementById('out-' + output).classList.add('active');
                    showToast('Output: ' + output);
                })
                .catch(error => showToast(error.message));
        }
        
        function enableMultiOutput() {
            fetch(apiBase + '/api/audio/multi', {method: 'POST'}).then(() => {
                showToast('Multi-output enabled');
            });
        }

        function displayBluetoothDevices(devices) {
            const container = document.getElementById('bluetooth-devices');
            const status = document.getElementById('bluetooth-status');
            if (!devices.length) {
                status.textContent = 'No devices found. Put your speaker in pairing mode and search again.';
                container.innerHTML = '<div class="empty-state" style="padding: 24px 10px;"><div class="empty-text">No Bluetooth devices found</div></div>';
                return;
            }

            const connected = devices.find(device => device.connected && device.default)
                || devices.find(device => device.connected);
            status.textContent = connected
                ? `Connected to ${connected.name}${connected.default ? ' • Default audio output' : ''}`
                : `${devices.length} device${devices.length === 1 ? '' : 's'} found`;
            container.innerHTML = devices.map(device => {
                const state = device.connected
                    ? (device.default ? 'Connected • Default output' : 'Connected')
                    : (device.paired ? 'Paired' : 'Available');
                return `
                    <div class="bluetooth-device">
                        <div class="bluetooth-device-icon">${device.connected ? '🔊' : '📡'}</div>
                        <div class="bluetooth-device-info">
                            <div class="bluetooth-device-name">${escapeHtml(device.name)}</div>
                            <div class="bluetooth-device-meta">${state} • ${device.address}</div>
                        </div>
                        <button class="bluetooth-connect"
                                onclick="connectBluetooth('${device.address}', this)"
                                ${device.connected && device.default ? 'disabled' : ''}>
                            ${device.connected && device.default ? 'Default' : 'Connect'}
                        </button>
                    </div>
                `;
            }).join('');
        }

        function loadBluetoothDevices() {
            fetch(apiBase + '/api/bluetooth/devices')
                .then(async response => {
                    const data = await response.json();
                    if (!response.ok || !data.success) throw new Error(data.error || 'Bluetooth is unavailable');
                    displayBluetoothDevices(data.devices);
                })
                .catch(error => {
                    document.getElementById('bluetooth-status').textContent = error.message;
                });
        }

        function scanBluetooth() {
            const button = document.getElementById('bluetooth-scan-btn');
            button.disabled = true;
            button.textContent = 'Searching…';
            document.getElementById('bluetooth-status').textContent = 'Searching for nearby devices…';
            fetch(apiBase + '/api/bluetooth/scan', {method: 'POST'})
                .then(async response => {
                    const data = await response.json();
                    if (!response.ok || !data.success) throw new Error(data.error || 'Bluetooth search failed');
                    displayBluetoothDevices(data.devices);
                })
                .catch(error => {
                    document.getElementById('bluetooth-status').textContent = error.message;
                    showToast(error.message);
                })
                .finally(() => {
                    button.disabled = false;
                    button.textContent = 'Search';
                });
        }

        function connectBluetooth(address, button) {
            button.disabled = true;
            button.textContent = 'Connecting…';
            document.getElementById('bluetooth-status').textContent = 'Pairing and connecting…';
            fetch(apiBase + '/api/bluetooth/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({address: address})
            })
                .then(async response => {
                    const data = await response.json();
                    if (!response.ok || !data.success) throw new Error(data.error || 'Connection failed');
                    document.querySelectorAll('.output-btn').forEach(item => item.classList.remove('active'));
                    document.getElementById('out-bluetooth').classList.remove('disabled');
                    document.getElementById('out-bluetooth').classList.add('active');
                    showToast('Bluetooth connected and set as default');
                    loadBluetoothDevices();
                })
                .catch(error => {
                    showToast(error.message);
                    document.getElementById('bluetooth-status').textContent = error.message;
                    button.disabled = false;
                    button.textContent = 'Connect';
                });
        }
        
        function setTheme(themeName) {
            applyTheme(themeName);
            fetch(apiBase + '/api/theme/' + themeName).then(() => {
                showToast('Theme updated');
            });
        }

        function saveWeatherLocation() {
            const location = document.getElementById('weather-location').value.trim();
            if (!location) {
                showToast('Enter a town, city, or postcode');
                return;
            }
            showToast('Finding weather location…');
            fetch(apiBase + '/api/weather/location', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({location: location})
            }).then(async response => {
                const data = await response.json();
                if (!response.ok || !data.success) {
                    throw new Error(data.error || 'Location update failed');
                }
                document.getElementById('weather-location').value = data.weather_name;
                document.getElementById('weather-location-current').textContent =
                    data.weather_name + (data.weather_country ? ', ' + data.weather_country : '');
                showToast('Weather location updated');
            }).catch(error => showToast(error.message));
        }

        function previewBrightness(value) {
            document.getElementById('brightness-value').textContent = value + '%';
        }

        function saveDisplaySettings() {
            const brightness = parseInt(document.getElementById('brightness-slider').value);
            const autoDimMinutes = parseInt(document.getElementById('auto-dim-minutes').value);
            const dimBrightness = parseInt(document.getElementById('dim-brightness-slider').value);
            fetch(apiBase + '/api/display/settings', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    brightness: brightness,
                    autoDimEnabled: autoDimEnabled,
                    autoDimMinutes: autoDimMinutes,
                    dimBrightness: dimBrightness
                })
            }).then(async response => {
                const data = await response.json();
                if (!response.ok || !data.success) {
                    throw new Error(data.error || 'Display update failed');
                }
                showToast('Display settings saved');
            }).catch(error => showToast(error.message));
        }

        function toggleAutoDim() {
            autoDimEnabled = !autoDimEnabled;
            document.getElementById('auto-dim-toggle').classList.toggle(
                'active', autoDimEnabled
            );
            saveDisplaySettings();
        }

        function requestSafeShutdown() {
            if (!confirm('Safely shut down TCRADIOS now?')) return;
            if (!confirm('The radio will turn off. Continue?')) return;
            fetch(apiBase + '/api/system/shutdown', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({confirm: 'SHUTDOWN'})
            }).then(async response => {
                const data = await response.json();
                if (!response.ok || !data.success) {
                    throw new Error(data.error || 'Shutdown failed');
                }
                showToast('Shutting down safely…');
            }).catch(error => showToast(error.message));
        }
        
        function showThemeModal() {
            switchView('audio');
            document.querySelectorAll('.nav-item')[4].classList.add('active');
            loadBluetoothDevices();
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
        device_settings=device_settings.as_dict(),
        outputs=outputs_data,
        current_output=audio_manager.current_output
    )

@app.route('/simulator')
def touchscreen_simulator():
    simulator_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'touchscreen_simulator.html'
    )
    try:
        with open(simulator_path, 'r', encoding='utf-8') as simulator_file:
            return Response(simulator_file.read(), mimetype='text/html')
    except OSError as error:
        return Response(
            f"Touchscreen simulator unavailable: {error}",
            status=404,
            mimetype='text/plain'
        )

@app.route('/manifest.json')
def manifest():
    return Response(json.dumps({
        "short_name": "TC RADIOS",
        "name": "TC RADIOS Remote",
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
            skip_playback(1)
        elif action == 'prev':
            skip_playback(-1)
        elif action == 'volup':
            apply_live_volume(min(vol_level + 10, 100))
        elif action == 'voldown':
            apply_live_volume(max(vol_level - 10, 0))
        elif action == 'toggle':
            player.pause()
        elif action == 'mute':
            apply_live_volume(0 if vol_level > 0 else last_unmuted_volume)
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
        apply_live_volume(level)
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

LISTEN_ALONG_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Listen along • TCRADIOS</title>
<style>
body { margin:0; min-height:100vh; background:#000; color:#fff;
  font-family:'TCRTamil','Noto Sans Tamil',system-ui,sans-serif;
  display:flex; align-items:center; justify-content:center; text-align:center;
  padding:24px; }
.card { width:min(420px,100%); }
.kicker { letter-spacing:.18em; font-size:12px; color:#e6ebf6; margin-bottom:12px; }
h1 { font-size:28px; margin:0 0 8px; }
.now { color:#e6ebf6; min-height:24px; margin-bottom:22px; }
audio { width:100%; margin:18px 0; }
a { color:#7ed4ff; }
.err { color:#ffb347; font-size:14px; margin-top:12px; }
</style>
</head>
<body>
<div class="card">
  <div class="kicker">LISTEN ALONG</div>
  <h1 id="name">TCRADIOS</h1>
  <div class="now" id="now"></div>
  <audio id="player" controls autoplay></audio>
  <div class="err" id="err"></div>
  <p><a id="stream" href="#">Open this station</a> · <a href="/">Full remote</a></p>
</div>
<script>
async function loadListen() {
  const res = await fetch('/api/listen');
  const data = await res.json();
  document.getElementById('name').textContent = data.name || 'TCRADIOS';
  document.getElementById('now').textContent = data.now_playing || '';
  const player = document.getElementById('player');
  const err = document.getElementById('err');
  const stream = document.getElementById('stream');
  if (data.url) stream.href = data.url;
  if (data.url && player.dataset.src !== data.url) {
    player.dataset.src = data.url;
    player.src = data.url;
    player.play().catch(() => {
      err.textContent = 'This station is playing on TCRADIOS. Tap play, or open the stream.';
    });
  }
  if (!data.url) err.textContent = 'No stream is ready yet.';
}
loadListen();
setInterval(loadListen, 8000);
</script>
</body>
</html>
"""

@app.route('/listen')
def listen_along():
    return Response(LISTEN_ALONG_PAGE, mimetype='text/html')

@app.route('/api/listen')
def api_listen():
    try:
        station = stations[current_idx]
        playing = meta_text or station.get('name', '')
    except Exception:
        station = {}
        playing = ''
    return jsonify({
        'name': station.get('name', 'TCRADIOS'),
        'url': station.get('url', ''),
        'now_playing': playing,
        'genre': station.get('genre', ''),
        'youtube': bool(station.get('youtube_id')),
    })

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

@app.route('/api/weather/location', methods=['GET', 'POST'])
def weather_location():
    global last_weather_update
    if request.method == 'GET':
        return jsonify({'success': True, **device_settings.as_dict()})

    try:
        data = request.get_json(silent=True) or {}
        query = str(data.get('location', '')).strip()
        if not query:
            return jsonify({
                'success': False,
                'error': 'Enter a town, city, or postcode'
            }), 400

        response = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={
                'name': query,
                'count': 1,
                'language': 'en',
                'format': 'json'
            },
            timeout=8
        )
        response.raise_for_status()
        results = response.json().get('results', [])
        if not results:
            return jsonify({
                'success': False,
                'error': 'Location not found'
            }), 404

        location = results[0]
        device_settings.weather_name = str(location.get('name', query))[:60]
        device_settings.weather_country = str(
            location.get('country', '')
        )[:60]
        device_settings.weather_latitude = float(location['latitude'])
        device_settings.weather_longitude = float(location['longitude'])
        device_settings.save()
        last_weather_update = 0
        return jsonify({
            'success': True,
            **device_settings.as_dict()
        })
    except (KeyError, ValueError, requests.RequestException) as error:
        return jsonify({'success': False, 'error': str(error)}), 502

@app.route('/api/display/settings', methods=['GET', 'POST'])
def display_settings():
    global last_interaction_time
    if request.method == 'GET':
        return jsonify({'success': True, **device_settings.as_dict()})

    try:
        data = request.get_json(silent=True) or {}
        if 'brightness' in data:
            device_settings.brightness = max(
                10, min(100, int(data['brightness']))
            )
        if 'autoDimEnabled' in data:
            device_settings.auto_dim_enabled = bool(data['autoDimEnabled'])
        if 'autoDimMinutes' in data:
            device_settings.auto_dim_minutes = max(
                1, min(60, int(data['autoDimMinutes']))
            )
        if 'dimBrightness' in data:
            device_settings.dim_brightness = max(
                5, min(50, int(data['dimBrightness']))
            )
        device_settings.save()
        last_interaction_time = time.time()
        device_settings.set_hardware_brightness(device_settings.brightness)
        return jsonify({
            'success': True,
            **device_settings.as_dict()
        })
    except (ValueError, TypeError) as error:
        return jsonify({'success': False, 'error': str(error)}), 400

def perform_safe_shutdown():
    time.sleep(1)
    try:
        player.stop()
    except Exception:
        pass
    result = subprocess.run(
        ['sudo', '-n', '/usr/bin/systemctl', 'poweroff'],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Safe shutdown failed: {result.stderr.strip()}")

@app.route('/api/system/shutdown', methods=['POST'])
def safe_shutdown():
    data = request.get_json(silent=True) or {}
    if data.get('confirm') != 'SHUTDOWN':
        return jsonify({
            'success': False,
            'error': 'Shutdown confirmation is required'
        }), 400
    threading.Thread(target=perform_safe_shutdown, daemon=True).start()
    return jsonify({'success': True, 'message': 'Shutting down safely'})

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

@app.route('/api/bluetooth/devices')
def bluetooth_devices():
    try:
        return jsonify({
            'success': True,
            'devices': audio_manager.get_bluetooth_devices()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 503

@app.route('/api/bluetooth/scan', methods=['POST'])
def bluetooth_scan():
    try:
        return jsonify({
            'success': True,
            'devices': audio_manager.scan_bluetooth()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 503

@app.route('/api/bluetooth/connect', methods=['POST'])
def bluetooth_connect():
    try:
        data = request.get_json(silent=True) or {}
        address = data.get('address', '')
        sink_name = audio_manager.connect_bluetooth(address)
        return jsonify({
            'success': True,
            'address': address.upper(),
            'sink': sink_name,
            'output': 'bluetooth'
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 503

_ytdlp_extract_args = None

def ytdlp_error_text(result):
    text = ''
    if result is not None:
        text = f"{result.stderr or ''}\n{result.stdout or ''}"
    lines = [
        line.strip() for line in text.splitlines()
        if line.strip() and not line.strip().startswith('{')
    ]
    message = lines[-1] if lines else 'YouTube request failed'
    return message[:240]

def ytdlp_extract_args():
    """Flags a current yt-dlp needs to solve YouTube playback challenges."""
    global _ytdlp_extract_args
    if _ytdlp_extract_args is not None:
        return list(_ytdlp_extract_args)
    args = []
    try:
        probe = subprocess.run(
            ['yt-dlp', '--help'],
            capture_output=True,
            text=True,
            timeout=15,
        )
        help_text = f'{probe.stdout}\n{probe.stderr}'
        if '--js-runtimes' in help_text and shutil.which('node'):
            args.extend(['--js-runtimes', 'node'])
        if '--remote-components' in help_text:
            args.extend(['--remote-components', 'ejs:github'])
        _ytdlp_extract_args = args
    except (OSError, subprocess.TimeoutExpired):
        return []
    return list(args)

def run_ytdlp(args, timeout):
    cmd = ['yt-dlp', '--no-warnings', '--no-progress', *args]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return None, 'yt-dlp is not installed'
    except subprocess.TimeoutExpired:
        return None, 'YouTube request timed out'
    stdout = (result.stdout or '').strip()
    if result.returncode != 0 or not stdout:
        return None, ytdlp_error_text(result)
    return stdout, None

def format_youtube_duration(value):
    if isinstance(value, str) and value.strip():
        return value.strip()
    try:
        total = int(float(value))
    except (TypeError, ValueError):
        return '0:00'
    if total < 0:
        return '0:00'
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f'{hours}:{minutes:02d}:{seconds:02d}'
    return f'{minutes}:{seconds:02d}'

def youtube_result_from_info(video, fallback_id=''):
    video_id = str(video.get('id') or fallback_id or '').strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{6,32}', video_id):
        url = video.get('url') or video.get('webpage_url') or ''
        match = re.search(r'(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{6,32})', str(url))
        video_id = match.group(1) if match else ''
    thumbnail = video.get('thumbnail') or ''
    if not thumbnail:
        for item in reversed(video.get('thumbnails') or []):
            if isinstance(item, dict) and item.get('url'):
                thumbnail = item['url']
                break
    if not thumbnail and video_id:
        thumbnail = f'https://i.ytimg.com/vi/{video_id}/mqdefault.jpg'
    duration = video.get('duration_string')
    if not duration:
        if video.get('is_live') or video.get('live_status') == 'is_live':
            duration = 'LIVE'
        else:
            duration = format_youtube_duration(video.get('duration'))
    return {
        'id': video_id,
        'title': video.get('title') or 'Unknown',
        'uploader': video.get('uploader') or video.get('channel') or video.get('uploader_id') or 'Unknown',
        'duration': duration,
        'thumbnail': thumbnail,
    }

def parse_youtube_payload(stdout):
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        videos = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                videos.append(youtube_result_from_info(item))
        return [video for video in videos if video['id']]
    if isinstance(payload, dict) and isinstance(payload.get('entries'), list):
        videos = [
            youtube_result_from_info(item)
            for item in payload['entries']
            if isinstance(item, dict)
        ]
        return [video for video in videos if video['id']]
    if isinstance(payload, dict):
        video = youtube_result_from_info(payload)
        return [video] if video['id'] else []
    return []

def search_youtube(query):
    query = str(query or '').strip()
    if not query:
        return [], 'Empty query'
    video_id = ''
    if 'youtube.com' in query or 'youtu.be' in query:
        match = re.search(r'(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{6,32})', query)
        video_id = match.group(1) if match else ''
    if video_id:
        stdout, err = run_ytdlp([
            *ytdlp_extract_args(),
            '--dump-single-json',
            '--skip-download',
            '--no-playlist',
            f'https://www.youtube.com/watch?v={video_id}',
        ], timeout=30)
        if not stdout:
            return [], err or 'Could not open that YouTube link'
        return parse_youtube_payload(stdout), None
    # Metadata only. --extract-audio used to download every hit, so search
    # was capped at 8. Flat metadata can return a longer list safely.
    stdout, err = run_ytdlp([
        '--dump-single-json',
        '--flat-playlist',
        '--skip-download',
        '--no-warnings',
        f'ytsearch{YOUTUBE_SEARCH_COUNT}:{query}',
    ], timeout=40)
    if not stdout:
        return [], err or 'YouTube search failed'
    return parse_youtube_payload(stdout), None

def youtube_audio_url(video_id, timeout=40):
    if not re.fullmatch(r'[A-Za-z0-9_-]{6,32}', str(video_id or '')):
        return '', 'No video ID'
    stdout, err = run_ytdlp([
        *ytdlp_extract_args(),
        '-f', 'bestaudio/best',
        '--get-url',
        '--no-playlist',
        f'https://www.youtube.com/watch?v={video_id}',
    ], timeout=timeout)
    if stdout:
        for line in stdout.splitlines():
            candidate = line.strip()
            if candidate.startswith('http'):
                return candidate, None
    return '', err or 'Could not extract audio URL'

# YouTube API Routes
@app.route('/api/youtube/search', methods=['POST'])
def youtube_search():
    global youtube_results_cache
    try:
        data = request.get_json(silent=True) or {}
        videos, err = search_youtube(data.get('query', ''))
        if err and not videos:
            status = 400 if err == 'Empty query' else 502
            return jsonify({'success': False, 'error': err}), status
        youtube_results_cache = videos
        return jsonify({'success': True, 'results': videos})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/youtube/play', methods=['POST'])
def youtube_play():
    try:
        data = request.get_json(silent=True) or {}
        video_id = str(data.get('video_id', '')).strip()
        title = str(data.get('title') or 'YouTube Audio')
        audio_url, err = youtube_audio_url(video_id)
        if not audio_url:
            return jsonify({'success': False, 'error': err}), 502
        remember_youtube_queue(video_id, title)
        play_youtube_station(video_id, title, audio_url)
        return jsonify({'success': True, 'message': f'Playing: {title}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/static/<path:filename>')
def serve_static(filename):
    if filename == 'NotoSansTamil-Regular.ttf':
        font_file = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'fonts',
            'NotoSansTamil-Regular.ttf',
        )
        if os.path.isfile(font_file):
            with open(font_file, 'rb') as handle:
                return Response(handle.read(), mimetype='font/ttf')
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
pygame.mouse.set_visible(False)
try:
    pygame.mouse.set_cursor((8, 8), (0, 0), (0,) * 8, (0,) * 8)
except Exception:
    pass

# Layout is authored at 320x480 and filled to the live screen. Positions
# and boxes follow X/Y so the 7-inch panel is used fully. Circles that
# must sit on that layout (glow, artwork) are drawn as matching ellipses.
BASE_W, BASE_H = 320, 480
OFFICIAL_7_W, OFFICIAL_7_H = 720, 1280
_Rect = pygame.Rect

def _open_touchscreen():
    flags = pygame.FULLSCREEN | pygame.NOFRAME
    try:
        surface = pygame.display.set_mode((0, 0), flags)
        width, height = surface.get_size()
        if width >= 640 and height >= 480:
            return surface, width, height
    except Exception:
        pass
    try:
        surface = pygame.display.set_mode((OFFICIAL_7_W, OFFICIAL_7_H), flags)
        return surface, surface.get_width(), surface.get_height()
    except Exception:
        surface = pygame.display.set_mode((OFFICIAL_7_W, OFFICIAL_7_H))
        return surface, surface.get_width(), surface.get_height()

screen, SCREEN_W, SCREEN_H = _open_touchscreen()
SCALE_X = SCREEN_W / float(BASE_W)
SCALE_Y = SCREEN_H / float(BASE_H)
SCALE = min(SCALE_X, SCALE_Y)

def X(value):
    return int(round(value * SCALE_X))

def Y(value):
    return int(round(value * SCALE_Y))

def S(value):
    return max(1, int(round(value * SCALE)))

def R(x, y, w, h):
    return _Rect(X(x), Y(y), max(1, X(w)), max(1, Y(h)))

def XY(x, y):
    return (X(x), Y(y))

def E(cx, cy, radius):
    return R(cx - radius, cy - radius, radius * 2, radius * 2)

print(f"Touchscreen {SCREEN_W}x{SCREEN_H} (fill {SCALE_X:.2f}x{SCALE_Y:.2f})")

# --- UNICODE FONT SETUP (Tamil Support) ---
TAMIL_RANGE = range(0x0B80, 0x0BFF + 1)
APP_FONT_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "fonts")
TAMIL_FONT_CANDIDATES = [
    os.path.join(APP_FONT_DIR, "NotoSansTamil-Regular.ttf"),
    "/usr/local/share/fonts/tcradios/NotoSansTamil-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansTamil-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansTamil-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansTamilUI-Regular.ttf",
    "/usr/share/fonts/truetype/lohit-tamil/Lohit-Tamil.ttf",
    "/usr/share/fonts/truetype/lohit-taml/Lohit-Tamil.ttf",
    "/usr/share/fonts/truetype/samyak/Samyak-Tamil.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansTamil-Regular.otf",
]

def first_existing_font(paths):
    for path in paths:
        if path and os.path.isfile(path):
            return path
    return None

def latin_font_path(bold=False):
    if bold:
        return first_existing_font([
            '/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
            '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        ])
    return first_existing_font([
        '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
    ])

def font_supports_tamil(path):
    if not path or not os.path.isfile(path):
        return False
    sample = '\u0b95'
    try:
        font = pygame.font.Font(path, 18)
        metrics = font.metrics(sample)
        return bool(metrics and metrics[0] and metrics[0][4] > 0)
    except Exception:
        pass
    try:
        if not PIL_AVAILABLE:
            return True
        font = ImageFont.truetype(path, 18)
        probe = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
        box = probe.textbbox((0, 0), sample, font=font)
        return box[2] > box[0]
    except Exception:
        return False

_TAMIL_FONT_UNSET = object()
_TAMIL_FONT_CACHE = _TAMIL_FONT_UNSET

def tamil_font_path():
    global _TAMIL_FONT_CACHE
    if _TAMIL_FONT_CACHE is not _TAMIL_FONT_UNSET:
        return _TAMIL_FONT_CACHE
    found = []
    for path in TAMIL_FONT_CANDIDATES:
        if path and os.path.isfile(path) and path not in found:
            found.append(path)
    try:
        import glob
        for path in glob.glob('/usr/share/fonts/**/*[Tt]amil*.ttf', recursive=True):
            if path not in found:
                found.append(path)
    except Exception:
        pass
    chosen = None
    for path in found:
        if font_supports_tamil(path):
            chosen = path
            break
    if chosen is None and found:
        chosen = found[0]
    _TAMIL_FONT_CACHE = chosen
    return chosen

def load_pygame_font(path, size):
    if path:
        try:
            return pygame.font.Font(path, size)
        except Exception:
            pass
    try:
        return pygame.font.SysFont(
            "DejaVu Sans,Liberation Sans,FreeSans,Noto Sans,sans-serif",
            size,
            bold=size >= 16,
        )
    except Exception:
        return pygame.font.Font(None, size)

def contains_tamil(text):
    return any(ord(char) in TAMIL_RANGE for char in str(text or ''))

def is_tamil_combiner(char):
    code = ord(char)
    return (
        char in '\u200c\u200d'
        or code in (0x0B82, 0x0B83, 0x0BD7)
        or 0x0BBE <= code <= 0x0BCD
    )

def is_tamil_consonant(char):
    return '\u0b95' <= char <= '\u0bb9'

def tamil_visual_order(text):
    """Put left-side Tamil vowels in front when the font cannot shape them."""
    text = str(text or '')
    if not contains_tamil(text):
        return text
    left_vowels = {'\u0bc6', '\u0bc7', '\u0bc8'}
    split_vowels = {
        '\u0bca': ('\u0bc6', '\u0bbe'),
        '\u0bcb': ('\u0bc7', '\u0bbe'),
        '\u0bcc': ('\u0bc6', '\u0bb3'),
    }
    result = []
    index = 0
    while index < len(text):
        char = text[index]
        if not (ord(char) in TAMIL_RANGE or char in '\u200c\u200d'):
            result.append(char)
            index += 1
            continue
        cluster = [char]
        index += 1
        while index < len(text):
            nxt = text[index]
            if is_tamil_combiner(nxt):
                cluster.append(nxt)
                index += 1
                continue
            if cluster[-1] == '\u0bcd' and is_tamil_consonant(nxt):
                cluster.append(nxt)
                index += 1
                continue
            break
        vowel = cluster[-1]
        base = ''.join(cluster[:-1])
        if vowel in left_vowels and base:
            result.append(vowel + base)
        elif vowel in split_vowels and base:
            left, right = split_vowels[vowel]
            result.append(left + base + right)
        else:
            result.append(''.join(cluster))
    return ''.join(result)

def sanitize_text(text):
    """Clean text for display - keeps Unicode characters including Tamil"""
    if not text:
        return "Unknown"
    text = str(text)
    text = ''.join(char for char in text if ord(char) >= 32 or char == '\n')
    return text.strip()

def style_now_playing(text):
    text = sanitize_text(text)
    if contains_tamil(text):
        return text
    return text.upper()

_TAMIL_INDEPENDENT = {
    '\u0b85': 'a', '\u0b86': 'aa', '\u0b87': 'i', '\u0b88': 'ii',
    '\u0b89': 'u', '\u0b8a': 'uu', '\u0b8e': 'e', '\u0b8f': 'ee',
    '\u0b90': 'ai', '\u0b92': 'o', '\u0b93': 'oo', '\u0b94': 'au',
}
_TAMIL_CONSONANT = {
    '\u0b95': 'k', '\u0b99': 'ng', '\u0b9a': 'c', '\u0b9c': 'j',
    '\u0b9e': 'nj', '\u0b9f': 't', '\u0ba3': 'n', '\u0ba4': 'th',
    '\u0ba8': 'n', '\u0ba9': 'n', '\u0baa': 'p', '\u0bae': 'm',
    '\u0baf': 'y', '\u0bb0': 'r', '\u0bb1': 'r', '\u0bb2': 'l',
    '\u0bb3': 'l', '\u0bb4': 'zh', '\u0bb5': 'v', '\u0bb6': 'sh',
    '\u0bb7': 'sh', '\u0bb8': 's', '\u0bb9': 'h',
}
_TAMIL_VOWEL_SIGN = {
    '\u0bbe': 'aa', '\u0bbf': 'i', '\u0bc0': 'ii', '\u0bc1': 'u',
    '\u0bc2': 'uu', '\u0bc6': 'e', '\u0bc7': 'ee', '\u0bc8': 'ai',
    '\u0bca': 'o', '\u0bcb': 'oo', '\u0bcc': 'au',
}

def transliterate_tamil(text):
    """Latin letters under a Tamil now-playing line."""
    text = str(text or '')
    if not contains_tamil(text):
        return ''
    out = []
    index = 0
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ''
        if char in _TAMIL_INDEPENDENT:
            out.append(_TAMIL_INDEPENDENT[char])
            index += 1
            continue
        if char in _TAMIL_CONSONANT:
            root = _TAMIL_CONSONANT[char]
            if nxt == '\u0bcd':
                out.append(root)
                index += 2
                continue
            if nxt in _TAMIL_VOWEL_SIGN:
                out.append(root + _TAMIL_VOWEL_SIGN[nxt])
                index += 2
                continue
            out.append(root + 'a')
            index += 1
            continue
        if char in _TAMIL_VOWEL_SIGN or char == '\u0bcd':
            index += 1
            continue
        if char == '\u0b82':
            out.append('m')
            index += 1
            continue
        if char == '\u0b83':
            out.append('h')
            index += 1
            continue
        out.append(char)
        index += 1
    return re.sub(r'\s+', ' ', ''.join(out)).strip()

def station_initials(name):
    name = sanitize_text(name)
    if not contains_tamil(name):
        return name[:2].upper()
    index = 0
    while index < len(name) and name[index].isspace():
        index += 1
    if index >= len(name):
        return name[:1]
    cluster = name[index]
    index += 1
    while index < len(name):
        nxt = name[index]
        if is_tamil_combiner(nxt):
            cluster += nxt
            index += 1
            continue
        if cluster.endswith('\u0bcd') and is_tamil_consonant(nxt):
            cluster += nxt
            index += 1
            continue
        break
    return tamil_visual_order(cluster)

def truncate_display(text, length, tail=False):
    text = sanitize_text(text)
    if len(text) <= length:
        return text
    if not contains_tamil(text):
        return ("…" + text[-(length - 1):]) if tail else (text[:length - 1] + "…")
    if tail:
        start = max(0, len(text) - (length - 1))
        while start < len(text) and is_tamil_combiner(text[start]):
            start += 1
        return "…" + text[start:]
    end = length - 1
    while end > 0 and is_tamil_combiner(text[end]):
        end -= 1
    return text[:end] + "…"

def render_pil_text(font_path, size, text, color, use_raqm=False):
    if not PIL_AVAILABLE or not font_path:
        return None
    try:
        layout = getattr(getattr(ImageFont, 'Layout', None), 'RAQM', None)
        if use_raqm and layout is None:
            return None
        font = (
            ImageFont.truetype(font_path, size, layout_engine=layout)
            if use_raqm and layout is not None
            else ImageFont.truetype(font_path, size)
        )
        probe = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
        box = probe.textbbox((0, 0), text, font=font)
        width = max(1, box[2] - box[0])
        height = max(1, box[3] - box[1])
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        fill = (*color, 255) if len(color) == 3 else color
        ImageDraw.Draw(image).text((-box[0], -box[1]), text, font=font, fill=fill)
        return pygame.image.fromstring(image.tobytes(), image.size, 'RGBA')
    except Exception:
        return None

def split_script_runs(text):
    """Keep Tamil syllables together; draw Latin with a Latin font."""
    runs = []
    kind = None
    chunk = []
    for char in str(text or ''):
        tamil_char = (
            ord(char) in TAMIL_RANGE
            or char in '\u200c\u200d'
            or (kind == 'ta' and is_tamil_combiner(char))
        )
        next_kind = 'ta' if tamil_char else 'lt'
        if next_kind != kind and chunk:
            runs.append((kind, ''.join(chunk)))
            chunk = []
        kind = next_kind
        chunk.append(char)
    if chunk:
        runs.append((kind, ''.join(chunk)))
    return runs

def stitch_text_surfaces(parts, background=None):
    parts = [part for part in parts if part is not None]
    if not parts:
        surface = pygame.Surface((1, 1), pygame.SRCALPHA)
        return surface
    width = sum(part.get_width() for part in parts)
    height = max(part.get_height() for part in parts)
    surface = pygame.Surface((max(1, width), max(1, height)), pygame.SRCALPHA)
    if background:
        surface.fill(background)
    x = 0
    for part in parts:
        surface.blit(part, (x, (height - part.get_height()) // 2))
        x += part.get_width()
    return surface

def render_tamil_run(font_path, pygame_font, size, text, color, antialias, background):
    """Draw Tamil from an explicit Tamil file. SDL_ttf often shows boxes."""
    if not text:
        return None
    display = tamil_visual_order(text)
    try:
        import pygame.freetype
        font = pygame.freetype.Font(font_path, size)
        font.kerning = True
        font.pad = True
        surface, _rect = font.render(display, color)
        if surface is not None and surface.get_width() > 1:
            return surface.convert_alpha()
    except Exception:
        pass
    surface = render_pil_text(font_path, size, display, color, use_raqm=False)
    if surface is not None:
        return surface
    surface = render_pil_text(font_path, size, text, color, use_raqm=True)
    if surface is not None:
        return surface
    if pygame_font is not None:
        return pygame_font.render(display, antialias, color, background)
    return None

class UiFont:
    """Latin font plus a dedicated Tamil font, mixed in the same label."""

    def __init__(self, size, bold=False):
        self.size = size
        self.latin_path = latin_font_path(bold)
        self.tamil_path = tamil_font_path()
        self.latin = load_pygame_font(self.latin_path, size)
        self.tamil = load_pygame_font(self.tamil_path, size)
        self._shaped_cache = {}

    def render(self, text, antialias, color, background=None):
        text = str(text or '')
        if not text:
            return self.latin.render('', antialias, color, background)
        if not contains_tamil(text):
            return self.latin.render(text, antialias, color, background)
        cache_key = (text, tuple(color), background)
        cached = self._shaped_cache.get(cache_key)
        if cached is not None:
            return cached
        parts = []
        for kind, chunk in split_script_runs(text):
            if kind == 'ta':
                parts.append(render_tamil_run(
                    self.tamil_path, self.tamil, self.size,
                    chunk, color, antialias, background
                ))
            else:
                parts.append(self.latin.render(chunk, antialias, color, background))
        shaped = stitch_text_surfaces(parts, background)
        if len(self._shaped_cache) > 80:
            self._shaped_cache.clear()
        self._shaped_cache[cache_key] = shaped
        return shaped

    def size(self, text):
        return self.render(text, True, (255, 255, 255)).get_size()

    def get_height(self):
        return self.latin.get_height()

def get_unicode_font(size, bold=False):
    return UiFont(size, bold=bold)

# Load Unicode fonts
try:
    f_lg = get_unicode_font(S(24), bold=True)
    f_sm = get_unicode_font(S(16), bold=True)
    f_xl = get_unicode_font(S(80), bold=True)
    f_med = get_unicode_font(S(24), bold=True)
    f_tiny = get_unicode_font(S(12), bold=True)
    f_weather = get_unicode_font(S(42), bold=True)
    tamil_loaded = tamil_font_path() or 'missing'
    print(f"Unicode fonts loaded. Tamil font: {tamil_loaded}")
    if tamil_loaded == 'missing':
        print("Tamil names will show as boxes until NotoSansTamil-Regular.ttf is installed.")
except Exception as e:
    print(f"Font error: {e}, using defaults")
    f_lg = pygame.font.Font(None, S(24))
    f_sm = pygame.font.Font(None, S(16))
    f_xl = pygame.font.Font(None, S(80))
    f_med = pygame.font.Font(None, S(24))
    f_tiny = pygame.font.Font(None, S(12))
    f_weather = pygame.font.Font(None, S(42))

# Cover application initialization with the same branding as the boot splash.
screen.fill((0, 0, 0))
splash_title_font = get_unicode_font(S(38), bold=True)
splash_subtitle_font = get_unicode_font(S(16))
splash_title = splash_title_font.render("TCRADIOS", True, (235, 242, 255))
splash_subtitle = splash_subtitle_font.render("by JayathaSoft", True, (214, 224, 240))
screen.blit(splash_title, splash_title.get_rect(center=XY(160, 218)))
screen.blit(splash_subtitle, splash_subtitle.get_rect(center=XY(160, 257)))
pygame.draw.line(screen, (38, 150, 210), XY(100, 282), XY(220, 282), S(2))
pygame.display.flip()
pygame.mouse.set_visible(False)
splash_started_at = time.time()
try:
    subprocess.run(
        ["plymouth", "quit"],
        timeout=2,
        capture_output=True,
        check=False,
    )
except Exception:
    pass

def release_display_and_exit(_signum, _frame):
    # Exit immediately so a fullscreen window cannot hold up reboot.
    try:
        save_playback_state(force=True)
    except Exception:
        pass
    try:
        pygame.display.quit()
        pygame.quit()
    except Exception:
        pass
    os._exit(0)

signal.signal(signal.SIGTERM, release_display_and_exit)
signal.signal(signal.SIGINT, release_display_and_exit)

UI_BG_TOP = (0, 0, 0)
UI_BG_BOTTOM = (7, 7, 10)
UI_SURFACE = (15, 18, 25)
UI_SURFACE_RAISED = (24, 28, 38)
UI_TEXT = (255, 255, 255)
UI_MUTED = (230, 234, 244)
UI_BLUE = (50, 205, 255)
UI_PURPLE = (145, 92, 255)
UI_PINK = (255, 83, 148)
UI_AMBER = (255, 193, 74)
UI_GREEN = (54, 222, 159)

def mix_colors(first, second, amount):
    return tuple(
        int(first[i] + (second[i] - first[i]) * amount)
        for i in range(3)
    )

def ensure_bright(color, minimum=125):
    luminance = color[0] * 0.2126 + color[1] * 0.7152 + color[2] * 0.0722
    if luminance >= minimum:
        return color
    amount = (minimum - luminance) / max(1, 255 - luminance)
    return mix_colors(color, (255, 255, 255), amount)

def create_ui_background():
    background = pygame.Surface((SCREEN_W, SCREEN_H))
    for y in range(SCREEN_H):
        ratio = y / max(1, SCREEN_H - 1)
        color = tuple(
            int(UI_BG_TOP[i] + (UI_BG_BOTTOM[i] - UI_BG_TOP[i]) * ratio)
            for i in range(3)
        )
        pygame.draw.line(background, color, (0, y), (SCREEN_W - 1, y))

    glow = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    pygame.draw.ellipse(glow, (*UI_BLUE, 28), E(292, 108, 120))
    pygame.draw.ellipse(glow, (*UI_PURPLE, 26), E(12, 360, 140))
    pygame.draw.ellipse(glow, (*UI_AMBER, 16), E(160, 24, 90))
    background.blit(glow, (0, 0))
    return background

def refresh_ui_palette():
    global UI_BG_TOP, UI_BG_BOTTOM, UI_SURFACE, UI_SURFACE_RAISED
    global UI_TEXT, UI_MUTED, UI_BLUE, UI_PURPLE, UI_AMBER, UI_PINK, UI_GREEN
    global ui_background, ui_palette_theme

    UI_BLUE = ensure_bright(current_theme.pygame_primary, 155)
    UI_PURPLE = ensure_bright(current_theme.pygame_secondary, 145)
    UI_AMBER = ensure_bright(current_theme.pygame_accent, 155)
    UI_PINK = ensure_bright(mix_colors((255, 78, 160), UI_PURPLE, 0.22), 155)
    UI_GREEN = ensure_bright(mix_colors((52, 220, 150), UI_BLUE, 0.22), 155)
    UI_TEXT = (255, 255, 255)
    UI_BG_TOP = (0, 0, 0)
    UI_BG_BOTTOM = mix_colors((0, 0, 0), UI_BLUE, 0.08)
    UI_SURFACE = mix_colors((10, 12, 16), UI_BLUE, 0.12)
    UI_SURFACE_RAISED = mix_colors((16, 18, 24), UI_BLUE, 0.2)
    UI_MUTED = (230, 234, 244)
    ui_background = create_ui_background()
    ui_palette_theme = current_theme.name

def _srgb_channel(value):
    scaled = value / 255.0
    if scaled <= 0.04045:
        return scaled / 12.92
    return ((scaled + 0.055) / 1.055) ** 2.4

def relative_luminance(color):
    red, green, blue = (_srgb_channel(channel) for channel in color[:3])
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue

def color_luminance(color):
    return relative_luminance(color) * 255

def contrast_ratio(first, second):
    light = max(relative_luminance(first), relative_luminance(second))
    dark = min(relative_luminance(first), relative_luminance(second))
    return (light + 0.05) / (dark + 0.05)

def contrasting_text(background):
    return (16, 18, 24) if relative_luminance(background) > 0.32 else (255, 255, 255)

def contrasting_muted(background):
    if relative_luminance(background) > 0.32:
        return (42, 46, 58)
    return (230, 234, 244)

def ink_on(background, preferred=None, minimum=4.5):
    if preferred is not None and contrast_ratio(preferred, background) >= minimum:
        return preferred
    return contrasting_text(background)

def muted_ink_on(background, preferred=None, minimum=3.5):
    if preferred is not None and contrast_ratio(preferred, background) >= minimum:
        return preferred
    return contrasting_muted(background)

def draw_centered_text(surface, font, text, color, rect):
    rendered = font.render(text, True, color)
    surface.blit(rendered, rendered.get_rect(center=rect.center))
    return rendered

try:
    import pygame.gfxdraw
    _GFXDRAW = True
except ImportError:
    _GFXDRAW = False

def draw_smooth_circle(surface, center, radius, color):
    x, y = int(center[0]), int(center[1])
    radius = max(1, int(radius))
    if _GFXDRAW:
        pygame.gfxdraw.filled_circle(surface, x, y, radius, color)
        pygame.gfxdraw.aacircle(surface, x, y, radius, color)
    else:
        pygame.draw.circle(surface, color, (x, y), radius)

def draw_round_cap_line(surface, start, end, color, width):
    pygame.draw.line(surface, color, start, end, width)
    cap = max(1, int(width / 2))
    draw_smooth_circle(surface, start, cap, color)
    draw_smooth_circle(surface, end, cap, color)

def draw_vector_icon(surface, center, kind, color, radius=10, width=4):
    x, y = center
    if kind == "minus":
        draw_round_cap_line(surface, (x - radius, y), (x + radius, y), color, width)
    elif kind == "plus":
        draw_round_cap_line(surface, (x - radius, y), (x + radius, y), color, width)
        draw_round_cap_line(surface, (x, y - radius), (x, y + radius), color, width)
    elif kind == "close":
        inset = int(radius * 0.75)
        draw_round_cap_line(
            surface, (x - inset, y - inset), (x + inset, y + inset), color, width
        )
        draw_round_cap_line(
            surface, (x - inset, y + inset), (x + inset, y - inset), color, width
        )
    elif kind == "gear":
        teeth = 6
        tooth = max(3, int(radius * 0.38))
        hub = max(4, int(radius * 0.55))
        for index in range(teeth):
            angle = math.radians(index * 60)
            inner = (
                x + math.cos(angle) * hub,
                y + math.sin(angle) * hub,
            )
            outer = (
                x + math.cos(angle) * (hub + tooth),
                y + math.sin(angle) * (hub + tooth),
            )
            draw_round_cap_line(surface, inner, outer, color, width + 1)
        pygame.draw.circle(surface, color, (int(x), int(y)), hub, max(2, width - 1))
        draw_smooth_circle(surface, (x, y), max(2, hub // 3), color)

def hide_mouse_pointer():
    pygame.mouse.set_visible(False)

def draw_circle_icon_button(surface, rect, fill, kind):
    radius = min(rect.width, rect.height) // 2
    draw_smooth_circle(surface, rect.center, radius, fill)
    ink = ink_on(fill)
    draw_vector_icon(
        surface, rect.center, kind, ink,
        radius=max(8, radius // 2),
        width=4 if radius >= 18 else 3,
    )
    return fill

def draw_modern_button(surface, rect, fill, border, radius=14, border_width=0):
    body = border if (border[0] + border[1] + border[2]) > 90 else fill
    pygame.draw.rect(surface, body, rect, border_radius=S(radius))
    return body

def labeled_button(surface, rect, fill, font, text, radius=14, border=None):
    body = draw_modern_button(surface, rect, fill, border or fill, radius)
    draw_centered_text(surface, font, text, ink_on(body), rect)
    return body

def draw_info_card(surface, rect, accent, radius=16):
    body = UI_SURFACE_RAISED
    pygame.draw.rect(surface, body, rect, border_radius=S(radius))
    pygame.draw.rect(surface, accent, rect, S(2), border_radius=S(radius))
    return body

def draw_animated_ui_glow(surface, now):
    ui_animation_layer.fill((0, 0, 0, 0))
    pulse = (math.sin(now * 1.1) + 1) / 2
    blue_cx = 278 + math.sin(now * 0.35) * 18
    blue_cy = 112 + math.cos(now * 0.42) * 16
    purple_cx = 28 + math.cos(now * 0.3) * 20
    purple_cy = 365 + math.sin(now * 0.38) * 18

    for radius, alpha in ((105, 3), (78, 5), (52, 7)):
        pygame.draw.ellipse(
            ui_animation_layer,
            (*UI_BLUE, alpha + int(pulse * 3)),
            E(blue_cx, blue_cy, radius)
        )
    for radius, alpha in ((120, 3), (88, 5), (58, 7)):
        pygame.draw.ellipse(
            ui_animation_layer,
            (*UI_PURPLE, alpha + int((1 - pulse) * 3)),
            E(purple_cx, purple_cy, radius)
        )
    surface.blit(ui_animation_layer, (0, 0))

def draw_pulsing_border(surface, rect, color, now):
    ui_animation_layer.fill((0, 0, 0, 0))
    pulse = (math.sin(now * 2.2) + 1) / 2
    outer = rect.inflate(X(8), Y(8))
    inner = rect.inflate(X(4), Y(4))
    pygame.draw.rect(
        ui_animation_layer,
        (*color, 10 + int(pulse * 12)),
        outer,
        S(2),
        border_radius=S(22)
    )
    pygame.draw.rect(
        ui_animation_layer,
        (*color, 20 + int(pulse * 18)),
        inner,
        S(2),
        border_radius=S(20)
    )
    surface.blit(ui_animation_layer, (0, 0))

ui_background = None
ui_palette_theme = None
ui_animation_layer = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
brightness_overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
refresh_ui_palette()

instance = vlc.Instance('--no-video')
player = instance.media_player_new()

URL = "https://raw.githubusercontent.com/simsonpeter/Tcradios/refs/heads/main/stations.json"
LANGUAGE_BASE_URL = (
    "https://raw.githubusercontent.com/simsonpeter/Tcradios/"
    "8d31b80bed64167d2887313baf5b3bb12879308d/languages"
)
LANGUAGE_STREAMS = {
    "Tamil": None,
    "Kannada": f"{LANGUAGE_BASE_URL}/Kannada.json",
    "Dutch": f"{LANGUAGE_BASE_URL}/dutch.json",
    "English": f"{LANGUAGE_BASE_URL}/english.json",
    "Hindi": f"{LANGUAGE_BASE_URL}/hindi.json",
    "Malayalam": f"{LANGUAGE_BASE_URL}/malayalam.json",
    "Sinhala": f"{LANGUAGE_BASE_URL}/sinhala.json",
    "Telugu": f"{LANGUAGE_BASE_URL}/telugu.json"
}
LAST_STATION_FILE = os.path.expanduser("~/.last_station")
PLAYBACK_FILE = os.path.expanduser("~/.tcradios_playback.json")
STATIONS_CACHE_FILE = os.path.expanduser("~/.tcradios_stations.json")
BUNDLED_STATIONS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "stations.json",
)
saved_station_url = ""
saved_station_index = 0
saved_playback = {}
stations_waiting_for_github = False
_playback_save_at = 0

def load_playback_state():
    global saved_station_url, saved_station_index, saved_playback
    saved_playback = {}
    for path in (PLAYBACK_FILE, LAST_STATION_FILE):
        try:
            text = open(path, "r").read().strip()
            if not text:
                continue
            if text.startswith("{"):
                saved = json.loads(text)
            else:
                saved = {"index": int(text)}
            saved_playback = saved if isinstance(saved, dict) else {}
            saved_station_url = str(saved_playback.get("url", "")).strip()
            saved_station_index = int(saved_playback.get("index", 0) or 0)
            return
        except (OSError, ValueError, TypeError):
            continue
    saved_station_url = ""
    saved_station_index = 0

def playback_snapshot():
    snapshot = {
        "volume": int(vol_level),
        "last_unmuted_volume": int(last_unmuted_volume),
    }
    try:
        if stations and 0 <= current_idx < len(stations):
            station = stations[current_idx]
            snapshot.update({
                "index": current_idx,
                "url": station.get("url", ""),
                "name": station.get("name", ""),
                "youtube_id": station.get("youtube_id", ""),
                "language": station.get("language", ""),
                "genre": station.get("genre", ""),
                "logo": station.get("logo", ""),
                "direct_link_id": station.get("direct_link_id", ""),
            })
    except NameError:
        pass
    return snapshot

def save_playback_state(force=False):
    global _playback_save_at
    now = time.time()
    if not force and now - _playback_save_at < 0.5:
        return
    _playback_save_at = now
    try:
        payload = json.dumps(playback_snapshot())
        for path in (PLAYBACK_FILE, LAST_STATION_FILE):
            temp_path = path + ".tmp"
            with open(temp_path, "w") as handle:
                handle.write(payload)
            os.replace(temp_path, path)
    except (OSError, TypeError, ValueError) as error:
        print(f"Could not save playback: {error}")

def normalize_stations(raw_stations):
    loaded = []
    if not isinstance(raw_stations, list):
        return loaded
    for item in raw_stations:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        url = str(item.get("url", "")).strip()
        if not name or not url:
            continue
        station = dict(item)
        station["name"] = name
        station["url"] = url
        loaded.append(station)
    return loaded

def read_saved_station():
    load_playback_state()

def read_stations_file(path):
    try:
        with open(path, "r") as station_file:
            return normalize_stations(json.load(station_file))
    except (OSError, ValueError, TypeError):
        return []

def read_stations_cache():
    return read_stations_file(STATIONS_CACHE_FILE)

def read_bundled_stations():
    return read_stations_file(BUNDLED_STATIONS_FILE)

def write_stations_cache(loaded):
    try:
        with open(STATIONS_CACHE_FILE, "w") as cache_file:
            json.dump(loaded, cache_file)
    except OSError as error:
        print(f"Could not save station list: {error}")

def fetch_github_stations():
    response = requests.get(URL, timeout=8)
    response.raise_for_status()
    return normalize_stations(response.json())

def choose_station_index(loaded):
    youtube_id = str(saved_playback.get("youtube_id") or "").strip()
    if youtube_id:
        for index, station in enumerate(loaded):
            if station.get("youtube_id") == youtube_id:
                return index
    direct_link_id = saved_playback.get("direct_link_id")
    if direct_link_id not in (None, ""):
        for index, station in enumerate(loaded):
            if station.get("direct_link_id") == direct_link_id:
                return index
    if saved_station_url:
        for index, station in enumerate(loaded):
            if station.get("url") == saved_station_url:
                return index
    saved_name = str(saved_playback.get("name") or "").strip()
    if saved_name:
        for index, station in enumerate(loaded):
            if station.get("name") == saved_name:
                return index
    if 0 <= saved_station_index < len(loaded):
        return saved_station_index
    return 0

read_saved_station()
try:
    stations = fetch_github_stations()
    if not stations:
        raise ValueError("GitHub station list was empty")
    write_stations_cache(stations)
    print(f"Loaded {len(stations)} stations from GitHub")
except Exception as error:
    print(f"GitHub station list unavailable: {error}")
    stations = read_stations_cache() or read_bundled_stations()
    if stations:
        print(f"Loaded {len(stations)} TCRADIOS stations from the local copy")
        stations_waiting_for_github = True
    else:
        stations = [{
            "name": "Loading stations",
            "url": "",
            "genre": "TCRADIOS",
        }]
        stations_waiting_for_github = True
        print("Waiting for the TCRADIOS station list")

base_stations = [station.copy() for station in stations if station.get("url")]
current_idx = choose_station_index(stations) if stations and stations[0].get("url") else 0

FAVORITES_FILE = os.path.expanduser("~/.radio_favorites")
favorite_indices = []

def load_favorite_indices():
    global favorite_indices
    try:
        with open(FAVORITES_FILE, "r") as favorites_file:
            favorite_indices = [
                index for index in json.load(favorites_file)
                if isinstance(index, int)
                and 0 <= index < len(stations)
                and stations[index].get("url")
            ][:6]
    except (OSError, ValueError, TypeError):
        playable = len([station for station in stations if station.get("url")])
        favorite_indices = list(range(min(4, playable)))

load_favorite_indices()

try:
    vol_level = max(0, min(100, int(saved_playback.get("volume", vol_level))))
    last_unmuted_volume = max(
        1,
        min(100, int(saved_playback.get("last_unmuted_volume", vol_level or 80))),
    )
except (TypeError, ValueError):
    vol_level = 80
    last_unmuted_volume = 80
if vol_level > 0:
    last_unmuted_volume = vol_level
try:
    player.audio_set_volume(vol_level)
    audio_manager.set_volume(vol_level)
except Exception as error:
    print(f"Volume restore error: {error}")
print(f"Restored volume {vol_level}%")
last_weather_update = 0
last_system_update = 0
saver_mode = False
show_qr = False
weather_str = f"{device_settings.weather_name.upper()}: --C"
current_temp = 0
weather_type = "clear"
weather_label = "Clear"
weather_forecast = []
meta_text = ""
scroll_x = SCREEN_W
saver_scroll_x = SCREEN_W
alarm_fade_active = False
alarm_fade_data = {}
saver_active = False
saver_started_at = time.time()
greeting_until = 0
greeting_shown_on = None
shutdown_confirm_until = 0
shutdown_in_progress = False
system_stats = {
    'cpu_temp': '--',
    'disk_free': '--',
    'wifi': '--',
    'bluetooth': 'Not connected'
}
system_stats_updating = False
touch_bluetooth_devices = []
touch_bluetooth_status = "Tap Search to find nearby devices"
touch_bluetooth_busy = False
touch_bluetooth_offset = 0
wifi_networks = []
wifi_status_text = "Choose a network"
wifi_busy = False
wifi_pending = None
wifi_password_open = False
wifi_password_text = ""
wifi_shift = False
wifi_target = None
wifi_setup_required = False
wifi_from_settings = False
language_stream_cache = {}
selected_language = None
language_stream_status = "Choose a language"
language_stream_busy = False
language_stream_offset = 0

# Logo setup
LOGO_SIZE = S(112)
LOGO_CENTER = LOGO_SIZE // 2
logo_rect = R(104, 72, 112, 112)
logo = pygame.Surface((LOGO_SIZE, LOGO_SIZE), pygame.SRCALPHA)
logo.fill((0, 0, 0, 0))
pygame.draw.circle(logo, (40, 40, 40), (LOGO_CENTER, LOGO_CENTER), LOGO_CENTER)
pygame.draw.circle(logo, CYAN, (LOGO_CENTER, LOGO_CENTER), LOGO_CENTER, 2)
initials = station_initials(stations[current_idx]['name'])
text = f_lg.render(initials, True, CYAN)
text_rect = text.get_rect(center=(LOGO_CENTER, LOGO_CENTER))
logo.blit(text, text_rect)

qr_target = ""
qr_surface = pygame.Surface((S(240), S(240)))
qr_surface.fill((0, 0, 0))
last_ip_check = time.time()

def listen_along_url():
    return f"http://{current_ip}:8080/listen"

def rebuild_qr_surface():
    global qr_surface, qr_target
    target = listen_along_url()
    if target == qr_target and qr_target:
        return
    try:
        qr_img = qrcode.make(target).convert('RGB')
        qr_surface = pygame.image.fromstring(qr_img.tobytes(), qr_img.size, 'RGB')
        qr_surface = pygame.transform.scale(qr_surface, (S(240), S(240)))
        qr_target = target
    except Exception:
        pass

rebuild_qr_surface()

def update_qr_code():
    global current_ip, last_ip_check
    now = time.time()
    if now - last_ip_check > 30:
        new_ip = get_local_ip()
        if new_ip != current_ip:
            current_ip = new_ip
        last_ip_check = now
    rebuild_qr_surface()

def update_logo(url):
    global logo
    try:
        if not url:
            raise ValueError("No logo URL")
        raw = urlopen(url, timeout=2).read()
        img = pygame.image.load(io.BytesIO(raw)).convert_alpha()
        img = pygame.transform.smoothscale(img, (LOGO_SIZE, LOGO_SIZE))
        
        mask = pygame.Surface((LOGO_SIZE, LOGO_SIZE), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 0))
        pygame.draw.circle(
            mask,
            (255, 255, 255, 255),
            (LOGO_CENTER, LOGO_CENTER),
            LOGO_CENTER
        )
        
        circular_logo = pygame.Surface((LOGO_SIZE, LOGO_SIZE), pygame.SRCALPHA)
        circular_logo.blit(img, (0, 0))
        circular_logo.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        pygame.draw.circle(
            circular_logo,
            CYAN,
            (LOGO_CENTER, LOGO_CENTER),
            LOGO_CENTER,
            2
        )
        logo = circular_logo
    except Exception as e:
        logo = pygame.Surface((LOGO_SIZE, LOGO_SIZE), pygame.SRCALPHA)
        logo.fill((0, 0, 0, 0))
        pygame.draw.circle(
            logo,
            (40, 40, 40),
            (LOGO_CENTER, LOGO_CENTER),
            LOGO_CENTER
        )
        pygame.draw.circle(
            logo,
            CYAN,
            (LOGO_CENTER, LOGO_CENTER),
            LOGO_CENTER,
            2
        )
        if stations[current_idx]['name']:
            initials = station_initials(stations[current_idx]['name'])
            text = f_lg.render(initials, True, CYAN)
            text_rect = text.get_rect(center=(LOGO_CENTER, LOGO_CENTER))
            logo.blit(text, text_rect)

def play():
    global meta_text, scroll_x, saver_scroll_x, saved_station_url, saved_station_index
    scroll_x = SCREEN_W
    saver_scroll_x = SCREEN_W
    if not stations:
        return
    station = stations[current_idx]
    if not station.get("url"):
        meta_text = "LOADING STATIONS"
        return
    try:
        player.set_media(instance.media_new(station['url']))
        player.play()
        player.audio_set_volume(vol_level)
        audio_manager.set_volume(vol_level)
        update_logo(station.get('logo', ''))
        saved_station_url = station.get("url", "")
        saved_station_index = current_idx
        save_playback_state(force=True)
        rebuild_qr_surface()
    except:
        pass

def apply_github_station_list(loaded):
    global current_idx, base_stations, stations_waiting_for_github
    previous_url = ""
    previous_youtube = ""
    previous_direct = None
    if stations and 0 <= current_idx < len(stations):
        previous = stations[current_idx]
        previous_url = previous.get("url") or ""
        previous_youtube = previous.get("youtube_id") or ""
        previous_direct = previous.get("direct_link_id")
    extras = [
        station for station in stations
        if station.get("youtube_id") or station.get("language")
        or station.get("direct_link_id")
    ]
    stations[:] = list(loaded) + extras
    base_stations = [station.copy() for station in loaded]
    matched = None
    for index, station in enumerate(stations):
        if previous_youtube and station.get("youtube_id") == previous_youtube:
            matched = index
            break
        if previous_direct not in (None, "") and station.get("direct_link_id") == previous_direct:
            matched = index
            break
        if previous_url and station.get("url") == previous_url:
            matched = index
            break
    if matched is not None:
        current_idx = matched
        stations_waiting_for_github = False
        return
    current_idx = choose_station_index(stations)
    stations_waiting_for_github = False
    load_favorite_indices()
    play()

def retry_github_stations():
    for _attempt in range(24):
        time.sleep(5)
        try:
            loaded = fetch_github_stations()
        except Exception:
            continue
        if not loaded:
            continue
        write_stations_cache(loaded)
        print(f"Loaded {len(loaded)} stations from GitHub")
        apply_github_station_list(loaded)
        return
    print("TCRADIOS station list could not be loaded")

def current_youtube_id():
    if stations and 0 <= current_idx < len(stations):
        return str(stations[current_idx].get("youtube_id") or "").strip()
    return ""

def remember_youtube_queue(video_id, title=""):
    global youtube_queue, youtube_queue_index, youtube_touch_offset
    video_id = str(video_id or "").strip()
    if not video_id:
        return
    if youtube_results_cache:
        youtube_queue = [
            dict(item) for item in youtube_results_cache if item.get("id")
        ]
    if not any(item.get("id") == video_id for item in youtube_queue):
        youtube_queue.append({
            "id": video_id,
            "title": title or "YouTube",
            "uploader": "",
            "duration": "",
        })
    youtube_queue_index = next(
        (
            index for index, item in enumerate(youtube_queue)
            if item.get("id") == video_id
        ),
        0,
    )
    youtube_touch_offset = (max(0, youtube_queue_index) // 4) * 4

def play_youtube_station(video_id, title, audio_url):
    global current_idx, _youtube_play_started_at, _youtube_ended_handled
    global _youtube_was_playing
    station = {
        'name': f"YT: {str(title)[:40]}",
        'url': audio_url,
        'genre': 'YouTube',
        'logo': f'https://img.youtube.com/vi/{video_id}/mqdefault.jpg',
        'youtube_id': video_id,
    }
    existing = next(
        (
            index for index, item in enumerate(stations)
            if item.get('youtube_id') == video_id
        ),
        None
    )
    if existing is None:
        stations.append(station)
        current_idx = len(stations) - 1
    else:
        stations[existing] = station
        current_idx = existing
    remember_youtube_queue(video_id, title)
    youtube_skip_ids.discard(video_id)
    _youtube_play_started_at = time.time()
    _youtube_ended_handled = False
    _youtube_was_playing = False
    play()

def save_favorites():
    try:
        with open(FAVORITES_FILE, "w") as favorites_file:
            json.dump(favorite_indices[:6], favorites_file)
    except OSError as error:
        print(f"Could not save favorites: {error}")

def toggle_current_favorite():
    if current_idx in favorite_indices:
        favorite_indices.remove(current_idx)
    else:
        favorite_indices.insert(0, current_idx)
        del favorite_indices[6:]
    save_favorites()

def read_system_stats():
    stats = {
        'cpu_temp': '--',
        'disk_free': '--',
        'wifi': '--',
        'bluetooth': 'Not connected'
    }
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as temp_file:
            stats['cpu_temp'] = f"{int(temp_file.read().strip()) / 1000:.0f}°C"
    except (OSError, ValueError):
        pass

    try:
        filesystem = os.statvfs('/')
        free_gb = filesystem.f_bavail * filesystem.f_frsize / (1024 ** 3)
        stats['disk_free'] = f"{free_gb:.1f} GB free"
    except OSError:
        pass

    try:
        with open('/proc/net/wireless', 'r') as wireless_file:
            wireless_lines = wireless_file.readlines()[2:]
        if wireless_lines:
            quality = float(wireless_lines[0].split()[2].rstrip('.'))
            stats['wifi'] = f"{max(0, min(100, int(quality / 70 * 100)))}%"
    except (OSError, ValueError, IndexError):
        pass

    try:
        devices, _, connected = audio_manager._bluetooth_device_sets()
        if connected:
            address = next(iter(connected))
            stats['bluetooth'] = devices.get(address, {}).get('name', address)
    except Exception:
        pass
    return stats

def refresh_system_stats():
    global system_stats, system_stats_updating
    try:
        system_stats = read_system_stats()
    finally:
        system_stats_updating = False

BLUETOOTH_PAGE_SIZE = 4


def bluetooth_last_page_offset(count):
    if count <= BLUETOOTH_PAGE_SIZE:
        return 0
    return ((count - 1) // BLUETOOTH_PAGE_SIZE) * BLUETOOTH_PAGE_SIZE


def visible_bluetooth_devices():
    return touch_bluetooth_devices[
        touch_bluetooth_offset:touch_bluetooth_offset + BLUETOOTH_PAGE_SIZE
    ]


def scan_touch_bluetooth():
    global touch_bluetooth_devices, touch_bluetooth_status
    global touch_bluetooth_busy, touch_bluetooth_offset
    try:
        touch_bluetooth_status = "Searching for nearby devices…"
        touch_bluetooth_devices = audio_manager.scan_bluetooth()
        count = len(touch_bluetooth_devices)
        touch_bluetooth_offset = bluetooth_last_page_offset(count)
        touch_bluetooth_status = (
            f"{count} device{'s' if count != 1 else ''} found"
        )
    except Exception as error:
        touch_bluetooth_status = str(error)
    finally:
        touch_bluetooth_busy = False

def has_network_connection():
    try:
        with open('/proc/net/route', 'r') as route_file:
            next(route_file)
            for line in route_file:
                fields = line.split()
                if (
                    len(fields) > 1
                    and fields[1] == '00000000'
                    and fields[0] != 'lo'
                ):
                    return True
    except (OSError, StopIteration):
        pass
    return False

def run_nmcli(args, timeout=25):
    last_error = 'Wi-Fi command failed'
    for prefix in ([], ['sudo', '-n']):
        try:
            result = subprocess.run(
                prefix + ['nmcli', *args],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            return '', 'nmcli is not installed'
        except subprocess.TimeoutExpired:
            last_error = 'Wi-Fi request timed out'
            continue
        if result.returncode == 0:
            return (result.stdout or '').strip(), None
        last_error = (
            (result.stderr or result.stdout or last_error).strip().split('\n')[-1]
        )
    return '', last_error[:160]

def current_wifi_ssid():
    stdout, _err = run_nmcli(
        ['-t', '-f', 'active,ssid', 'device', 'wifi'], timeout=8
    )
    for line in stdout.splitlines():
        if line.startswith('yes:'):
            return line.split(':', 1)[1]
    return ''

def parse_wifi_networks(stdout):
    networks = []
    seen = set()
    for line in stdout.splitlines():
        raw = line.replace('\\:', '\x00')
        parts = raw.split(':')
        if len(parts) < 4:
            continue
        in_use = parts[0] == '*'
        security = parts[-1].replace('\x00', ':')
        try:
            strength = int(parts[-2])
        except ValueError:
            strength = 0
        ssid = ':'.join(parts[1:-2]).replace('\x00', ':').strip()
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)
        networks.append({
            'ssid': ssid,
            'signal': max(0, min(100, strength)),
            'secure': bool(security and security not in ('--', '')),
            'connected': in_use,
        })
    networks.sort(key=lambda item: (not item['connected'], -item['signal']))
    return networks[:12]

def wifi_status_label():
    if wifi_busy:
        return wifi_status_text
    ssid = current_wifi_ssid()
    if ssid:
        return f"Connected: {ssid}"
    if has_network_connection():
        return f"Online • {current_ip}"
    return "No network. Choose a Wi-Fi."

def scan_touch_wifi():
    global wifi_busy, wifi_pending
    try:
        run_nmcli(['device', 'wifi', 'rescan'], timeout=12)
        stdout, err = run_nmcli(
            ['-t', '-f', 'IN-USE,SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list'],
            timeout=20,
        )
        if err and not stdout:
            wifi_pending = ('error', err)
            return
        wifi_pending = ('list', parse_wifi_networks(stdout))
    except Exception as error:
        wifi_pending = ('error', str(error))

def connect_touch_wifi(ssid, password=''):
    global wifi_pending
    try:
        args = ['device', 'wifi', 'connect', ssid]
        if password:
            args.extend(['password', password])
        _stdout, err = run_nmcli(args, timeout=35)
        if err:
            wifi_pending = ('error', err)
            return
        wifi_pending = ('connected', ssid)
    except Exception as error:
        wifi_pending = ('error', str(error))

def begin_wifi_scan():
    global wifi_busy, wifi_status_text
    if wifi_busy:
        return
    wifi_busy = True
    wifi_status_text = "Scanning…"
    threading.Thread(target=scan_touch_wifi, daemon=True).start()

def begin_wifi_connect(network):
    global wifi_busy, wifi_status_text, wifi_password_open, wifi_target
    global wifi_password_text, wifi_shift
    if wifi_busy or not network.get('ssid'):
        return
    if network.get('secure') and not wifi_password_open:
        wifi_target = network
        wifi_password_open = True
        wifi_password_text = ""
        wifi_shift = False
        return
    wifi_busy = True
    wifi_password_open = False
    wifi_status_text = f"Joining {network['ssid']}…"
    password = wifi_password_text if network.get('secure') else ''
    threading.Thread(
        target=connect_touch_wifi,
        args=(network['ssid'], password),
        daemon=True,
    ).start()

def apply_wifi_result():
    global wifi_pending, wifi_busy, wifi_status_text, wifi_networks
    global wifi_password_open, wifi_setup_required, active_page, current_ip
    pending = wifi_pending
    if not pending:
        return
    wifi_pending = None
    wifi_busy = False
    kind = pending[0]
    if kind == 'list':
        wifi_networks = pending[1]
        wifi_status_text = (
            f"{len(wifi_networks)} network"
            f"{'s' if len(wifi_networks) != 1 else ''}"
            if wifi_networks else "No networks found"
        )
    elif kind == 'connected':
        wifi_password_open = False
        current_ip = get_local_ip()
        wifi_status_text = f"Connected: {pending[1]}"
        begin_wifi_scan()
        if stations_waiting_for_github:
            threading.Thread(target=retry_github_stations, daemon=True).start()
        if wifi_setup_required:
            wifi_setup_required = False
            active_page = "radio"
    elif kind == 'error':
        wifi_status_text = str(pending[1])[:80]

def submit_wifi_password():
    global wifi_busy, wifi_status_text
    if wifi_busy or not wifi_target:
        return
    wifi_busy = True
    wifi_status_text = f"Joining {wifi_target['ssid']}…"
    threading.Thread(
        target=connect_touch_wifi,
        args=(wifi_target['ssid'], wifi_password_text),
        daemon=True,
    ).start()

def handle_wifi_key(value):
    global wifi_password_text, wifi_shift, wifi_password_open
    symbols = {
        '1': '!', '2': '@', '3': '#', '4': '$', '5': '%',
        '6': '^', '7': '&', '8': '*', '9': '(', '0': ')',
        '-': '_', '.': ',', '/': '?',
    }
    if value == 'shift':
        wifi_shift = not wifi_shift
    elif value == 'backspace':
        wifi_password_text = wifi_password_text[:-1]
    elif value == 'space':
        if len(wifi_password_text) < 63:
            wifi_password_text += ' '
    elif value == 'cancel':
        wifi_password_open = False
        wifi_password_text = ''
        wifi_shift = False
    elif value == 'connect':
        submit_wifi_password()
    elif len(wifi_password_text) < 63:
        typed = symbols.get(value, value.upper()) if wifi_shift else value
        wifi_password_text += typed
        wifi_shift = False

def set_home_card_layout(layout):
    device_settings.home_card_layout = normalize_home_card_layout(layout)
    device_settings.save()


def cycle_home_card(slot, direction):
    if slot not in (0, 1):
        return
    kinds = list(HOME_CARD_KINDS)
    cards = list(device_settings.home_cards)
    current = cards[slot]
    index = kinds.index(current) if current in kinds else 0
    other = cards[1 - slot]
    for _ in kinds:
        index = (index + direction) % len(kinds)
        candidate = kinds[index]
        if (
            device_settings.home_card_layout == "single"
            or candidate != other
        ):
            cards[slot] = candidate
            break
    device_settings.home_cards = normalize_home_cards(cards)
    device_settings.save()


def swap_home_cards():
    cards = list(device_settings.home_cards)
    device_settings.home_cards = [cards[1], cards[0]]
    device_settings.save()


def home_card_slots(top=HOME_CARD_TOP, height=HOME_CARD_HEIGHT):
    cards = normalize_home_cards(device_settings.home_cards)
    if device_settings.home_card_layout == "single":
        return [(
            R(HOME_CARD_INSET, top, HOME_CARD_FULL_W, height),
            cards[0], HOME_CARD_INSET, top, HOME_CARD_FULL_W, height
        )]
    left_x = HOME_CARD_INSET
    right_x = HOME_CARD_INSET + HOME_CARD_HALF_W
    return [
        (R(left_x, top, HOME_CARD_HALF_W, height), cards[0], left_x, top, HOME_CARD_HALF_W, height),
        (R(right_x, top, HOME_CARD_HALF_W, height), cards[1], right_x, top, HOME_CARD_HALF_W, height),
    ]


def playback_card_box():
    for slot in home_card_slots():
        if slot[1] == "now_playing":
            return slot
    return None


def hidden_playback_controls():
    hidden = R(-200, -200, 1, 1)
    return {
        "vol_minus": hidden,
        "vol_plus": hidden,
        "vol_bar": hidden,
        "pct_x": -200,
        "pct_y": -200,
        "prev": hidden,
        "toggle": hidden,
        "next": hidden,
        "compact": True,
        "visible": False,
    }


def playback_control_layout():
    box = playback_card_box()
    if box is None:
        return hidden_playback_controls()
    _rect, _kind, x, y, w, h = box
    if w < 220:
        vol_y = y + h - 136
        btn_y = y + h - 80
        return {
            "vol_minus": R(x + 8, vol_y, 28, 34),
            "vol_plus": R(x + w - 36, vol_y, 28, 34),
            "vol_bar": R(x + 40, vol_y + 10, w - 80, 12),
            "pct_x": x + w // 2,
            "pct_y": vol_y + 32,
            "prev": R(x + 8, btn_y, 42, 44),
            "toggle": R(x + 54, btn_y - 2, 44, 48),
            "next": R(x + w - 50, btn_y, 42, 44),
            "compact": True,
            "visible": True,
        }
    vol_y = y + h - 132
    btn_y = y + h - 76
    return {
        "vol_minus": R(x + 10, vol_y, 46, 46),
        "vol_plus": R(x + w - 56, vol_y, 46, 46),
        "vol_bar": R(x + 64, vol_y + 14, w - 128, 14),
        "pct_x": x + w // 2,
        "pct_y": vol_y + 34,
        "prev": R(x + 10, btn_y, 88, 50),
        "toggle": R(x + w // 2 - 46, btn_y - 4, 92, 58),
        "next": R(x + w - 98, btn_y, 88, 50),
        "compact": False,
        "visible": True,
    }


def connect_touch_bluetooth(address, name):
    global touch_bluetooth_devices, touch_bluetooth_status
    global touch_bluetooth_busy, touch_bluetooth_offset
    try:
        touch_bluetooth_status = f"Connecting to {name}…"
        audio_manager.connect_bluetooth(address)
        touch_bluetooth_devices = audio_manager.get_bluetooth_devices()
        touch_bluetooth_offset = min(
            touch_bluetooth_offset,
            bluetooth_last_page_offset(len(touch_bluetooth_devices))
        )
        touch_bluetooth_status = f"Connected to {name}"
    except Exception as error:
        touch_bluetooth_status = str(error)
    finally:
        touch_bluetooth_busy = False

def load_language_streams(language):
    global language_stream_status, language_stream_busy
    try:
        if language == "Tamil":
            catalog = base_stations
        else:
            response = requests.get(LANGUAGE_STREAMS[language], timeout=12)
            response.raise_for_status()
            catalog = response.json()
        loaded_streams = []
        seen_urls = set()
        for stream in catalog:
            name = str(stream.get('name', '')).strip()
            url = str(stream.get('url', '')).strip()
            if not name or not url or url in seen_urls:
                continue
            seen_urls.add(url)
            loaded_streams.append({
                'name': name,
                'url': url,
                'logo': str(stream.get('logo', '')).strip(),
                'genre': str(
                    stream.get('genre') or f"{language} Radio"
                ).strip(),
                'metadata': bool(stream.get('metadata', True)),
                'language': language
            })
        language_stream_cache[language] = loaded_streams
        count = len(loaded_streams)
        language_stream_status = (
            f"{count} station{'s' if count != 1 else ''}"
        )
    except Exception as error:
        language_stream_status = str(error)
    finally:
        language_stream_busy = False

def play_language_stream(stream):
    global current_idx
    existing_index = next(
        (
            index for index, station in enumerate(stations)
            if station.get('url') == stream['url']
        ),
        None
    )
    if existing_index is None:
        stations.append(stream.copy())
        current_idx = len(stations) - 1
    else:
        current_idx = existing_index
    play()

def resume_last_playback():
    global current_idx
    youtube_id = str(saved_playback.get("youtube_id") or "").strip()
    if youtube_id:
        title = str(saved_playback.get("name") or "YouTube")
        if title.startswith("YT: "):
            title = title[4:]
        audio_url, err = youtube_audio_url(youtube_id, timeout=18)
        if audio_url:
            play_youtube_station(youtube_id, title, audio_url)
            return
        print(f"Could not restore YouTube item: {err}")
    saved_url = str(saved_station_url or "").strip()
    if youtube_id:
        saved_url = ""
    if saved_url and all(station.get("url") != saved_url for station in stations):
        restored = {
            "name": saved_playback.get("name") or "Last played",
            "url": saved_url,
            "genre": saved_playback.get("genre") or "Radio",
            "logo": saved_playback.get("logo") or "",
        }
        for key in ("language", "direct_link_id"):
            value = saved_playback.get(key)
            if value not in (None, ""):
                restored[key] = value
        stations.append(restored)
        current_idx = len(stations) - 1
    play()

splash_remaining = 5.0 - (time.time() - splash_started_at)
if splash_remaining > 0:
    time.sleep(splash_remaining)

resume_last_playback()
if stations_waiting_for_github:
    threading.Thread(target=retry_github_stations, daemon=True).start()
ip_display_time = 0
show_startup_ip = False

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

def target_display_brightness(now):
    if (
        device_settings.auto_dim_enabled
        and now - last_interaction_time
        >= device_settings.auto_dim_minutes * 60
    ):
        return min(
            device_settings.brightness,
            device_settings.dim_brightness
        )
    return device_settings.brightness

def apply_display_brightness(now):
    target = target_display_brightness(now)
    device_settings.set_hardware_brightness(target)
    if not device_settings.hardware_brightness_available and target < 100:
        alpha = int(230 * (1 - target / 100))
        brightness_overlay.fill((0, 0, 0, alpha))
        screen.blit(brightness_overlay, (0, 0))

def request_touch_shutdown():
    global shutdown_in_progress
    if shutdown_in_progress:
        return
    shutdown_in_progress = True
    threading.Thread(target=perform_safe_shutdown, daemon=True).start()

def draw_weather_icon(surface, x, y, type, size=30, dimmed=True, on_background=None):
    x, y, size = X(x), Y(y), S(size)
    line_width = max(2, size // 8)
    if dimmed:
        sun_color = tuple(int(channel * 0.3) for channel in GOLD)
        rain_color = tuple(int(channel * 0.28) for channel in CYAN)
        cloud_dark = (38, 38, 38)
        cloud_light = (58, 58, 58)
    else:
        background = on_background or UI_SURFACE_RAISED
        sun_color = ink_on(background, UI_AMBER)
        rain_color = ink_on(background, UI_BLUE)
        cloud_dark = muted_ink_on(background)
        cloud_light = ink_on(background)
    if type == "clear":
        sun_radius = size * 3 // 5
        pygame.draw.circle(surface, sun_color, (x, y), sun_radius)
        for i in range(8):
            angle = i * (math.pi / 4)
            x1 = x + math.cos(angle) * (sun_radius + 3)
            y1 = y + math.sin(angle) * (sun_radius + 3)
            x2 = x + math.cos(angle) * size
            y2 = y + math.sin(angle) * size
            pygame.draw.line(surface, sun_color, (x1, y1), (x2, y2), line_width)
    elif type == "cloud":
        pygame.draw.circle(surface, cloud_dark, (x-size//2, y+size//6), size//3)
        pygame.draw.circle(surface, cloud_light, (x, y-size//8), size*2//5)
        pygame.draw.circle(surface, cloud_dark, (x+size//2, y+size//6), size//3)
        pygame.draw.rect(surface, cloud_dark, (x-size//2, y, size, size//3))
    elif type == "rain":
        cloud_radius = size * 2 // 5
        pygame.draw.circle(surface, cloud_dark, (x, y-size//5), cloud_radius)
        for i in range(3):
            rx = x - size//2 + (i * size//2)
            pygame.draw.line(
                surface, rain_color,
                (rx, y+size//3),
                (rx-size//8, y+size),
                line_width
            )

def weather_code_to_type(code):
    if code == 0:
        return "clear"
    if code < 50:
        return "cloud"
    return "rain"

def weather_code_label(code):
    if code == 0:
        return "Clear"
    if code in (1, 2):
        return "Partly cloudy"
    if code in (3, 45, 48):
        return "Cloudy"
    if code in (51, 53, 55, 56, 57):
        return "Drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "Rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "Snow"
    if code in (95, 96, 99):
        return "Thunder"
    return "Mixed"

def draw_forecast_screen(now):
    screen.blit(ui_background, (0, 0))
    draw_animated_ui_glow(screen, now)

    header_rect = R(8, 7, 304, 52)
    pygame.draw.rect(screen, UI_SURFACE, header_rect, border_radius=S(17))
    pygame.draw.rect(screen, (54, 75, 112), header_rect, S(1), border_radius=S(17))
    draw_centered_text(screen, f_lg, "5-DAY FORECAST", UI_TEXT, header_rect)

    current_rect = R(14, 72, 292, 84)
    body = draw_info_card(screen, current_rect, UI_BLUE, 18)
    draw_weather_icon(
        screen, 65, 111, weather_type, 25, dimmed=False, on_background=body
    )
    current_surface = f_weather.render(
        f"{current_temp}°C", True, ink_on(body)
    )
    screen.blit(current_surface, XY(103, 82))
    location_label = fit_label(device_settings.weather_name.upper(), 18)
    now_surface = f_tiny.render(
        f"{location_label}  •  NOW", True, muted_ink_on(body)
    )
    screen.blit(now_surface, XY(106, 127))

    if weather_forecast:
        for index, forecast in enumerate(weather_forecast[:5]):
            row = R(14, 166 + index * 52, 292, 45)
            accent = UI_PURPLE if index == 0 else (72, 80, 98)
            body = draw_info_card(screen, row, accent, 13)

            day_surface = f_sm.render(
                forecast['day'].upper(), True, ink_on(body)
            )
            screen.blit(day_surface, (X(29), row.y + Y(7)))
            label_surface = f_tiny.render(
                forecast['label'], True, muted_ink_on(body)
            )
            screen.blit(label_surface, (X(29), row.y + Y(25)))

            draw_weather_icon(
                screen, 196, 166 + index * 52 + 22,
                forecast['type'], 12, dimmed=False, on_background=body
            )
            temperature = f"{forecast['high']}° / {forecast['low']}°"
            temperature_surface = f_sm.render(temperature, True, ink_on(body))
            screen.blit(
                temperature_surface,
                (X(292) - temperature_surface.get_width(), row.y + Y(14))
            )
    else:
        loading_rect = R(14, 166, 292, 253)
        body = draw_info_card(screen, loading_rect, (72, 80, 98), 16)
        draw_centered_text(
            screen, f_sm, "Forecast unavailable", muted_ink_on(body), loading_rect
        )

    labeled_button(screen, btn_pages, UI_BLUE, f_sm, "PAGES", 16)

def draw_page_base(title, now):
    screen.blit(ui_background, (0, 0))
    draw_animated_ui_glow(screen, now)
    header = R(8, 7, 304, 52)
    pygame.draw.rect(screen, UI_SURFACE, header, border_radius=S(17))
    pygame.draw.rect(screen, (54, 75, 112), header, S(1), border_radius=S(17))
    draw_centered_text(screen, f_lg, title, UI_TEXT, header)

def draw_pages_button():
    body = draw_modern_button(screen, btn_pages, UI_BLUE, UI_BLUE, 16)
    draw_centered_text(screen, f_sm, "PAGES", contrasting_text(body), btn_pages)

def fit_label(text, length=16):
    return truncate_display(text, length)

def fit_tail(text, length=28):
    return truncate_display(text, length, tail=True)

def draw_menu_screen(now):
    draw_page_base("TC RADIOS", now)
    labels = [
        ("NOW PLAYING", "Radio controls"),
        ("FAVORITES", "Quick stations"),
        ("FORECAST", "Five days"),
        ("CLOCK", "Time dashboard"),
        ("ALARM / SLEEP", "Timers"),
        ("SYSTEM", "Pi status"),
        ("LANGUAGES", "More streams"),
        ("SETTINGS", "Audio • Wi-Fi"),
        ("YOUTUBE", "Search and play"),
    ]
    for index, (title, subtitle) in enumerate(labels):
        rect = menu_card_rects[index]
        border = (
            UI_PINK if index == 8
            else (UI_BLUE, UI_PURPLE, UI_AMBER)[index % 3]
        )
        body = draw_modern_button(screen, rect, border, border, 16)
        title_surface = f_sm.render(title, True, contrasting_text(body))
        screen.blit(
            title_surface,
            (rect.centerx - title_surface.get_width() // 2, rect.y + Y(12))
        )
        subtitle_surface = f_tiny.render(subtitle, True, contrasting_muted(body))
        screen.blit(
            subtitle_surface,
            (rect.centerx - subtitle_surface.get_width() // 2, rect.y + Y(34))
        )
def draw_favorites_screen(now):
    draw_page_base("FAVORITES", now)
    add_border = UI_PINK if current_idx in favorite_indices else UI_GREEN
    add_label = (
        "REMOVE CURRENT" if current_idx in favorite_indices
        else "ADD CURRENT"
    )
    labeled_button(
        screen, btn_favorite_toggle, add_border, f_tiny, add_label, 13
    )

    for index, rect in enumerate(favorite_card_rects):
        if index < len(favorite_indices):
            station_index = favorite_indices[index]
            station = stations[station_index]
            accent = UI_BLUE if station_index == current_idx else (72, 80, 98)
            body = draw_info_card(screen, rect, accent, 14)
            number = f_tiny.render(
                f"{index + 1}", True, ink_on(body, UI_BLUE)
            )
            screen.blit(number, (rect.x + X(10), rect.y + Y(9)))
            name = f_sm.render(
                fit_label(station['name'], 15), True, ink_on(body)
            )
            screen.blit(name, (rect.x + X(10), rect.y + Y(31)))
            genre = f_tiny.render(
                fit_label(station.get('genre', 'Radio'), 18),
                True, muted_ink_on(body)
            )
            screen.blit(genre, (rect.x + X(10), rect.y + Y(54)))
        else:
            body = draw_info_card(screen, rect, (72, 80, 98), 14)
            draw_centered_text(screen, f_tiny, "EMPTY", muted_ink_on(body), rect)
    draw_pages_button()

def draw_home_card(
    rect, kind, now, layout_x=8, layout_y=64, layout_w=148, layout_h=200
):
    global logo_rect
    accents = {
        "now_playing": UI_BLUE,
        "weather": UI_PURPLE,
        "forecast": UI_AMBER,
        "alarm": UI_AMBER,
        "system": (72, 80, 98),
        "bluetooth": UI_GREEN,
    }
    half = layout_w < 220
    preview = layout_h < 100
    body = draw_info_card(
        screen, rect, accents.get(kind, UI_BLUE), 14 if preview else 16
    )
    title = f_tiny.render(
        HOME_CARD_LABELS.get(kind, "CARD"), True, muted_ink_on(body)
    )
    screen.blit(
        title,
        (rect.centerx - title.get_width() // 2, Y(layout_y + 6))
    )
    main_chars = 13 if half else 28
    sub_chars = 15 if half else 32

    def blit_centered(text, font, color, y_layout, chars):
        surface = font.render(fit_label(text, chars), True, color)
        screen.blit(
            surface,
            (rect.centerx - surface.get_width() // 2, Y(y_layout))
        )
        return surface

    def blit_lines(main_text, sub_text, y_layout):
        blit_centered(main_text, f_sm, ink_on(body), y_layout, main_chars)
        blit_centered(
            sub_text, f_tiny, muted_ink_on(body), y_layout + 20, sub_chars
        )

    def blit_rows(rows, start_y, step=36):
        for index, (label, value) in enumerate(rows):
            row_y = start_y + index * step
            label_surf = f_tiny.render(label, True, muted_ink_on(body))
            value_surf = f_sm.render(
                fit_label(str(value), main_chars), True, ink_on(body)
            )
            screen.blit(label_surf, (rect.x + X(10), Y(row_y)))
            screen.blit(
                value_surf,
                (
                    rect.right - value_surf.get_width() - X(10),
                    Y(row_y + (8 if half else 4))
                )
            )

    if preview:
        if kind == "now_playing":
            station = stations[current_idx]['name'] if stations else "TCRADIOS"
            blit_lines(sanitize_text(meta_text) or station, station, layout_y + 24)
        elif kind == "weather":
            blit_lines(
                f"{current_temp}°C" if current_temp else "--°C",
                device_settings.weather_name.upper(),
                layout_y + 24
            )
        elif kind == "forecast":
            today = weather_forecast[0] if weather_forecast else None
            blit_lines(
                f"{today['high']}° / {today['low']}°" if today else "No forecast",
                today['label'] if today else "yet",
                layout_y + 24
            )
        elif kind == "alarm":
            blit_lines(
                alarm_system.alarm_time,
                "ON" if alarm_system.alarm_enabled else "OFF",
                layout_y + 24
            )
        elif kind == "system":
            blit_lines(
                f"CPU {system_stats['cpu_temp']}",
                f"IP {current_ip}",
                layout_y + 24
            )
        else:
            blit_lines(system_stats['bluetooth'], "SPEAKER", layout_y + 24)
        return body

    if kind == "now_playing":
        station = stations[current_idx]['name'] if stations else "TCRADIOS"
        playing = sanitize_text(meta_text) or station
        genre = ""
        if stations:
            genre = str(stations[current_idx].get('genre') or "").strip()
        text_y = layout_y + layout_h - 186
        radius = 38 if half else 52
        cx = layout_x + layout_w // 2
        cy = layout_y + 30 + radius
        pygame.draw.ellipse(screen, (17, 31, 53), E(cx, cy, radius))
        pygame.draw.ellipse(screen, (40, 58, 91), E(cx, cy, radius - 2), S(1))
        inner_r = radius - 4
        logo_rect = R(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2)
        screen.blit(
            pygame.transform.smoothscale(
                logo, (logo_rect.width, logo_rect.height)
            ),
            logo_rect
        )
        try:
            is_playing = player.get_state() == vlc.State.Playing
        except Exception:
            is_playing = False
        if is_playing:
            pulse = (math.sin(now * 3) + 1) / 2
            pygame.draw.ellipse(
                screen,
                (
                    int(UI_BLUE[0] * 0.75),
                    int(UI_BLUE[1] * 0.75),
                    int(UI_BLUE[2] * 0.75)
                ),
                E(cx, cy, radius - 2 + pulse * 4),
                S(2)
            )
        blit_centered(playing, f_sm, ink_on(body), text_y, main_chars)
        blit_centered(station, f_tiny, muted_ink_on(body), text_y + 20, sub_chars)
        if genre and genre.upper() not in (station.upper(), "TCRADIOS", "RADIO"):
            blit_centered(genre, f_tiny, muted_ink_on(body), text_y + 38, sub_chars)
    elif kind == "weather":
        icon_y = layout_y + (58 if half else 54)
        draw_weather_icon(
            screen, layout_x + layout_w // 2, icon_y,
            weather_type, 30 if half else 36,
            dimmed=False, on_background=body
        )
        temp_text = f"{current_temp}°C" if current_temp else "--°C"
        blit_centered(temp_text, f_weather, ink_on(body), icon_y + 36, 8)
        blit_centered(weather_label.upper(), f_sm, ink_on(body), icon_y + 82, main_chars)
        blit_centered(
            device_settings.weather_name.upper(),
            f_tiny, muted_ink_on(body), icon_y + 104, sub_chars
        )
        rows = weather_forecast[:4 if half else 5]
        row_y = icon_y + 128
        if rows:
            for index, forecast in enumerate(rows):
                fy = row_y + index * (36 if half else 30)
                day = f_tiny.render(forecast['day'].upper(), True, muted_ink_on(body))
                screen.blit(day, (rect.x + X(10), Y(fy)))
                draw_weather_icon(
                    screen, layout_x + layout_w // 2, fy + 10,
                    forecast['type'], 8, dimmed=False, on_background=body
                )
                hi_lo = f_tiny.render(
                    f"{forecast['high']}° / {forecast['low']}°",
                    True, ink_on(body)
                )
                screen.blit(
                    hi_lo,
                    (rect.right - hi_lo.get_width() - X(8), Y(fy + 6))
                )
        else:
            blit_centered(
                "Forecast loading", f_tiny, muted_ink_on(body),
                row_y, 18
            )
    elif kind == "forecast":
        days = weather_forecast[:5]
        if days:
            row_h = 56 if half else 52
            for index, forecast in enumerate(days):
                fy = layout_y + 30 + index * row_h
                day = f_sm.render(forecast['day'].upper(), True, ink_on(body))
                screen.blit(day, (rect.x + X(10), Y(fy)))
                label = f_tiny.render(
                    fit_label(forecast['label'], 12 if half else 18),
                    True, muted_ink_on(body)
                )
                screen.blit(label, (rect.x + X(10), Y(fy + 20)))
                draw_weather_icon(
                    screen, layout_x + (98 if half else 170), fy + 22,
                    forecast['type'], 10, dimmed=False, on_background=body
                )
                hi_lo = f_sm.render(
                    f"{forecast['high']}° / {forecast['low']}°",
                    True, ink_on(body)
                )
                screen.blit(
                    hi_lo,
                    (rect.right - hi_lo.get_width() - X(8), Y(fy + 12))
                )
        else:
            blit_lines("No forecast", "yet", layout_y + 80)
    elif kind == "alarm":
        blit_centered(
            alarm_system.alarm_time, f_weather, ink_on(body),
            layout_y + 70, 8
        )
        blit_centered(
            "ALARM ON" if alarm_system.alarm_enabled else "ALARM OFF",
            f_sm,
            ink_on(body) if alarm_system.alarm_enabled else muted_ink_on(body),
            layout_y + 130, 14
        )
        if alarm_system.sleep_timer_enabled:
            blit_centered(
                f"SLEEP {alarm_system.get_sleep_remaining()} MIN",
                f_tiny, muted_ink_on(body), layout_y + 168, 18
            )
        else:
            blit_centered(
                "SLEEP TIMER OFF", f_tiny, muted_ink_on(body),
                layout_y + 168, 18
            )
    elif kind == "system":
        blit_rows(
            (
                ("WI-FI", system_stats['wifi']),
                ("IP", current_ip),
                ("CPU", system_stats['cpu_temp']),
                ("STORAGE", system_stats['disk_free']),
            ),
            layout_y + 40,
            56 if half else 52
        )
    elif kind == "bluetooth":
        blit_centered("SPEAKER", f_tiny, muted_ink_on(body), layout_y + 50, 12)
        blit_centered(
            system_stats['bluetooth'], f_lg if not half else f_sm,
            ink_on(body), layout_y + 86, main_chars
        )
        blit_centered(
            touch_bluetooth_status, f_tiny, muted_ink_on(body),
            layout_y + 140, sub_chars
        )
    return body


def draw_clock_screen(now):
    draw_page_base("CLOCK", now)
    current_time = datetime.now()
    time_surface = f_xl.render(current_time.strftime("%H:%M"), True, UI_TEXT)
    screen.blit(time_surface, (X(160) - time_surface.get_width() // 2, Y(82)))
    date_surface = f_med.render(
        current_time.strftime("%A").upper(), True, ink_on(UI_BG_TOP, UI_BLUE)
    )
    screen.blit(date_surface, (X(160) - date_surface.get_width() // 2, Y(177)))
    full_date = f_sm.render(
        current_time.strftime("%d %B %Y"), True, muted_ink_on(UI_BG_TOP)
    )
    screen.blit(full_date, (X(160) - full_date.get_width() // 2, Y(213)))

    weather_card = R(28, 252, 264, 78)
    body = draw_info_card(screen, weather_card, UI_PURPLE, 18)
    draw_weather_icon(
        screen, 76, 291, weather_type, 22,
        dimmed=False, on_background=body
    )
    temp = f_weather.render(f"{current_temp}°C", True, ink_on(body))
    screen.blit(temp, (X(112), weather_card.y + Y(11)))
    city = f_tiny.render(
        fit_label(device_settings.weather_name.upper(), 18),
        True, muted_ink_on(body)
    )
    screen.blit(city, (X(116), weather_card.y + Y(53)))

    station_card = R(28, 344, 264, 58)
    body = draw_info_card(screen, station_card, (72, 80, 98), 15)
    draw_centered_text(
        screen, f_sm, fit_label(stations[current_idx]['name'], 28),
        ink_on(body), station_card
    )
    draw_pages_button()

def draw_alarm_screen(now):
    draw_page_base("ALARM & SLEEP", now)
    alarm_card = R(18, 75, 284, 115)
    body = draw_info_card(
        screen, alarm_card,
        UI_AMBER if alarm_system.alarm_enabled else (72, 80, 98), 18
    )
    alarm_label = f_weather.render(
        alarm_system.alarm_time, True, ink_on(body)
    )
    screen.blit(
        alarm_label,
        (alarm_card.centerx - alarm_label.get_width() // 2, 91)
    )
    state = "ALARM ON" if alarm_system.alarm_enabled else "ALARM OFF"
    state_surface = f_sm.render(
        state, True, muted_ink_on(
            body, UI_AMBER if alarm_system.alarm_enabled else None
        )
    )
    screen.blit(
        state_surface,
        (alarm_card.centerx - state_surface.get_width() // 2, 150)
    )

    for rect, label in (
        (btn_alarm_minus, "− 5 MIN"),
        (btn_alarm_toggle_page, "ON / OFF"),
        (btn_alarm_plus, "+ 5 MIN")
    ):
        labeled_button(screen, rect, UI_BLUE, f_tiny, label, 13)

    sleep_title = f_sm.render("SLEEP TIMER", True, UI_TEXT)
    screen.blit(sleep_title, XY(20, 261))
    for rect, minutes in zip(btn_sleep_presets, (15, 30, 60)):
        active = (
            alarm_system.sleep_timer_enabled
            and alarm_system.sleep_duration == minutes * 60
        )
        labeled_button(
            screen, rect,
            UI_GREEN if active else (55, 61, 77),
            f_sm, f"{minutes} MIN", 13
        )

    sleep_status = (
        f"{alarm_system.get_sleep_remaining()} min remaining"
        if alarm_system.sleep_timer_enabled else "Timer off"
    )
    labeled_button(
        screen, btn_sleep_cancel,
        UI_PINK if alarm_system.sleep_timer_enabled else (55, 61, 77),
        f_tiny, sleep_status.upper(), 13
    )
    draw_pages_button()

def draw_system_screen(now):
    draw_page_base("SYSTEM STATUS", now)
    values = [
        ("WI-FI", system_stats['wifi']),
        ("IP ADDRESS", current_ip),
        ("CPU", system_stats['cpu_temp']),
        ("STORAGE", system_stats['disk_free'])
    ]
    for rect, (label, value) in zip(system_card_rects, values):
        body = draw_info_card(screen, rect, (72, 80, 98), 16)
        label_surface = f_tiny.render(label, True, muted_ink_on(body))
        screen.blit(label_surface, (rect.x + X(14), rect.y + Y(15)))
        value_surface = f_sm.render(
            fit_label(value, 18), True, ink_on(body)
        )
        screen.blit(value_surface, (rect.x + X(14), rect.y + Y(43)))

    bluetooth_card = R(18, 320, 284, 54)
    body = draw_info_card(screen, bluetooth_card, UI_BLUE, 16)
    bt_label = f_tiny.render("BLUETOOTH AUDIO", True, muted_ink_on(body))
    screen.blit(bt_label, (X(34), bluetooth_card.y + Y(8)))
    bt_value = f_sm.render(
        fit_label(system_stats['bluetooth'], 28), True, ink_on(body)
    )
    screen.blit(bt_value, (X(34), bluetooth_card.y + Y(28)))

    shutdown_armed = now <= shutdown_confirm_until
    shutdown_label = (
        "SHUTTING DOWN…"
        if shutdown_in_progress
        else ("TAP AGAIN TO SHUT DOWN" if shutdown_armed else "SAFE SHUTDOWN")
    )
    labeled_button(
        screen, btn_safe_shutdown,
        UI_PINK if shutdown_armed else (94, 49, 61),
        f_tiny, shutdown_label, 13
    )
    draw_pages_button()

def draw_settings_screen(now):
    draw_page_base("SETTINGS", now)

    audio_title = f_sm.render("SOUND OUTPUT", True, UI_TEXT)
    screen.blit(audio_title, XY(18, 67))
    audio_labels = ("AUTO", "JACK", "HDMI", "BLUETOOTH")
    audio_names = ("auto", "analog", "hdmi", "bluetooth")
    for rect, label, output_name in zip(
        btn_audio_outputs, audio_labels, audio_names
    ):
        active = audio_manager.current_output == output_name
        available = (
            output_name in ("auto", "bluetooth")
            or audio_manager.outputs.get(output_name, {}).get(
                'available', False
            )
        )
        border = UI_GREEN if active else (UI_BLUE if available else (55, 61, 77))
        fill = UI_SURFACE_RAISED if available else UI_SURFACE
        body = draw_modern_button(screen, rect, fill, border, 12)
        draw_centered_text(
            screen, f_tiny, label,
            contrasting_text(body) if available else contrasting_muted(body),
            rect
        )

    display_title = f_sm.render(
        f"DISPLAY  •  {device_settings.brightness}%", True, UI_TEXT
    )
    screen.blit(display_title, XY(18, 158))
    labeled_button(screen, btn_brightness_minus, UI_BLUE, f_lg, "−", 13)
    labeled_button(
        screen, btn_auto_dim,
        UI_GREEN if device_settings.auto_dim_enabled else (55, 61, 77),
        f_tiny,
        (
            f"AUTO DIM {device_settings.auto_dim_minutes} MIN"
            if device_settings.auto_dim_enabled else "AUTO DIM OFF"
        ),
        13
    )
    labeled_button(screen, btn_brightness_plus, UI_BLUE, f_lg, "+", 13)

    theme_title = f_sm.render("THEME", True, UI_TEXT)
    screen.blit(theme_title, XY(18, 248))
    current_theme_rect = R(78, 274, 164, 58)
    labeled_button(
        screen, current_theme_rect, UI_AMBER, f_sm,
        current_theme.name.upper(), 14
    )
    labeled_button(screen, btn_theme_previous, UI_BLUE, f_lg, "‹", 14)
    labeled_button(screen, btn_theme_next, UI_BLUE, f_lg, "›", 14)
    labeled_button(screen, btn_wifi_setup, UI_GREEN, f_tiny, "WI-FI", 14)
    labeled_button(screen, btn_wifi_qr, UI_PURPLE, f_tiny, "WEB QR", 14)
    labeled_button(screen, btn_home_cards, UI_AMBER, f_tiny, "CARDS", 14)
    draw_pages_button()

def draw_home_cards_settings_screen(now):
    draw_page_base("HOME CARDS", now)
    layout_title = f_tiny.render("LAYOUT", True, UI_MUTED)
    screen.blit(layout_title, XY(18, 62))
    bubble = device_settings.home_card_layout == "bubble"
    labeled_button(
        screen, btn_card_layout_single,
        UI_GREEN if not bubble else (55, 61, 77),
        f_tiny, "1 FULL", 13
    )
    labeled_button(
        screen, btn_card_layout_bubble,
        UI_GREEN if bubble else (55, 61, 77),
        f_tiny, "2 HALVES", 13
    )

    left_title = f_tiny.render(
        "LEFT CARD" if bubble else "CARD", True, UI_MUTED
    )
    screen.blit(left_title, XY(18, 118))
    labeled_button(screen, btn_card_left_prev, UI_BLUE, f_lg, "‹", 13)
    labeled_button(
        screen, btn_card_left_label, UI_BLUE, f_tiny,
        HOME_CARD_LABELS[device_settings.home_cards[0]], 13
    )
    labeled_button(screen, btn_card_left_next, UI_BLUE, f_lg, "›", 13)

    if bubble:
        right_title = f_tiny.render("RIGHT CARD", True, UI_MUTED)
        screen.blit(right_title, XY(18, 186))
        labeled_button(screen, btn_card_right_prev, UI_BLUE, f_lg, "‹", 13)
        labeled_button(
            screen, btn_card_right_label, UI_PURPLE, f_tiny,
            HOME_CARD_LABELS[device_settings.home_cards[1]], 13
        )
        labeled_button(screen, btn_card_right_next, UI_BLUE, f_lg, "›", 13)
        labeled_button(screen, btn_card_swap, UI_AMBER, f_sm, "SWAP ORDER", 14)

    preview = f_tiny.render("PREVIEW", True, UI_MUTED)
    screen.blit(preview, XY(18, 292))
    for rect, kind, layout_x, layout_y, layout_w, layout_h in home_card_slots(
        top=318, height=64
    ):
        draw_home_card(
            rect, kind, now,
            layout_x=layout_x, layout_y=layout_y,
            layout_w=layout_w, layout_h=layout_h
        )

    labeled_button(
        screen, btn_home_cards_back, UI_BLUE, f_sm, "‹  SETTINGS", 16
    )


def draw_bluetooth_screen(now):
    draw_page_base("BLUETOOTH", now)
    labeled_button(
        screen, btn_bluetooth_search,
        UI_PURPLE if touch_bluetooth_busy else UI_BLUE, f_sm,
        "SEARCHING…" if touch_bluetooth_busy else "SEARCH DEVICES",
        15
    )

    status_surface = f_tiny.render(
        fit_label(touch_bluetooth_status, 42), True, UI_MUTED
    )
    screen.blit(
        status_surface,
        (X(160) - status_surface.get_width() // 2, Y(118))
    )

    visible = visible_bluetooth_devices()
    if visible:
        for device, rect in zip(visible, bluetooth_device_rects):
            connected = device.get('connected', False)
            accent = UI_GREEN if connected else (72, 80, 98)
            body = draw_info_card(screen, rect, accent, 13)
            name_surface = f_sm.render(
                fit_label(device.get('name', 'Bluetooth device'), 23),
                True, ink_on(body)
            )
            screen.blit(name_surface, (rect.x + X(13), rect.y + Y(5)))
            state = (
                "CONNECTED" if connected
                else ("PAIRED • TAP TO CONNECT" if device.get('paired')
                      else "AVAILABLE • TAP TO PAIR")
            )
            state_surface = f_tiny.render(
                state, True, muted_ink_on(body, UI_GREEN if connected else None)
            )
            screen.blit(state_surface, (rect.x + X(13), rect.y + Y(24)))
    else:
        empty_rect = R(18, 142, 284, 208)
        body = draw_info_card(screen, empty_rect, (72, 80, 98), 16)
        draw_centered_text(
            screen, f_sm, "No devices loaded", muted_ink_on(body), empty_rect
        )

    count = len(touch_bluetooth_devices)
    page_number = touch_bluetooth_offset // BLUETOOTH_PAGE_SIZE + 1
    page_count = max(1, math.ceil(count / BLUETOOTH_PAGE_SIZE))
    labeled_button(
        screen, btn_bluetooth_previous,
        UI_BLUE if touch_bluetooth_offset > 0 else (55, 61, 77),
        f_tiny, "PREV", 13
    )
    draw_centered_text(
        screen, f_sm, f"{page_number} / {page_count}", UI_MUTED,
        R(118, 360, 84, 44)
    )
    has_next = touch_bluetooth_offset + BLUETOOTH_PAGE_SIZE < count
    labeled_button(
        screen, btn_bluetooth_next,
        UI_BLUE if has_next else (55, 61, 77),
        f_tiny, "NEXT", 13
    )
    labeled_button(
        screen, btn_bluetooth_back, UI_BLUE, f_sm, "‹  SETTINGS", 16
    )

def wifi_key_label(value):
    names = {
        'shift': 'SHIFT',
        'space': 'SPACE',
        'backspace': '⌫',
        'connect': 'JOIN',
        'cancel': 'BACK',
    }
    if value in names:
        return names[value]
    if wifi_shift:
        symbols = {
            '1': '!', '2': '@', '3': '#', '4': '$', '5': '%',
            '6': '^', '7': '&', '8': '*', '9': '(', '0': ')',
            '-': '_', '.': ',', '/': '?',
        }
        return symbols.get(value, value.upper())
    return value

def draw_wifi_screen(now):
    draw_page_base("WI-FI", now)
    if wifi_password_open and wifi_target:
        name = fit_label(wifi_target.get('ssid', 'Wi-Fi'), 28)
        status = f_tiny.render(name, True, UI_MUTED)
        screen.blit(status, (X(160) - status.get_width() // 2, Y(64)))
        body = draw_modern_button(
            screen, btn_wifi_password_field, UI_PURPLE, UI_PURPLE, 14
        )
        secret = '•' * len(wifi_password_text) if wifi_password_text else "Password"
        color = contrasting_text(body) if wifi_password_text else contrasting_muted(body)
        draw_centered_text(
            screen, f_sm, fit_tail(secret, 22), color, btn_wifi_password_field
        )
        for value, rect in wifi_key_rects:
            if value == 'connect':
                border = UI_GREEN
            elif value == 'shift' and wifi_shift:
                border = UI_AMBER
            elif value in ('backspace', 'cancel'):
                border = UI_PINK
            else:
                border = UI_BLUE
            labeled_button(
                screen, rect, border, f_tiny, wifi_key_label(value), 10
            )
        draw_pages_button()
        return

    status = f_tiny.render(fit_label(wifi_status_label(), 42), True, UI_MUTED)
    screen.blit(status, (X(160) - status.get_width() // 2, Y(64)))
    labeled_button(
        screen, btn_wifi_scan,
        UI_PURPLE if wifi_busy else UI_BLUE, f_sm,
        "SCANNING…" if wifi_busy else "SCAN NETWORKS",
        15
    )
    visible = wifi_networks[:4]
    if visible:
        for network, rect in zip(visible, wifi_network_rects):
            border = UI_GREEN if network.get('connected') else UI_BLUE
            body = draw_modern_button(screen, rect, border, border, 13)
            lock = "LOCK " if network.get('secure') else ""
            name = f_sm.render(
                fit_label(f"{lock}{network['ssid']}", 22),
                True, contrasting_text(body)
            )
            screen.blit(name, (rect.x + X(12), rect.y + Y(6)))
            meta = f_tiny.render(
                f"{network['signal']}%", True, contrasting_muted(body)
            )
            screen.blit(meta, (rect.x + X(12), rect.y + Y(26)))
    else:
        empty = R(16, 142, 288, 200)
        body = draw_info_card(screen, empty, (72, 80, 98), 16)
        draw_centered_text(
            screen, f_sm, "Tap SCAN to find Wi-Fi", muted_ink_on(body), empty
        )
    if wifi_setup_required:
        labeled_button(screen, btn_wifi_skip, UI_AMBER, f_sm, "SKIP", 14)
    else:
        labeled_button(screen, btn_wifi_skip, UI_PURPLE, f_sm, "‹ SETTINGS", 14)
    draw_pages_button()

def draw_languages_screen(now):
    draw_page_base("LANGUAGES", now)
    for index, (language, rect) in enumerate(
        zip(LANGUAGE_STREAMS, language_card_rects)
    ):
        border = (UI_BLUE, UI_PURPLE, UI_AMBER)[index % 3]
        labeled_button(screen, rect, border, f_sm, language.upper(), 15)
    draw_pages_button()

def draw_language_stations_screen(now):
    title = selected_language.upper() if selected_language else "LANGUAGE"
    draw_page_base(title, now)

    status_surface = f_tiny.render(
        fit_label(language_stream_status, 42), True, UI_MUTED
    )
    screen.blit(
        status_surface,
        (160 - status_surface.get_width() // 2, 67)
    )

    streams = language_stream_cache.get(selected_language, [])
    visible_streams = streams[
        language_stream_offset:language_stream_offset + 5
    ]
    if language_stream_busy:
        loading_rect = R(18, 89, 284, 257)
        body = draw_info_card(screen, loading_rect, (72, 80, 98), 16)
        draw_centered_text(
            screen, f_sm, "Loading stations…", muted_ink_on(body), loading_rect
        )
    elif visible_streams:
        for stream, rect in zip(visible_streams, language_station_rects):
            body = draw_info_card(screen, rect, (72, 80, 98), 13)
            name_surface = f_sm.render(
                fit_label(stream['name'], 28), True, ink_on(body)
            )
            screen.blit(name_surface, (rect.x + X(13), rect.y + Y(7)))
            genre_surface = f_tiny.render(
                fit_label(stream.get('genre', 'Radio'), 34),
                True, muted_ink_on(body)
            )
            screen.blit(genre_surface, (rect.x + X(13), rect.y + Y(29)))
    elif selected_language:
        empty_rect = R(18, 89, 284, 257)
        body = draw_info_card(screen, empty_rect, (72, 80, 98), 16)
        draw_centered_text(
            screen, f_sm, "No stations available", muted_ink_on(body), empty_rect
        )

    page_number = language_stream_offset // 5 + 1
    page_count = max(1, math.ceil(len(streams) / 5))
    labeled_button(
        screen, btn_language_previous,
        UI_BLUE if language_stream_offset > 0 else (55, 61, 77),
        f_tiny, "PREV", 13
    )
    page_rect = R(118, 360, 84, 44)
    draw_centered_text(
        screen, f_sm, f"{page_number} / {page_count}", UI_MUTED, page_rect
    )
    has_next = language_stream_offset + 5 < len(streams)
    labeled_button(
        screen, btn_language_next,
        UI_BLUE if has_next else (55, 61, 77),
        f_tiny, "NEXT", 13
    )
    labeled_button(
        screen, btn_language_back, UI_BLUE, f_sm, "<  LANGUAGES", 16
    )

def draw_youtube_search_bar():
    typed = youtube_keyboard_text.strip() or youtube_touch_query
    body = draw_info_card(
        screen, btn_youtube_search_field, UI_PURPLE, 14
    )
    label = fit_tail(typed, 20) if typed else "Search YouTube..."
    color = ink_on(body) if typed else muted_ink_on(body)
    text = f_sm.render(label, True, color)
    screen.blit(
        text,
        (
            btn_youtube_search_field.x + 12,
            btn_youtube_search_field.centery - text.get_height() // 2,
        ),
    )
    labeled_button(screen, btn_youtube_search_go, UI_GREEN, f_sm, "GO", 14)

def draw_youtube_screen(now):
    draw_page_base("YOUTUBE", now)
    draw_youtube_search_bar()
    if youtube_keyboard_open:
        for label, value, rect in youtube_key_rects:
            if value == "search":
                border = UI_GREEN
            elif value == "backspace":
                border = UI_AMBER
            else:
                border = UI_BLUE
            labeled_button(screen, rect, border, f_tiny, label, 10)
        labeled_button(
            screen, btn_youtube_keyboard_close, UI_BLUE, f_sm, "RESULTS", 14
        )
        draw_pages_button()
        return

    status = "Searching…" if youtube_touch_busy else youtube_touch_status
    status_surface = f_tiny.render(fit_label(status, 42), True, UI_MUTED)
    screen.blit(
        status_surface,
        (160 - status_surface.get_width() // 2, 116)
    )
    for (label, query), rect in zip(YOUTUBE_PRESETS, youtube_preset_rects):
        selected = youtube_touch_query == query and not youtube_touch_busy
        labeled_button(
            screen, rect, UI_PINK if selected else UI_BLUE, f_tiny, label, 12
        )

    total = len(youtube_results_cache)
    has_prev = youtube_touch_offset > 0
    has_next = youtube_touch_offset + 4 < total
    labeled_button(
        screen, btn_youtube_prev,
        UI_BLUE if has_prev else (55, 61, 77), f_sm, "‹", 10
    )
    if total:
        page_label = (
            f"{youtube_touch_offset + 1}"
            f"-{min(youtube_touch_offset + 4, total)} / {total}"
        )
    else:
        page_label = "NO RESULTS"
    draw_centered_text(screen, f_tiny, page_label, UI_MUTED, youtube_page_rect)
    labeled_button(
        screen, btn_youtube_next,
        UI_BLUE if has_next else (55, 61, 77), f_sm, "›", 10
    )

    visible = youtube_results_cache[youtube_touch_offset:youtube_touch_offset + 4]
    if youtube_touch_busy and not visible:
        waiting = R(16, 232, 288, 184)
        body = draw_info_card(screen, waiting, (72, 80, 98), 16)
        draw_centered_text(
            screen, f_sm, "Searching YouTube…", muted_ink_on(body), waiting
        )
    elif visible:
        playing_id = current_youtube_id()
        for video, rect in zip(visible, youtube_result_rects):
            accent = (
                UI_GREEN if video.get('id') == playing_id else (72, 80, 98)
            )
            body = draw_info_card(screen, rect, accent, 12)
            now_prefix = "▶ " if video.get('id') == playing_id else ""
            title = f_sm.render(
                fit_label(now_prefix + (video.get('title') or 'YouTube'), 28),
                True, ink_on(body)
            )
            screen.blit(title, (rect.x + X(12), rect.y + Y(4)))
            meta = f_tiny.render(
                fit_label(
                    f"{video.get('uploader', '')} • {video.get('duration', '')}",
                    40
                ),
                True, muted_ink_on(body)
            )
            screen.blit(meta, (rect.x + X(12), rect.y + Y(22)))
    else:
        empty = R(16, 232, 288, 184)
        body = draw_info_card(screen, empty, (72, 80, 98), 16)
        draw_centered_text(
            screen, f_sm, "Type in the search bar", muted_ink_on(body), empty
        )
    draw_pages_button()

def draw_screensaver():
    # Lantern clock: huge dim time and a weather icon only.
    screen.fill((0, 0, 0))
    time_surf = f_xl.render(datetime.now().strftime("%H:%M"), True, (58, 58, 58))
    screen.blit(time_surf, time_surf.get_rect(center=XY(160, 200)))
    draw_weather_icon(screen, 160, 332, weather_type, 36)

def greeting_phrases():
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning", "காலை வணக்கம்"
    if hour < 17:
        return "Good afternoon", "மதிய வணக்கம்"
    return "Good evening", "மாலை வணக்கம்"

def should_show_house_greeting(previous_interaction, now):
    if greeting_shown_on == datetime.now().date():
        return False
    hour = datetime.now().hour
    if not (5 <= hour <= 11):
        return False
    idle = now - previous_interaction
    if idle >= 4 * 3600:
        return True
    if now - saver_started_at >= 20 * 60:
        return True
    previous_hour = datetime.fromtimestamp(previous_interaction).hour
    return previous_hour >= 21 or previous_hour < 5

def draw_house_greeting():
    screen.fill((0, 0, 0))
    english, tamil = greeting_phrases()
    station = sanitize_text(stations[current_idx]['name'] if stations else "TCRADIOS")
    temp = f"{current_temp}°C" if current_temp else "--°C"
    time_surf = f_xl.render(datetime.now().strftime("%H:%M"), True, UI_TEXT)
    screen.blit(time_surf, time_surf.get_rect(center=XY(160, 92)))
    draw_weather_icon(
        screen, 118, 168, weather_type, 22, dimmed=False, on_background=(0, 0, 0)
    )
    temp_surf = f_weather.render(temp, True, UI_TEXT)
    screen.blit(temp_surf, XY(148, 146))
    tamil_line = f_sm.render(f"{tamil}. {station} தயார்.", True, UI_TEXT)
    screen.blit(tamil_line, tamil_line.get_rect(center=XY(160, 250)))
    english_line = f_tiny.render(
        f"{english}. {temp}. {fit_label(station, 18)} is ready.",
        True, UI_MUTED
    )
    screen.blit(english_line, english_line.get_rect(center=XY(160, 286)))

adjusting_volume = False
show_volume_bar = False
volume_bar_timer = 0
touch_start_pos = (0,0)
touch_start_time = 0
active_page = "radio"
PAGE_ORDER = [
    "radio", "favorites", "forecast", "clock",
    "alarm", "system", "languages", "settings", "youtube"
]
btn_open_pages = R(16, 422, 228, 46)
fab_open = False
btn_fab = R(256, 416, 54, 54)
btn_sleep = R(16, 248, 140, 52)
btn_saver = R(164, 248, 140, 52)
btn_alarm = R(16, 308, 140, 52)
btn_mute = R(164, 308, 140, 52)
vol_rect = R(0, 0, 0, 0)
btn_pages = R(70, 430, 180, 38)
menu_card_rects = [
    R(16 + (index % 2) * 152, 68 + (index // 2) * 70, 136, 62)
    for index in range(8)
]
menu_card_rects.append(R(16, 348, 288, 62))
YOUTUBE_PRESETS = (
    ("LOFI", "lofi hip hop radio"),
    ("JAZZ", "smooth jazz radio"),
    ("NEWS", "live news"),
    ("CHILL", "chillout music"),
    ("POP", "pop hits radio"),
    ("CLASSICAL", "classical music radio"),
)
btn_youtube_search_field = R(16, 68, 220, 42)
btn_youtube_search_go = R(244, 68, 60, 42)
youtube_preset_rects = [
    R(16 + (index % 3) * 102, 134 + (index // 3) * 36, 92, 32)
    for index in range(6)
]
btn_youtube_prev = R(16, 210, 52, 28)
btn_youtube_next = R(252, 210, 52, 28)
youtube_page_rect = R(74, 210, 172, 28)
youtube_result_rects = [
    R(16, 246 + index * 44, 288, 40)
    for index in range(4)
]
btn_youtube_keyboard_close = R(70, 372, 180, 40)
youtube_keyboard_open = False
youtube_keyboard_text = ""
youtube_touch_query = ""
youtube_touch_status = "Choose a station or search"
youtube_touch_busy = False
youtube_touch_offset = 0
youtube_touch_pending = None

def build_youtube_keys():
    keys = []
    rows = ("1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm")
    y = 116
    key_w, key_h, gap = 28, 36, 3
    for row in rows:
        row_w = len(row) * key_w + (len(row) - 1) * gap
        extra = 0
        if row == "zxcvbnm":
            extra = 6 + 46
            row_w += extra
        x = (320 - row_w) // 2
        for character in row:
            keys.append((
                character.upper(),
                character,
                R(x, y, key_w, key_h)
            ))
            x += key_w + gap
        if row == "zxcvbnm":
            keys.append(("⌫", "backspace", R(x + 3, y, 46, key_h)))
        y += 42
    keys.append(("SPACE", "space", R(16, y, 140, 40)))
    keys.append(("SEARCH", "search", R(164, y, 140, 40)))
    return keys

youtube_key_rects = build_youtube_keys()

def fetch_youtube_search(query):
    global youtube_touch_pending
    try:
        videos, err = search_youtube(query)
        youtube_touch_pending = ('results', videos, err)
    except Exception as error:
        youtube_touch_pending = ('results', [], str(error))

def fetch_youtube_audio(video, auto=False):
    global youtube_touch_pending
    video_id = str(video.get('id', '')).strip()
    title = video.get('title') or 'YouTube Audio'
    try:
        audio_url, err = youtube_audio_url(video_id)
        if audio_url:
            youtube_touch_pending = ('play', video_id, title, audio_url, auto)
        else:
            youtube_touch_pending = (
                'error', err or 'Could not extract audio URL', auto, video_id
            )
    except Exception as error:
        youtube_touch_pending = ('error', str(error), auto, video_id)

def begin_youtube_search(query):
    global youtube_touch_busy, youtube_touch_status, youtube_touch_query
    global youtube_keyboard_open, youtube_keyboard_text
    query = str(query or '').strip()
    if youtube_touch_busy:
        return
    if not query:
        youtube_touch_status = "Type a search"
        return
    youtube_touch_query = query
    youtube_keyboard_text = query
    youtube_keyboard_open = False
    youtube_touch_busy = True
    youtube_touch_status = "Searching…"
    threading.Thread(
        target=fetch_youtube_search, args=(query,), daemon=True
    ).start()

def begin_youtube_play(video, auto=False):
    global youtube_touch_busy, youtube_touch_status
    if youtube_touch_busy or not video.get('id'):
        return False
    if not auto:
        youtube_skip_ids.clear()
        remember_youtube_queue(video.get('id'), video.get('title') or '')
    youtube_touch_busy = True
    youtube_touch_status = "Opening next…" if auto else "Opening audio…"
    threading.Thread(
        target=fetch_youtube_audio, args=(video, auto), daemon=True
    ).start()
    return True

def continue_youtube_queue(step=1, user=False):
    global youtube_queue_index
    if youtube_touch_busy:
        return True
    if len(youtube_queue) <= 1:
        return False
    n = len(youtube_queue)
    for _attempt in range(n):
        youtube_queue_index = (youtube_queue_index + step) % n
        video = youtube_queue[youtube_queue_index]
        video_id = str(video.get('id') or '').strip()
        if video_id and video_id not in youtube_skip_ids:
            return begin_youtube_play(video, auto=not user)
    return False

def youtube_queue_status():
    if not youtube_queue or youtube_queue_index < 0:
        return "Playing"
    total = len(youtube_queue)
    if total <= 1:
        return "Playing"
    nxt = youtube_queue[(youtube_queue_index + 1) % total]
    next_title = fit_label(nxt.get('title') or 'YouTube', 16)
    return f"{youtube_queue_index + 1}/{total} · next {next_title}"

def maybe_advance_youtube_queue():
    global _youtube_was_playing, _youtube_ended_handled
    if not current_youtube_id() or len(youtube_queue) <= 1:
        return
    try:
        state = player.get_state()
    except Exception:
        return
    if state in (
        vlc.State.Opening, vlc.State.Buffering, vlc.State.Playing, vlc.State.Paused
    ):
        if state == vlc.State.Playing:
            _youtube_was_playing = True
        _youtube_ended_handled = False
        return
    if state not in (vlc.State.Ended, vlc.State.Error):
        return
    if _youtube_ended_handled:
        return
    waited = time.time() - _youtube_play_started_at
    if not _youtube_was_playing and waited < 8:
        return
    if waited < 2:
        return
    _youtube_ended_handled = True
    _youtube_was_playing = False
    continue_youtube_queue(1, user=False)

def apply_youtube_touch_result():
    global youtube_touch_pending, youtube_touch_busy, youtube_touch_status
    global youtube_touch_offset, youtube_results_cache, active_page
    pending = youtube_touch_pending
    if not pending:
        return
    youtube_touch_pending = None
    youtube_touch_busy = False
    kind = pending[0]
    if kind == 'results':
        videos, err = pending[1], pending[2]
        if err and not videos:
            youtube_touch_status = err
            youtube_results_cache = []
        else:
            youtube_results_cache = videos
            youtube_touch_offset = 0
            count = len(videos)
            youtube_touch_status = (
                f"{count} result" + ("s" if count != 1 else "")
                if count else "No results"
            )
    elif kind == 'play':
        _kind, video_id, title, audio_url, auto = (
            pending[0], pending[1], pending[2], pending[3],
            pending[4] if len(pending) > 4 else False
        )
        play_youtube_station(video_id, title, audio_url)
        youtube_touch_status = youtube_queue_status()
        if not auto:
            active_page = "radio"
    elif kind == 'error':
        youtube_touch_status = str(pending[1])[:80]
        auto = pending[2] if len(pending) > 2 else False
        video_id = pending[3] if len(pending) > 3 else ''
        if video_id:
            youtube_skip_ids.add(video_id)
        if auto:
            continue_youtube_queue(1, user=False)

def handle_youtube_key(value):
    global youtube_keyboard_text
    if value == "backspace":
        youtube_keyboard_text = youtube_keyboard_text[:-1]
    elif value == "space":
        if len(youtube_keyboard_text) < 60:
            youtube_keyboard_text += " "
    elif value == "search":
        begin_youtube_search(youtube_keyboard_text)
    elif len(youtube_keyboard_text) < 60:
        youtube_keyboard_text += value
btn_favorite_toggle = R(90, 67, 140, 34)
favorite_card_rects = [
    R(16 + (index % 2) * 152, 112 + (index // 2) * 96, 136, 86)
    for index in range(6)
]
btn_alarm_minus = R(18, 204, 88, 42)
btn_alarm_toggle_page = R(116, 204, 88, 42)
btn_alarm_plus = R(214, 204, 88, 42)
btn_sleep_presets = [
    R(18 + index * 98, 282, 88, 48) for index in range(3)
]
btn_sleep_cancel = R(18, 344, 284, 54)
btn_safe_shutdown = R(55, 383, 210, 36)
system_card_rects = [
    R(18 + (index % 2) * 146, 76 + (index // 2) * 126, 138, 110)
    for index in range(4)
]
btn_audio_outputs = [
    R(14 + index * 76, 88, 70, 56) for index in range(4)
]
btn_brightness_minus = R(18, 184, 50, 48)
btn_auto_dim = R(78, 184, 164, 48)
btn_brightness_plus = R(252, 184, 50, 48)
btn_theme_previous = R(18, 274, 50, 58)
btn_theme_next = R(252, 274, 50, 58)
btn_wifi_setup = R(16, 353, 92, 50)
btn_wifi_qr = R(114, 353, 92, 50)
btn_home_cards = R(212, 353, 92, 50)
btn_wifi_scan = R(16, 86, 288, 40)
wifi_network_rects = [
    R(16, 142 + index * 50, 288, 46) for index in range(4)
]
btn_wifi_skip = R(70, 352, 180, 42)
btn_wifi_password_field = R(16, 86, 288, 40)

def build_wifi_keys():
    keys = []
    rows = ("1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm-./")
    y = 136
    key_w, key_h, gap = 28, 34, 3
    for row in rows:
        row_w = len(row) * key_w + (len(row) - 1) * gap
        x = (320 - row_w) // 2
        for character in row:
            keys.append((character, R(x, y, key_w, key_h)))
            x += key_w + gap
        y += 38
    keys.extend((
        ('shift', R(16, y, 70, 38)),
        ('space', R(92, y, 70, 38)),
        ('backspace', R(168, y, 52, 38)),
        ('connect', R(226, y, 78, 38)),
        ('cancel', R(70, 372, 180, 40)),
    ))
    return keys

wifi_key_rects = build_wifi_keys()
if not has_network_connection():
    wifi_setup_required = True
    active_page = "wifi"
    begin_wifi_scan()
btn_bluetooth_search = R(70, 64, 180, 42)
bluetooth_device_rects = [
    R(18, 142 + index * 52, 284, 46) for index in range(BLUETOOTH_PAGE_SIZE)
]
btn_bluetooth_previous = R(18, 360, 88, 44)
btn_bluetooth_next = R(214, 360, 88, 44)
btn_bluetooth_back = R(70, 430, 180, 38)
btn_card_layout_single = R(16, 76, 140, 40)
btn_card_layout_bubble = R(164, 76, 140, 40)
btn_card_left_prev = R(16, 132, 44, 44)
btn_card_left_label = R(66, 132, 188, 44)
btn_card_left_next = R(260, 132, 44, 44)
btn_card_right_prev = R(16, 194, 44, 44)
btn_card_right_label = R(66, 194, 188, 44)
btn_card_right_next = R(260, 194, 44, 44)
btn_card_swap = R(16, 248, 288, 40)
btn_home_cards_back = R(70, 430, 180, 38)
language_card_rects = [
    R(16 + (index % 2) * 152, 75 + (index // 2) * 83, 136, 70)
    for index in range(8)
]
language_station_rects = [
    R(18, 89 + index * 52, 284, 46) for index in range(5)
]
btn_language_previous = R(18, 360, 88, 44)
btn_language_next = R(214, 360, 88, 44)
btn_language_back = R(70, 430, 180, 38)

def adjust_volume(delta):
    global show_volume_bar, volume_bar_timer, last_interaction_time
    apply_live_volume(vol_level + delta)
    show_volume_bar = True
    volume_bar_timer = time.time()
    last_interaction_time = time.time()

def toggle_output_mute():
    global show_volume_bar, volume_bar_timer, last_interaction_time
    apply_live_volume(0 if vol_level > 0 else last_unmuted_volume)
    show_volume_bar = True
    volume_bar_timer = time.time()
    last_interaction_time = time.time()

def start_rotary_encoder():
    # CLK=GPIO5 (pin 29), DT=GPIO6 (pin 31), SW=GPIO13 (pin 33), GND=pin 30.
    global rotary_controls
    try:
        from gpiozero import DigitalInputDevice
        clock = DigitalInputDevice(5, pull_up=True, bounce_time=0.004)
        direction = DigitalInputDevice(6, pull_up=True)
        switch = DigitalInputDevice(13, pull_up=True, bounce_time=0.08)

        def rotated():
            adjust_volume(2 if direction.is_active else -2)

        clock.when_activated = rotated
        switch.when_activated = toggle_output_mute
        rotary_controls = [clock, direction, switch]
        print("Rotary encoder ready: GPIO 5, GPIO 6, switch GPIO 13")
    except Exception as error:
        rotary_controls = []
        print(f"Rotary encoder disabled: {error}")

rotary_controls = []
start_rotary_encoder()

btn_qr = R(15, 13, 42, 40)
btn_exit = R(268, 13, 37, 40)
_playback_controls = playback_control_layout()
vol_minus_rect = _playback_controls["vol_minus"]
vol_plus_rect = _playback_controls["vol_plus"]
vol_bar_rect = _playback_controls["vol_bar"]
btn_prev = _playback_controls["prev"]
btn_toggle = _playback_controls["toggle"]
btn_next = _playback_controls["next"]

while True:
    now = time.time()
    update_qr_code()
    
    if alarm_system.check_alarm() and not alarm_fade_active:
        alarm_fade_data = alarm_system.trigger_alarm(player, stations, current_idx, vol_level)
        alarm_fade_active = True
    
    handle_alarm_fade()
    handle_sleep_timer()
    apply_youtube_touch_result()
    maybe_advance_youtube_queue()
    apply_wifi_result()
    
    if now - last_weather_update > 1200:
        try:
            r = requests.get(device_settings.weather_url(), timeout=5)
            if r.status_code == 200:
                weather_data = r.json()
                data = weather_data['current_weather']
                current_temp = int(round(data['temperature']))
                code = data['weathercode']
                weather_type = weather_code_to_type(code)
                weather_label = weather_code_label(code)

                daily = weather_data.get('daily', {})
                dates = daily.get('time', [])
                codes = daily.get('weather_code', [])
                highs = daily.get('temperature_2m_max', [])
                lows = daily.get('temperature_2m_min', [])
                weather_forecast = []
                for date, daily_code, high, low in zip(
                    dates, codes, highs, lows
                ):
                    forecast_date = datetime.strptime(date, "%Y-%m-%d")
                    weather_forecast.append({
                        'day': forecast_date.strftime("%a"),
                        'type': weather_code_to_type(daily_code),
                        'label': weather_code_label(daily_code),
                        'high': int(round(high)),
                        'low': int(round(low))
                    })
        except: pass
        last_weather_update = now

    if (
        active_page in ("system", "settings", "clock", "radio")
        and now - last_system_update > 10
        and not system_stats_updating
    ):
        system_stats_updating = True
        last_system_update = now
        threading.Thread(target=refresh_system_stats, daemon=True).start()
    
    try:
        media = player.get_media()
        if media:
            try:
                m = media.get_meta(vlc.Meta.NowPlaying)
                if m:
                    meta_text = style_now_playing(m)
                else:
                    meta_text = style_now_playing(stations[current_idx]['name'])
            except: 
                meta_text = style_now_playing(stations[current_idx]['name'])
    except: 
        meta_text = style_now_playing(stations[current_idx]['name'])
    
    if show_volume_bar and now - volume_bar_timer > 3:
        show_volume_bar = False
        adjusting_volume = False
    
    hide_mouse_pointer()
    if saver_active:
        draw_screensaver()
    elif now < greeting_until:
        draw_house_greeting()
    else:
        if ui_palette_theme != current_theme.name:
            refresh_ui_palette()
        screen.blit(ui_background, (0, 0))
        draw_animated_ui_glow(screen, now)

        try: is_playing = player.get_state() == vlc.State.Playing
        except: is_playing = False

        logo_rect = R(0, 0, 1, 1)

        # Title bar stays its own strip. Cards fill the band under it.
        header_rect = R(8, 7, 304, 52)
        pygame.draw.rect(screen, UI_SURFACE, header_rect, border_radius=S(17))
        pygame.draw.rect(screen, (54, 75, 112), header_rect, S(1), border_radius=S(17))
        pygame.draw.line(screen, UI_BLUE, XY(28, 58), XY(145, 58), S(2))
        pygame.draw.line(screen, UI_PURPLE, XY(175, 58), XY(292, 58), S(2))

        btn_qr = R(15, 13, 42, 40)
        qr_body = draw_modern_button(screen, btn_qr, UI_BLUE, UI_BLUE, 12)
        draw_centered_text(screen, f_sm, "QR", contrasting_text(qr_body), btn_qr)

        title_rect = R(65, 10, 190, 38)
        draw_centered_text(screen, f_lg, "TC RADIOS", UI_TEXT, title_rect)
        if show_startup_ip and now < ip_display_time:
            ip_surface = f_tiny.render(f"{current_ip}:8080", True, UI_MUTED)
            screen.blit(ip_surface, (X(160) - ip_surface.get_width() // 2, Y(43)))

        btn_exit = R(268, 13, 37, 40)
        draw_modern_button(screen, btn_exit, (75, 30, 55), UI_PINK, 12)
        pygame.draw.line(screen, UI_TEXT, XY(279, 24), XY(294, 40), S(3))
        pygame.draw.line(screen, UI_TEXT, XY(294, 24), XY(279, 40), S(3))

        home_slots = home_card_slots()
        for rect, kind, layout_x, layout_y, layout_w, layout_h in home_slots:
            draw_home_card(
                rect, kind, now,
                layout_x=layout_x, layout_y=layout_y,
                layout_w=layout_w, layout_h=layout_h
            )
        if len(home_slots) == 2:
            seam_x = HOME_CARD_INSET + HOME_CARD_HALF_W
            notch = 16
            pygame.draw.rect(
                screen, UI_SURFACE_RAISED,
                R(seam_x - 2, HOME_CARD_TOP, 4, notch)
            )
            pygame.draw.rect(
                screen, UI_SURFACE_RAISED,
                R(seam_x - 2, HOME_CARD_TOP + HOME_CARD_HEIGHT - notch, 4, notch)
            )
            pygame.draw.line(
                screen, (54, 75, 112),
                XY(seam_x, HOME_CARD_TOP + 8),
                XY(seam_x, HOME_CARD_TOP + HOME_CARD_HEIGHT - 8),
                S(1)
            )

        # Volume and play controls stay on the now-playing card only.
        controls = playback_control_layout()
        vol_minus_rect = controls["vol_minus"]
        vol_plus_rect = controls["vol_plus"]
        vol_bar_rect = controls["vol_bar"]
        btn_prev = controls["prev"]
        btn_toggle = controls["toggle"]
        btn_next = controls["next"]
        if controls["visible"]:
            control_font = f_tiny if controls["compact"] else f_sm
            draw_circle_icon_button(screen, vol_minus_rect, UI_AMBER, "minus")
            pygame.draw.rect(screen, (37, 48, 72), vol_bar_rect, border_radius=S(8))
            fill_width = int(vol_bar_rect.width * vol_level / 100)
            if fill_width > 0:
                fill_rect = _Rect(
                    vol_bar_rect.x, vol_bar_rect.y, max(X(10), fill_width), vol_bar_rect.height
                )
                pygame.draw.rect(screen, UI_BLUE, fill_rect, border_radius=S(8))
            knob_x = vol_bar_rect.x + int(vol_bar_rect.width * vol_level / 100)
            knob_x = max(vol_bar_rect.x + X(6), min(vol_bar_rect.right - X(6), knob_x))
            draw_smooth_circle(screen, (knob_x, vol_bar_rect.centery), S(8), UI_TEXT)
            draw_smooth_circle(screen, (knob_x, vol_bar_rect.centery), S(4), UI_BLUE)
            vol_pct_surf = f_tiny.render(f"{vol_level}%", True, UI_TEXT)
            screen.blit(
                vol_pct_surf,
                (
                    X(controls["pct_x"]) - vol_pct_surf.get_width() // 2,
                    Y(controls["pct_y"])
                )
            )
            draw_circle_icon_button(screen, vol_plus_rect, UI_GREEN, "plus")

            draw_pulsing_border(
                screen,
                btn_toggle,
                UI_AMBER if is_playing else UI_GREEN,
                now
            )
            prev_body = draw_modern_button(screen, btn_prev, UI_BLUE, UI_BLUE, 16)
            toggle_color = UI_AMBER if is_playing else UI_GREEN
            toggle_body = draw_modern_button(
                screen, btn_toggle, toggle_color, toggle_color, 18
            )
            next_body = draw_modern_button(screen, btn_next, UI_PURPLE, UI_PURPLE, 16)
            draw_centered_text(
                screen, control_font, "PREV", contrasting_text(prev_body), btn_prev
            )
            draw_centered_text(
                screen, control_font, "PAUSE" if is_playing else "PLAY",
                contrasting_text(toggle_body),
                btn_toggle
            )
            draw_centered_text(
                screen, control_font, "NEXT", contrasting_text(next_body), btn_next
            )

        pages_body = draw_modern_button(
            screen, btn_open_pages, UI_BLUE, UI_BLUE, 16
        )
        draw_centered_text(
            screen, f_sm, "PAGES", contrasting_text(pages_body), btn_open_pages
        )

        if fab_open:
            dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 150))
            screen.blit(dim, (0, 0))
            panel = R(8, 236, 304, 136)
            pygame.draw.rect(screen, UI_SURFACE, panel, border_radius=S(18))
            pygame.draw.rect(screen, (54, 64, 91), panel, S(1), border_radius=S(18))
            sleep_fill = UI_PURPLE if alarm_system.sleep_timer_enabled else UI_SURFACE_RAISED
            moon_fill = UI_BLUE if saver_active else UI_SURFACE_RAISED
            alarm_fill = UI_AMBER if alarm_system.alarm_enabled else UI_SURFACE_RAISED
            mute_fill = UI_PINK if vol_level == 0 else UI_SURFACE_RAISED
            labeled_button(screen, btn_sleep, sleep_fill, f_sm, "SLEEP", 14)
            labeled_button(screen, btn_saver, moon_fill, f_sm, "MOON", 14)
            labeled_button(screen, btn_alarm, alarm_fill, f_sm, "ALARM", 14)
            labeled_button(
                screen, btn_mute, mute_fill, f_sm,
                "MUTE" if vol_level else "UNMUTE", 14
            )

        fab_fill = UI_PINK if fab_open else UI_PURPLE
        draw_smooth_circle(screen, btn_fab.center, S(26), fab_fill)
        draw_vector_icon(
            screen, btn_fab.center,
            "close" if fab_open else "gear",
            ink_on(fab_fill),
            radius=S(11),
            width=S(3),
        )
        if (
            not fab_open
            and (
                vol_level == 0
                or alarm_system.alarm_enabled
                or alarm_system.sleep_timer_enabled
            )
        ):
            pygame.draw.circle(
                screen,
                UI_PINK if vol_level == 0 else UI_AMBER,
                (btn_fab.centerx + X(16), btn_fab.centery - Y(16)),
                S(5),
            )

        if show_qr:
            qr_panel = R(31, 78, 258, 278)
            body = draw_info_card(screen, qr_panel, UI_BLUE, 18)
            screen.blit(qr_surface, XY(40, 88))
            draw_centered_text(
                screen, f_tiny, "LISTEN ALONG", ink_on(body),
                R(40, 328, 240, 16)
            )
            station_label = fit_label(
                stations[current_idx]['name'] if stations else "TCRADIOS", 22
            )
            draw_centered_text(
                screen, f_sm, station_label, muted_ink_on(body),
                R(40, 344, 240, 18)
            )

        if not show_qr:
            if active_page == "menu":
                draw_menu_screen(now)
            elif active_page == "favorites":
                draw_favorites_screen(now)
            elif active_page == "forecast":
                draw_forecast_screen(now)
            elif active_page == "clock":
                draw_clock_screen(now)
            elif active_page == "alarm":
                draw_alarm_screen(now)
            elif active_page == "system":
                draw_system_screen(now)
            elif active_page == "settings":
                draw_settings_screen(now)
            elif active_page == "home_cards":
                draw_home_cards_settings_screen(now)
            elif active_page == "bluetooth":
                draw_bluetooth_screen(now)
            elif active_page == "languages":
                draw_languages_screen(now)
            elif active_page == "language_stations":
                draw_language_stations_screen(now)
            elif active_page == "youtube":
                draw_youtube_screen(now)
            elif active_page == "wifi":
                draw_wifi_screen(now)
    
    for event in pygame.event.get():
        if event.type == pygame.MOUSEBUTTONDOWN:
            was_auto_dimmed = (
                target_display_brightness(now) < device_settings.brightness
            )
            previous_interaction = last_interaction_time
            last_interaction_time = now
            morning_greeting = (
                not wifi_setup_required
                and should_show_house_greeting(previous_interaction, now)
            )
            if was_auto_dimmed:
                device_settings.set_hardware_brightness(
                    device_settings.brightness
                )
                if morning_greeting:
                    greeting_until = now + 6
                    greeting_shown_on = datetime.now().date()
                continue
            touch_start_pos = event.pos
            touch_start_time = time.time()
            if saver_active:
                saver_active = False
                if morning_greeting:
                    greeting_until = now + 6
                    greeting_shown_on = datetime.now().date()
                continue
            if now < greeting_until:
                greeting_until = 0
                continue
            if morning_greeting:
                greeting_until = now + 6
                greeting_shown_on = datetime.now().date()
                continue
            if show_qr:
                show_qr = False
                continue
            if active_page == "menu":
                for page_index, card in enumerate(menu_card_rects):
                    if card.collidepoint(event.pos):
                        active_page = PAGE_ORDER[page_index]
                        break
                continue

            if active_page == "wifi":
                if btn_pages.collidepoint(event.pos):
                    wifi_password_open = False
                    wifi_setup_required = False
                    active_page = "menu"
                elif wifi_password_open:
                    for value, rect in wifi_key_rects:
                        if rect.collidepoint(event.pos):
                            handle_wifi_key(value)
                            break
                elif btn_wifi_scan.collidepoint(event.pos):
                    begin_wifi_scan()
                elif btn_wifi_skip.collidepoint(event.pos):
                    wifi_password_open = False
                    if wifi_setup_required:
                        wifi_setup_required = False
                        active_page = "radio"
                    else:
                        active_page = "settings"
                elif not wifi_busy:
                    for network, rect in zip(wifi_networks[:4], wifi_network_rects):
                        if rect.collidepoint(event.pos):
                            begin_wifi_connect(network)
                            break
                continue

            if active_page == "bluetooth":
                if btn_bluetooth_back.collidepoint(event.pos):
                    active_page = "settings"
                elif (
                    btn_bluetooth_search.collidepoint(event.pos)
                    and not touch_bluetooth_busy
                ):
                    touch_bluetooth_busy = True
                    threading.Thread(
                        target=scan_touch_bluetooth, daemon=True
                    ).start()
                elif btn_bluetooth_previous.collidepoint(event.pos):
                    if touch_bluetooth_offset > 0:
                        touch_bluetooth_offset = max(
                            0, touch_bluetooth_offset - BLUETOOTH_PAGE_SIZE
                        )
                elif btn_bluetooth_next.collidepoint(event.pos):
                    if (
                        touch_bluetooth_offset + BLUETOOTH_PAGE_SIZE
                        < len(touch_bluetooth_devices)
                    ):
                        touch_bluetooth_offset += BLUETOOTH_PAGE_SIZE
                elif not touch_bluetooth_busy:
                    for device, rect in zip(
                        visible_bluetooth_devices(), bluetooth_device_rects
                    ):
                        if rect.collidepoint(event.pos):
                            touch_bluetooth_busy = True
                            threading.Thread(
                                target=connect_touch_bluetooth,
                                args=(device['address'], device['name']),
                                daemon=True
                            ).start()
                            break
                continue

            if active_page == "home_cards":
                if btn_home_cards_back.collidepoint(event.pos):
                    active_page = "settings"
                elif btn_card_layout_single.collidepoint(event.pos):
                    set_home_card_layout("single")
                elif btn_card_layout_bubble.collidepoint(event.pos):
                    set_home_card_layout("bubble")
                elif btn_card_left_prev.collidepoint(event.pos):
                    cycle_home_card(0, -1)
                elif btn_card_left_next.collidepoint(event.pos):
                    cycle_home_card(0, 1)
                elif device_settings.home_card_layout == "bubble":
                    if btn_card_right_prev.collidepoint(event.pos):
                        cycle_home_card(1, -1)
                    elif btn_card_right_next.collidepoint(event.pos):
                        cycle_home_card(1, 1)
                    elif btn_card_swap.collidepoint(event.pos):
                        swap_home_cards()
                continue

            if active_page == "languages":
                if btn_pages.collidepoint(event.pos):
                    active_page = "menu"
                else:
                    for language, rect in zip(
                        LANGUAGE_STREAMS, language_card_rects
                    ):
                        if rect.collidepoint(event.pos):
                            if (
                                language_stream_busy
                                and language not in language_stream_cache
                            ):
                                break
                            selected_language = language
                            language_stream_offset = 0
                            active_page = "language_stations"
                            if language in language_stream_cache:
                                count = len(language_stream_cache[language])
                                language_stream_status = (
                                    f"{count} station"
                                    f"{'s' if count != 1 else ''}"
                                )
                            elif not language_stream_busy:
                                language_stream_busy = True
                                language_stream_status = "Loading stations…"
                                threading.Thread(
                                    target=load_language_streams,
                                    args=(language,),
                                    daemon=True
                                ).start()
                            break
                continue

            if active_page == "language_stations":
                streams = language_stream_cache.get(selected_language, [])
                if btn_language_back.collidepoint(event.pos):
                    active_page = "languages"
                elif (
                    btn_language_previous.collidepoint(event.pos)
                    and language_stream_offset > 0
                ):
                    language_stream_offset = max(
                        0, language_stream_offset - 5
                    )
                elif (
                    btn_language_next.collidepoint(event.pos)
                    and language_stream_offset + 5 < len(streams)
                ):
                    language_stream_offset += 5
                elif not language_stream_busy:
                    visible_streams = streams[
                        language_stream_offset:language_stream_offset + 5
                    ]
                    for stream, rect in zip(
                        visible_streams, language_station_rects
                    ):
                        if rect.collidepoint(event.pos):
                            play_language_stream(stream)
                            active_page = "radio"
                            break
                continue

            if active_page != "radio":
                if btn_pages.collidepoint(event.pos):
                    youtube_keyboard_open = False
                    active_page = "menu"
                elif active_page == "youtube":
                    if btn_youtube_search_go.collidepoint(event.pos):
                        query = youtube_keyboard_text.strip() or youtube_touch_query
                        if query:
                            begin_youtube_search(query)
                        else:
                            youtube_keyboard_open = True
                    elif btn_youtube_search_field.collidepoint(event.pos):
                        youtube_keyboard_open = True
                    elif youtube_keyboard_open:
                        if btn_youtube_keyboard_close.collidepoint(event.pos):
                            youtube_keyboard_open = False
                        else:
                            for _label, value, rect in youtube_key_rects:
                                if rect.collidepoint(event.pos):
                                    handle_youtube_key(value)
                                    break
                    elif not youtube_touch_busy:
                            for (_label, query), rect in zip(
                                YOUTUBE_PRESETS, youtube_preset_rects
                            ):
                                if rect.collidepoint(event.pos):
                                    youtube_keyboard_text = query
                                    begin_youtube_search(query)
                                    break
                            total = len(youtube_results_cache)
                            if (
                                btn_youtube_prev.collidepoint(event.pos)
                                and youtube_touch_offset > 0
                            ):
                                youtube_touch_offset = max(
                                    0, youtube_touch_offset - 4
                                )
                            elif (
                                btn_youtube_next.collidepoint(event.pos)
                                and youtube_touch_offset + 4 < total
                            ):
                                youtube_touch_offset += 4
                            else:
                                visible = youtube_results_cache[
                                    youtube_touch_offset:youtube_touch_offset + 4
                                ]
                                for video, rect in zip(
                                    visible, youtube_result_rects
                                ):
                                    if rect.collidepoint(event.pos):
                                        begin_youtube_play(video)
                                        break
                elif active_page == "favorites":
                    if btn_favorite_toggle.collidepoint(event.pos):
                        toggle_current_favorite()
                    else:
                        for favorite_index, card in enumerate(
                            favorite_card_rects
                        ):
                            if (
                                card.collidepoint(event.pos)
                                and favorite_index < len(favorite_indices)
                            ):
                                current_idx = favorite_indices[favorite_index]
                                play()
                                break
                elif active_page == "alarm":
                    if btn_alarm_toggle_page.collidepoint(event.pos):
                        alarm_system.alarm_enabled = (
                            not alarm_system.alarm_enabled
                        )
                        alarm_system.save_alarm_settings()
                    elif (
                        btn_alarm_minus.collidepoint(event.pos)
                        or btn_alarm_plus.collidepoint(event.pos)
                    ):
                        alarm_time = datetime.strptime(
                            alarm_system.alarm_time, "%H:%M"
                        )
                        minutes = (
                            -5 if btn_alarm_minus.collidepoint(event.pos) else 5
                        )
                        alarm_system.alarm_time = (
                            alarm_time + timedelta(minutes=minutes)
                        ).strftime("%H:%M")
                        alarm_system.save_alarm_settings()
                    else:
                        for preset, minutes in zip(
                            btn_sleep_presets, (15, 30, 60)
                        ):
                            if preset.collidepoint(event.pos):
                                alarm_system.start_sleep_timer(minutes)
                                break
                        if btn_sleep_cancel.collidepoint(event.pos):
                            alarm_system.stop_sleep_timer()
                elif active_page == "system":
                    if btn_safe_shutdown.collidepoint(event.pos):
                        if now <= shutdown_confirm_until:
                            request_touch_shutdown()
                        else:
                            shutdown_confirm_until = now + 5
                elif active_page == "settings":
                    for rect, output_name in zip(
                        btn_audio_outputs,
                        ("auto", "analog", "hdmi", "bluetooth")
                    ):
                        available = (
                            output_name in ("auto", "bluetooth")
                            or audio_manager.outputs.get(
                                output_name, {}
                            ).get('available', False)
                        )
                        if rect.collidepoint(event.pos) and available:
                            if output_name == "bluetooth":
                                active_page = "bluetooth"
                                if (
                                    not touch_bluetooth_devices
                                    and not touch_bluetooth_busy
                                ):
                                    try:
                                        touch_bluetooth_devices = (
                                            audio_manager.get_bluetooth_devices()
                                        )
                                        touch_bluetooth_offset = 0
                                    except Exception:
                                        pass
                            else:
                                audio_manager.set_output(output_name)
                            break
                    if (
                        btn_brightness_minus.collidepoint(event.pos)
                        or btn_brightness_plus.collidepoint(event.pos)
                    ):
                        change = (
                            -10
                            if btn_brightness_minus.collidepoint(event.pos)
                            else 10
                        )
                        device_settings.brightness = max(
                            10,
                            min(100, device_settings.brightness + change)
                        )
                        device_settings.save()
                        device_settings.set_hardware_brightness(
                            device_settings.brightness
                        )
                    elif btn_auto_dim.collidepoint(event.pos):
                        device_settings.auto_dim_enabled = (
                            not device_settings.auto_dim_enabled
                        )
                        device_settings.save()
                    elif btn_wifi_setup.collidepoint(event.pos):
                        wifi_from_settings = True
                        wifi_setup_required = False
                        wifi_password_open = False
                        active_page = "wifi"
                        if not wifi_networks and not wifi_busy:
                            begin_wifi_scan()
                    elif btn_wifi_qr.collidepoint(event.pos):
                        show_qr = True
                    elif btn_home_cards.collidepoint(event.pos):
                        active_page = "home_cards"
                    elif (
                        btn_theme_previous.collidepoint(event.pos)
                        or btn_theme_next.collidepoint(event.pos)
                    ):
                        current_theme_index = next(
                            (
                                index for index, theme_name
                                in enumerate(theme_names)
                                if THEMES[theme_name].name
                                == current_theme.name
                            ),
                            0
                        )
                        direction = (
                            -1 if btn_theme_previous.collidepoint(event.pos)
                            else 1
                        )
                        set_theme(
                            theme_names[
                                (current_theme_index + direction)
                                % len(theme_names)
                            ]
                        )
                continue

            if btn_fab.collidepoint(event.pos):
                fab_open = not fab_open
                continue
            if fab_open:
                if btn_sleep.collidepoint(event.pos):
                    if alarm_system.sleep_timer_enabled:
                        alarm_system.stop_sleep_timer()
                    else:
                        alarm_system.start_sleep_timer(30)
                elif btn_saver.collidepoint(event.pos):
                    saver_active = not saver_active
                    if saver_active:
                        saver_started_at = time.time()
                elif btn_alarm.collidepoint(event.pos):
                    alarm_system.alarm_enabled = not alarm_system.alarm_enabled
                    alarm_system.save_alarm_settings()
                elif btn_mute.collidepoint(event.pos):
                    apply_live_volume(0 if vol_level > 0 else last_unmuted_volume)
                fab_open = False
                continue
            if btn_open_pages.collidepoint(event.pos):
                fab_open = False
                active_page = "menu"
                continue
            if btn_exit.collidepoint(event.pos):
                save_playback_state(force=True)
                pygame.quit()
                sys.exit()
            if btn_qr.collidepoint(event.pos):
                show_qr = True
            if btn_prev.collidepoint(event.pos):
                skip_playback(-1)
            if btn_next.collidepoint(event.pos):
                skip_playback(1)
            if btn_toggle.collidepoint(event.pos):
                player.pause()
            if vol_minus_rect.collidepoint(event.pos):
                apply_live_volume(vol_level - 5)
                show_volume_bar = True
                volume_bar_timer = time.time()
            if vol_plus_rect.collidepoint(event.pos):
                apply_live_volume(vol_level + 5)
                show_volume_bar = True
                volume_bar_timer = time.time()
            if vol_bar_rect.collidepoint(event.pos):
                adjusting_volume = True
                apply_live_volume(
                    int((event.pos[0] - vol_bar_rect.x) * 100 / vol_bar_rect.width)
                )
                show_volume_bar = True
                volume_bar_timer = time.time()
        
        elif event.type == pygame.MOUSEBUTTONUP:
            dx = event.pos[0] - touch_start_pos[0]
            dy = event.pos[1] - touch_start_pos[1]
            dt = time.time() - touch_start_time
            if (
                active_page in PAGE_ORDER
                and abs(dx) > X(45)
                and abs(dx) > abs(dy)
                and dt < 2.5
            ):
                youtube_keyboard_open = False
                fab_open = False
                page_index = PAGE_ORDER.index(active_page)
                direction = 1 if dx < 0 else -1
                active_page = PAGE_ORDER[
                    (page_index + direction) % len(PAGE_ORDER)
                ]
                adjusting_volume = False
                continue

            if active_page == "radio" and logo_rect.collidepoint(touch_start_pos):
                dy = touch_start_pos[1] - event.pos[1]
                if dt > 1.0:
                    if alarm_system.sleep_timer_enabled:
                        alarm_system.stop_sleep_timer()
                    else:
                        alarm_system.start_sleep_timer(30)
                elif abs(dy) > Y(30):
                    apply_live_volume(vol_level + (5 if dy > 0 else -5))
                    show_volume_bar = True
                    volume_bar_timer = time.time()
            if adjusting_volume:
                save_playback_state(force=True)
            adjusting_volume = False
        
        elif event.type == pygame.MOUSEMOTION and adjusting_volume:
            if event.pos[0] >= vol_bar_rect.x and event.pos[0] <= vol_bar_rect.right:
                apply_live_volume(
                    int((event.pos[0] - vol_bar_rect.x) * 100 / vol_bar_rect.width)
                )
                volume_bar_timer = time.time()
    
    apply_display_brightness(now)
    pygame.display.flip()
    time.sleep(0.05)

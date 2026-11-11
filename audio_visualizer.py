"""Non-invasive real audio spectrum monitoring for PiRadio 7.

Captures only the default PulseAudio/PipeWire sink's .monitor via parec. Does
not alter VLC/MPV/Bible playback, mixer settings, or audio routing. If monitor
recording or NumPy is unavailable, returns a clear unavailable state rather
than inventing fake music-reactive bars.
"""
import shutil
import subprocess
import threading
import time

try:
    import numpy as np
except ImportError:
    np = None

BANDS = 24
SAMPLE_RATE = 16000
FRAME_SAMPLES = 2048
RETRY_SECONDS = 20
FREQUENCIES = (45, 60, 78, 100, 130, 170, 220, 285, 370, 480,
               620, 800, 1030, 1320, 1700, 2200, 2800, 3500, 4300,
               5100, 5900, 6600, 7200, 7800)


def spectrum_from_pcm(pcm):
    """24 logarithmic-range spectral amplitudes from signed mono 16-bit PCM."""
    if np is None:
        raise RuntimeError("python3-numpy required for live audio spectrum")
    if len(pcm) < FRAME_SAMPLES * 2:
        return tuple([0.0] * BANDS)
    samples = np.frombuffer(pcm[-FRAME_SAMPLES*2:], dtype="<i2").astype(np.float32)
    samples *= np.hanning(FRAME_SAMPLES)
    values = np.abs(np.fft.rfft(samples)) / (32768.0 * (FRAME_SAMPLES/4))
    freqs = np.fft.rfftfreq(FRAME_SAMPLES, 1 / SAMPLE_RATE)
    result = []
    for centre in FREQUENCIES:
        lo, hi = centre / 1.19, centre * 1.19
        mask = (freqs >= lo) & (freqs < hi)
        level = float(np.max(values[mask])) if np.any(mask) else 0.0
        # Smooth perceptual log response, no visualizer peaks from silence.
        result.append(max(0.0, min(1.0, level * 6.5)) ** 0.55)
    return tuple(result)


def monitor_command(sink):
    """Monitor the resolved current sink, never a microphone or input device."""
    if not isinstance(sink, str) or not sink or any(c.isspace() for c in sink):
        raise ValueError("Invalid audio sink name")
    return ["parec", "--raw", "--format=s16le", "--rate=16000",
            "--channels=1", "--device=" + sink + ".monitor"]


class AudioSpectrumMonitor:
    def __init__(self, run=subprocess.run, popen=subprocess.Popen,
                 executable=shutil.which, clock=time.monotonic):
        self._run = run
        self._popen = popen
        self._executable = executable
        self._clock = clock
        self._next_attempt = 0.0
        self._lock = threading.Lock()
        self._process = None
        self._active = False
        self._generation = 0
        self._levels = tuple([0.0] * BANDS)
        self._message = "Open Visualizer to start monitor"

    def snapshot(self):
        with self._lock:
            return {"levels": self._levels, "active": self._active,
                    "message": self._message}

    def _failure(self, generation, message):
        """Ignore late errors from monitor workers that have been stopped."""
        with self._lock:
            if self._generation == generation:
                self._levels = tuple([0.0] * BANDS)
                self._message = message
                self._active = False

    def start(self):
        with self._lock:
            if self._active or self._clock() < self._next_attempt:
                return
            self._active = True
            self._next_attempt = self._clock() + RETRY_SECONDS
            self._generation += 1
            generation = self._generation
            self._message = "Connecting to system audio monitor"
        threading.Thread(target=self._worker, args=(generation,),
                         daemon=True).start()

    def stop(self):
        with self._lock:
            self._active = False
            self._generation += 1
            process = self._process
            self._process = None
            self._levels = tuple([0.0] * BANDS)
            self._message = "Visualizer stopped"
            # Explicitly leaving and reopening allows an immediate retry.
            self._next_attempt = 0.0
        if process is not None:
            try:
                process.terminate()
            except OSError:
                pass

    def _worker(self, generation):
        if np is None:
            self._failure(generation, "Install python3-numpy for spectrum")
            return
        if not self._executable("parec") or not self._executable("pactl"):
            self._failure(generation, "PulseAudio monitor unavailable (parec/pactl)")
            return
        process = None
        try:
            r = self._run(["pactl", "get-default-sink"], text=True,
                          capture_output=True, timeout=3)
            if r.returncode != 0 or not r.stdout.strip():
                raise RuntimeError("No default audio sink found")
            sink = r.stdout.strip()
            cmd = monitor_command(sink)
            process = self._popen(cmd, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, bufsize=0)
            with self._lock:
                if self._generation != generation:
                    process.terminate()
                    return
                self._process = process
                self._message = "Real-time sink monitor"
            while True:
                with self._lock:
                    if self._generation != generation or not self._active:
                        break
                pcm = process.stdout.read(FRAME_SAMPLES * 2)
                if len(pcm) < FRAME_SAMPLES * 2:
                    raise RuntimeError("Audio monitor stream ended")
                levels = spectrum_from_pcm(pcm)
                with self._lock:
                    if self._generation != generation:
                        break
                    self._levels = levels
        except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError) as error:
            self._failure(generation, str(error)[:76] or "Audio monitor unavailable")
        finally:
            if process is not None:
                try:
                    process.terminate()
                    process.wait(timeout=1)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        process.kill()
                    except OSError:
                        pass
            with self._lock:
                if self._process is process:
                    self._process = None

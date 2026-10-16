"""
Victoria - Unified Audio Stream Capture
Captures microphone audio seamlessly using:
1. sounddevice (PortAudio) if library is present
2. Linux native arecord (ALSA) / pw-record (PipeWire) without needing PortAudio
"""

import subprocess
import shutil
import numpy as np
from typing import Optional
from rich.console import Console

console = Console()


class AudioStream:
    """
    Unified Microphone Audio Stream supporting sounddevice, arecord, and pw-record.
    """

    def __init__(self, sample_rate: int = 16000, channels: int = 1, device: Optional[int] = None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device

        self.backend = "unknown"
        self._proc: Optional[subprocess.Popen] = None

        # On modern Linux with PipeWire, pw-record captures full unattenuated native audio
        if shutil.which("pw-record"):
            self.backend = "pw-record"
            # Auto-ensure microphone input volume is at optimal level (85%)
            try:
                if shutil.which("wpctl"):
                    subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SOURCE@", "0.85"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        else:
            try:
                import sounddevice as sd
                sd.query_devices()
                self.backend = "sounddevice"
            except Exception:
                if shutil.which("arecord"):
                    self.backend = "arecord"
                else:
                    self.backend = "none"

        console.print(f"[dim]🎙️ Audio capture backend selected: {self.backend}[/dim]")

    def __enter__(self):
        if self.backend == "sounddevice":
            import sounddevice as sd
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                device=self.device,
            )
            self._stream.start()
            return self

        elif self.backend == "arecord":
            cmd = [
                "arecord",
                "-q",
                "-r", str(self.sample_rate),
                "-c", str(self.channels),
                "-f", "S16_LE",
                "-t", "raw",
            ]
            self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            return self

        elif self.backend == "pw-record":
            cmd = [
                "pw-record",
                "--rate", str(self.sample_rate),
                "--channels", str(self.channels),
                "--format", "s16",
                "-",
            ]
            self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            return self

        raise RuntimeError("No microphone recording utility found (sounddevice, arecord, or pw-record).")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.backend == "sounddevice" and hasattr(self, "_stream"):
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
        elif self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=1)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

    def read(self, frame_size: int) -> np.ndarray:
        """
        Read frame_size samples as float32 array in range [-1.0, 1.0].
        """
        if self.backend == "sounddevice":
            chunk, _ = self._stream.read(frame_size)
            return chunk.flatten()

        elif self._proc and self._proc.stdout:
            # 16-bit PCM = 2 bytes per sample
            bytes_to_read = frame_size * self.channels * 2
            raw_bytes = self._proc.stdout.read(bytes_to_read)
            if not raw_bytes or len(raw_bytes) < bytes_to_read:
                return np.zeros(frame_size, dtype=np.float32)

            int_samples = np.frombuffer(raw_bytes, dtype=np.int16)
            return int_samples.astype(np.float32) / 32768.0

        return np.zeros(frame_size, dtype=np.float32)

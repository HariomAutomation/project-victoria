"""
Victoria - Microphone Listener & Voice Activity Detection
Captures audio from the microphone and detects when the user is speaking.
Uses WebRTC VAD or Silero VAD for speech detection.
"""

import io
import wave
import threading
import queue
import numpy as np
from typing import Optional, Callable
from rich.console import Console

from victoria.config import get_config
from victoria.voice.audio_stream import AudioStream

console = Console()


class AudioListener:
    """
    Continuous microphone listener with Voice Activity Detection.

    Records audio in chunks, detects speech segments using WebRTC VAD,
    and returns complete utterances as numpy arrays.
    """

    def __init__(self):
        cfg = get_config()
        audio_cfg = cfg.audio_config
        vad_cfg = cfg.vad_config

        self.sample_rate: int = audio_cfg.get("sample_rate", 16000)
        self.channels: int = audio_cfg.get("channels", 1)
        self.chunk_duration: float = vad_cfg.get("chunk_duration", 0.03)  # 30ms
        self.chunk_size: int = int(self.sample_rate * self.chunk_duration)
        self.max_recording_seconds: int = audio_cfg.get("max_recording_seconds", 30)
        self.silence_duration: float = vad_cfg.get("silence_duration", 1.5)
        self.min_speech_duration: float = vad_cfg.get("min_speech_duration", 0.5)
        self.input_device: Optional[int] = audio_cfg.get("input_device", None)
        self.vad_aggressiveness: int = vad_cfg.get("aggressiveness", 2)

        self._vad = None
        self._is_listening = False
        self._audio_queue: queue.Queue = queue.Queue()

        self._init_vad()

    def _init_vad(self):
        """Initialize WebRTC VAD."""
        try:
            import webrtcvad
            self._vad = webrtcvad.Vad(self.vad_aggressiveness)
            console.print("[green]✅ WebRTC VAD initialized[/green]")
        except ImportError:
            console.print("[yellow]⚠️  webrtcvad not installed. VAD disabled, using simple energy detection.[/yellow]")
            self._vad = None

    def _is_speech(self, audio_chunk: np.ndarray) -> bool:
        """Check if an audio chunk contains speech."""
        if self._vad is not None:
            # WebRTC VAD expects 16-bit PCM at 16kHz in 10/20/30ms frames
            pcm_data = (audio_chunk * 32767).astype(np.int16).tobytes()
            try:
                return self._vad.is_speech(pcm_data, self.sample_rate)
            except Exception:
                # Fallback to energy-based detection
                return self._energy_vad(audio_chunk)
        return self._energy_vad(audio_chunk)

    def _energy_vad(self, audio_chunk: np.ndarray) -> bool:
        """Simple energy-based voice activity detection."""
        energy = np.sqrt(np.mean(audio_chunk ** 2))
        return energy > 0.012

    def record_until_silence(self, pre_audio: Optional[np.ndarray] = None) -> Optional[np.ndarray]:
        """
        Record audio from microphone with adaptive noise floor and rapid silence detection.
        Stops within ~0.9s of the user finishing speaking.
        """
        frames = []
        if pre_audio is not None:
            frames.append(pre_audio)

        frame_size = int(self.sample_rate * 0.03)  # 30ms frames
        chunk_dur = 0.03

        # Snappy silence cutoff: 0.9s of silence after speech stops
        max_silence_chunks = int(0.9 / chunk_dur)  # 30 chunks
        min_speech_chunks = 8                      # ~240ms of genuine speech minimum
        max_chunks = int(12.0 / chunk_dur)         # Max 12s timeout (safety limit)
        no_speech_timeout_chunks = int(3.5 / chunk_dur)  # If nobody spoke in 3.5s, exit

        speech_started = False
        speech_chunks = 0
        silence_chunks = 0
        initial_energies = []

        console.print("[cyan]🎤 Listening...[/cyan]")

        try:
            with AudioStream(
                sample_rate=self.sample_rate,
                channels=self.channels,
                device=self.input_device,
            ) as stream:
                # Flush initial buffer to clear any speaker echo
                try:
                    stream.read(frame_size * 2)
                except Exception:
                    pass

                for chunk_idx in range(max_chunks):
                    audio_chunk = stream.read(frame_size)
                    chunk_energy = float(np.sqrt(np.mean(audio_chunk ** 2)))

                    # Adaptively estimate room ambient noise during the first 6 frames (180ms)
                    if chunk_idx < 6:
                        initial_energies.append(chunk_energy)
                        noise_floor = float(np.median(initial_energies))
                    else:
                        noise_floor = float(np.median(initial_energies))

                    speech_thresh = max(0.014, noise_floor * 2.5)
                    silence_thresh = max(0.006, noise_floor * 1.4)

                    if chunk_energy > speech_thresh:
                        speech_started = True
                        speech_chunks += 1
                        silence_chunks = 0
                        frames.append(audio_chunk)
                    else:
                        if speech_started:
                            frames.append(audio_chunk)  # Keep audio during speech pauses
                            if chunk_energy < silence_thresh:
                                silence_chunks += 1

                            # Snappy cutoff: Stop recording as soon as owner finishes speaking!
                            if speech_chunks >= min_speech_chunks and silence_chunks >= max_silence_chunks:
                                console.print("[dim]⚡ Speech completed (silence detected)[/dim]")
                                break
                        else:
                            # Pre-speech buffer: keep the last 3 chunks (~90ms) to not clip first word
                            frames.append(audio_chunk)
                            if len(frames) > 4:
                                frames.pop(0)

                            # Early exit if user didn't speak within 3.5 seconds
                            if chunk_idx >= no_speech_timeout_chunks:
                                console.print("[dim]🔇 No speech detected within timeout[/dim]")
                                return None

        except Exception as e:
            console.print(f"[red]❌ Microphone error: {e}[/red]")
            return None

        if speech_chunks < min_speech_chunks:
            console.print("[dim]🔇 No speech detected[/dim]")
            return None

        recorded = np.concatenate(frames)
        duration = len(recorded) / self.sample_rate
        console.print(f"[green]✅ Recorded {duration:.1f}s of audio[/green]")
        return recorded

    def listen_continuous(self, callback: Callable[[np.ndarray], None], stop_event: threading.Event):
        """
        Continuously listen for speech segments and call callback for each.
        Runs until stop_event is set.

        Args:
            callback: Function to call with each speech segment (numpy array)
            stop_event: Threading event to signal stopping
        """
        frame_size = int(self.sample_rate * 0.03)

        while not stop_event.is_set():
            try:
                with AudioStream(
                    sample_rate=self.sample_rate,
                    channels=self.channels,
                    device=self.input_device,
                ) as stream:
                    frames = []
                    silence_chunks = 0
                    speech_chunks = 0
                    max_silence = int(self.silence_duration / 0.03)
                    min_speech = int(self.min_speech_duration / 0.03)
                    max_total = int(self.max_recording_seconds / 0.03)

                    for _ in range(max_total):
                        if stop_event.is_set():
                            break

                        chunk = stream.read(frame_size)

                        if self._is_speech(chunk):
                            speech_chunks += 1
                            silence_chunks = 0
                            frames.append(chunk)
                        else:
                            silence_chunks += 1
                            if speech_chunks > 0:
                                frames.append(chunk)
                            if speech_chunks >= min_speech and silence_chunks >= max_silence:
                                break

                    if speech_chunks >= min_speech and frames:
                        audio = np.concatenate(frames)
                        callback(audio)

            except Exception as e:
                console.print(f"[red]❌ Mic error: {e}[/red]")
                import time
                time.sleep(1)

    def get_audio_bytes(self, audio: np.ndarray) -> bytes:
        """Convert numpy audio array to WAV bytes for processing."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            pcm = (audio * 32767).astype(np.int16)
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()

    def save_audio(self, audio: np.ndarray, filepath: str):
        """Save audio to a WAV file."""
        import soundfile as sf
        sf.write(filepath, audio, self.sample_rate)
        console.print(f"[dim]💾 Audio saved: {filepath}[/dim]")

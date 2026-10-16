"""
Victoria - Wake Word Detection
Detects when the user says "Hey Victoria" to activate the assistant.
Supports two modes:
  1. STT Keyword: Uses faster-whisper to continuously transcribe short audio segments
     and checks for the wake phrase (flexible, works with any phrase)
  2. openWakeWord: Uses a dedicated wake word model (low-resource, always-on)
"""

import re
import numpy as np
import threading
from typing import Optional
from rich.console import Console

from victoria.config import get_config
from victoria.voice.audio_stream import AudioStream

console = Console()


class WakeWordDetector:
    """
    Detects the wake word/phrase to activate Victoria.

    Default mode is 'stt_keyword' which uses faster-whisper to transcribe
    short audio windows and check for the wake phrase. This is more flexible
    and works with any custom phrase like "Hey Victoria".
    """

    def __init__(self):
        cfg = get_config()
        ww_cfg = cfg.get("voice.wake_word", {})

        self.wake_phrase: str = cfg.wake_phrase.lower().strip()
        self.engine: str = ww_cfg.get("engine", "stt_keyword")
        self.sensitivity: float = ww_cfg.get("sensitivity", 0.5)
        self.sample_rate: int = cfg.audio_config.get("sample_rate", 16000)

        self._stt_model = None
        self._oww_model = None

        console.print(f"[cyan]🎯 Wake phrase: '{self.wake_phrase}' (engine: {self.engine})[/cyan]")

    def _get_stt_model(self):
        """Lazy-load the faster-whisper model for keyword detection."""
        if self._stt_model is None:
            from faster_whisper import WhisperModel
            cfg = get_config()
            stt_cfg = cfg.stt_config
            # Use tiny model for wake word to minimize latency
            model_size = "tiny"
            device = stt_cfg.get("device", "cpu")
            compute_type = stt_cfg.get("compute_type", "int8")
            console.print(f"[dim]Loading wake word STT model ({model_size})...[/dim]")
            self._stt_model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
                cpu_threads=2,
                num_workers=1,
            )
            console.print("[green]✅ Wake word STT model loaded[/green]")
        return self._stt_model

    def _init_openwakeword(self):
        """Initialize openWakeWord model."""
        try:
            import openwakeword
            from openwakeword.model import Model as OWWModel

            ww_cfg = get_config().get("voice.wake_word", {})
            model_path = ww_cfg.get("openwakeword_model")

            if model_path:
                self._oww_model = OWWModel(wakeword_models=[model_path])
            else:
                # Download default models
                openwakeword.utils.download_models()
                self._oww_model = OWWModel()

            console.print("[green]✅ openWakeWord initialized[/green]")
        except ImportError:
            console.print("[yellow]⚠️  openwakeword not installed. Falling back to STT keyword mode.[/yellow]")
            self.engine = "stt_keyword"
        except Exception as e:
            # Model download/init failures must not crash the wake loop.
            console.print(f"[yellow]⚠️  openWakeWord init failed ({e}). Falling back to STT keyword mode.[/yellow]")
            self._oww_model = None
            self.engine = "stt_keyword"

    def _check_phrase_match(self, text: str) -> bool:
        """
        Check if the transcribed text contains the wake phrase.
        Supports both English and Devanagari Hindi variants.
        """
        if not text:
            return False

        text_lower = text.lower().strip()
        # Clean punctuation for robust matching
        clean_text = "".join(c for c in text_lower if c.isalnum() or c.isspace()).strip()

        # Must explicitly contain a Victoria variant in English or Hindi.
        # Word-boundary matching prevents false wakes from words like "victory",
        # "victor hugo", or arbitrary substrings.
        match_keywords = [
            "victoria", "viktoria", "victoriya", "viktor", "victor",
            "vitoria", "vittoria", "biktoria", "bikoria", "wiktor", "wiktoria",
            "विक्टोरिया", "विकटोरिया", "विक्टोरीया", "विक्तोरिया", "विटोरिया",
            "विक्टर", "विक्टरी"
        ]
        wake_phrase = (self.wake_phrase or "").strip()
        if wake_phrase and wake_phrase not in match_keywords:
            match_keywords.append(wake_phrase)

        def _is_word(keyword: str, haystack: str) -> bool:
            return re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", haystack) is not None

        return any(_is_word(kw, clean_text) or _is_word(kw, text_lower) for kw in match_keywords)

    def wait_for_wake_word(
        self,
        stop_event: threading.Event,
        wake_event: Optional[threading.Event] = None,
    ) -> Optional[np.ndarray]:
        """
        Block until wake word is detected or stop_event is set.

        Args:
            stop_event: stops the whole assistant when set.
            wake_event: optional manual-wake request (e.g. floating widget
                click-to-listen). When set, the wake wait exits immediately.

        Returns:
            The audio that was captured after the wake word (trailing audio),
            or None if stopped (or manually woken via wake_event).
        """
        if self.engine == "openwakeword" and self._oww_model is None:
            self._init_openwakeword()

        if self.engine == "stt_keyword":
            return self._wait_stt_keyword(stop_event, wake_event)
        elif self.engine == "openwakeword":
            return self._wait_openwakeword(stop_event, wake_event)
        else:
            console.print(f"[red]❌ Unknown wake word engine: {self.engine}[/red]")
            return None

    def _wait_stt_keyword(
        self,
        stop_event: threading.Event,
        wake_event: Optional[threading.Event] = None,
    ) -> Optional[np.ndarray]:
        """
        Listen for wake word using continuous STT transcription.
        Records 2-second sliding windows and checks for the wake phrase.
        """
        model = self._get_stt_model()
        window_duration = 2.0  # seconds
        window_size = int(self.sample_rate * window_duration)
        step_duration = 0.5    # slide step
        step_size = int(self.sample_rate * step_duration)

        # Circular buffer for sliding window
        buffer = np.zeros(window_size, dtype=np.float32)

        frame_size = int(self.sample_rate * 0.03)  # 30ms frames

        console.print(f"[dim]👂 Waiting for '{self.wake_phrase}'...[/dim]")

        try:
            with AudioStream(
                sample_rate=self.sample_rate,
                channels=1,
                device=get_config().audio_config.get("input_device"),
            ) as stream:
                samples_since_check = 0

                while not stop_event.is_set():
                    # Manual wake request (floating widget click-to-listen)
                    if wake_event is not None and wake_event.is_set():
                        return None
                    chunk = stream.read(frame_size)

                    # Shift buffer and add new chunk
                    buffer = np.roll(buffer, -len(chunk))
                    buffer[-len(chunk):] = chunk
                    samples_since_check += len(chunk)

                    # Check every step_duration seconds
                    if samples_since_check >= step_size:
                        samples_since_check = 0

                        # Quick energy check first - skip transcription if silence/quiet background hum
                        peak = float(np.max(np.abs(buffer)))
                        rms = float(np.sqrt(np.mean(buffer ** 2)))
                        if peak < 0.003 or rms < 0.0018:
                            continue

                        # AGC normalize buffer so Whisper reliably identifies quiet speech
                        norm_buffer = (buffer / peak) * 0.7

                        # Transcribe with language=None to allow both Hindi and English wake words
                        segments, _ = model.transcribe(
                            norm_buffer,
                            language=None,
                            beam_size=1,
                            best_of=1,
                            without_timestamps=True,
                            vad_filter=True,
                        )
                        text = " ".join(seg.text for seg in segments).strip()

                        if text and self._check_phrase_match(text):
                            console.print(f"[green]🎯 Wake word detected! (heard: '{text}')[/green]")
                            return buffer  # Return the audio buffer for potential pre-speech

        except Exception as e:
            console.print(f"[red]❌ Mic error during wake word detection: {e}[/red]")

        return None

    def _wait_openwakeword(
        self,
        stop_event: threading.Event,
        wake_event: Optional[threading.Event] = None,
    ) -> Optional[np.ndarray]:
        """Listen for wake word using openWakeWord model."""
        if self._oww_model is None:
            self._init_openwakeword()
            if self._oww_model is None:
                return self._wait_stt_keyword(stop_event, wake_event)

        frame_size = 1280  # openWakeWord expects 80ms frames at 16kHz
        threshold = 0.5

        console.print("[dim]👂 Waiting for wake word (openWakeWord)...[/dim]")

        try:
            with AudioStream(
                sample_rate=self.sample_rate,
                channels=1,
                device=get_config().audio_config.get("input_device"),
            ) as stream:
                while not stop_event.is_set():
                    # Manual wake request (floating widget click-to-listen)
                    if wake_event is not None and wake_event.is_set():
                        return None
                    chunk = stream.read(frame_size)
                    chunk_int16 = (chunk * 32767).astype(np.int16)

                    prediction = self._oww_model.predict(chunk_int16)

                    for model_name, score in prediction.items():
                        if score > threshold:
                            console.print(f"[green]🎯 Wake word detected! ({model_name}: {score:.2f})[/green]")
                            return chunk

        except Exception as e:
            console.print(f"[red]❌ Mic error: {e}[/red]")

        return None

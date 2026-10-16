"""
Victoria - Speech-to-Text Engine
Converts recorded audio to text using faster-whisper (local, fast, accurate).
Supports auto language detection (Hindi, English, and more).
"""

import numpy as np
from typing import Optional, Tuple
from rich.console import Console

from victoria.config import get_config

console = Console()


class SpeechToText:
    """
    Speech-to-Text engine using faster-whisper.
    Supports multiple model sizes for speed/accuracy tradeoff.
    """

    def __init__(self):
        cfg = get_config()
        stt_cfg = cfg.stt_config

        self.model_size: str = stt_cfg.get("model_size", "base")
        self.language: Optional[str] = stt_cfg.get("language", None)
        self.device: str = stt_cfg.get("device", "cpu")
        self.compute_type: str = stt_cfg.get("compute_type", "int8")
        self.sample_rate: int = cfg.audio_config.get("sample_rate", 16000)

        self._model = None

    def _load_model(self):
        """Lazy-load the Whisper model."""
        if self._model is None:
            from faster_whisper import WhisperModel

            console.print(f"[dim]🔄 Loading STT model: {self.model_size} ({self.device}/{self.compute_type})...[/dim]")
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            console.print(f"[green]✅ STT model loaded: {self.model_size}[/green]")

    def transcribe(self, audio: np.ndarray) -> Tuple[str, str, float]:
        """
        Transcribe audio to text.

        Args:
            audio: numpy array of audio samples (float32, 16kHz, mono)

        Returns:
            Tuple of (transcribed_text, detected_language, confidence)
        """
        self._load_model()

        segments, info = self._model.transcribe(
            audio,
            language=self.language,
            beam_size=5,
            best_of=3,
            without_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=200,
            ),
        )

        if audio is None or len(audio) == 0:
            return "", "unknown", 0.0

        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms < 0.005:
            console.print("[dim]📝 STT: Audio below noise floor, skipped.[/dim]")
            return "", "unknown", 0.0

        # Collect all segments
        texts = []
        for segment in segments:
            texts.append(segment.text.strip())

        full_text = " ".join(texts).strip()
        detected_lang = info.language or "unknown"
        confidence = info.language_probability or 0.0

        # Whisper hallucination filter on silence/noise
        hallucinations = [
            "thank you", "thanks for watching", "subscribe", "subtitles by",
            "amara.org", "sous-titres", "c'est un peu", "c'est un", "merci",
            "you", "so", "the", "a", "...", "bye", "please subscribe"
        ]
        text_clean = full_text.lower().strip(" .!?,;\"'")
        if text_clean in hallucinations or (len(text_clean) <= 2 and text_clean not in ["हा", "ना", "ha", "na", "no"]):
            console.print(f"[dim]📝 STT: Filtered hallucination/noise: '{full_text}'[/dim]")
            return "", "unknown", 0.0

        # Reject foreign languages unless high confidence
        if detected_lang not in ["hi", "en", "ur", "ne", "mr", "gu", "pa"] and confidence < 0.90:
            console.print(f"[dim]📝 STT: Ignored foreign noise ({detected_lang}): '{full_text}'[/dim]")
            return "", "unknown", 0.0

        if full_text:
            console.print(f"[cyan]📝 STT: \"{full_text}\" [{detected_lang}, conf: {confidence:.2f}][/cyan]")
        else:
            console.print("[dim]📝 STT: (no text detected)[/dim]")

        return full_text, detected_lang, confidence

    def transcribe_stream(self, audio_chunks):
        """
        Transcribe audio in streaming mode (for real-time feedback).

        Args:
            audio_chunks: Iterator of numpy audio chunks

        Yields:
            Partial transcription strings
        """
        self._load_model()

        # Buffer chunks for batch processing
        buffer = []
        buffer_duration = 0.0

        for chunk in audio_chunks:
            buffer.append(chunk)
            buffer_duration += len(chunk) / self.sample_rate

            # Process every 1 second of audio
            if buffer_duration >= 1.0:
                audio = np.concatenate(buffer)
                segments, _ = self._model.transcribe(
                    audio,
                    language=self.language,
                    beam_size=1,
                    without_timestamps=True,
                )
                text = " ".join(seg.text for seg in segments).strip()
                if text:
                    yield text
                buffer = []
                buffer_duration = 0.0

        # Process remaining audio
        if buffer:
            audio = np.concatenate(buffer)
            segments, _ = self._model.transcribe(
                audio,
                language=self.language,
                beam_size=3,
                without_timestamps=True,
            )
            text = " ".join(seg.text for seg in segments).strip()
            if text:
                yield text

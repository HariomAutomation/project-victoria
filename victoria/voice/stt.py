import io
import wave
import json
import urllib.request
import numpy as np
from typing import Optional, Tuple
from rich.console import Console

from victoria.config import get_config

console = Console()


class SpeechToText:
    """
    Speech-to-Text engine using Sarvam AI Saaras:v3 (Primary) and faster-whisper (Offline Fallback).
    Supports auto language detection (Hindi, English, Hinglish).
    """

    def __init__(self):
        cfg = get_config()
        stt_cfg = cfg.stt_config

        self.model_size: str = stt_cfg.get("model_size", "base")
        self.language: Optional[str] = stt_cfg.get("language", "hi")
        if self.language and self.language.lower() in ["hi-in", "hi_in", "hindi"]:
            self.language = "hi"
        self.device: str = stt_cfg.get("device", "cpu")
        self.compute_type: str = stt_cfg.get("compute_type", "int8")
        self.sample_rate: int = cfg.audio_config.get("sample_rate", 16000)

        self._model = None

    def _transcribe_sarvam(self, audio: np.ndarray) -> Optional[Tuple[str, str, float]]:
        """
        High-fidelity Indian Speech-to-Text via Sarvam AI Saaras:v3 model.
        Flawless Devanagari and Hinglish recognition.
        """
        try:
            cfg = get_config()
            key = cfg.get_api_key("SARVAM_API_KEY")
            if not key:
                return None

            # Convert normalized float32 audio to 16-bit PCM WAV in memory
            int16_samples = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
            wav_buf = io.BytesIO()
            with wave.open(wav_buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(int16_samples.tobytes())
            wav_bytes = wav_buf.getvalue()

            boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
            body = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="voice.wav"\r\n'
                f"Content-Type: audio/wav\r\n\r\n"
            ).encode("utf-8") + wav_bytes + (
                f"\r\n--{boundary}\r\n"
                f'Content-Disposition: form-data; name="model"\r\n\r\n'
                f"saaras:v3\r\n"
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="language_code"\r\n\r\n'
                f"hi-IN\r\n"
                f"--{boundary}--\r\n"
            ).encode("utf-8")

            req = urllib.request.Request(
                "https://api.sarvam.ai/speech-to-text",
                data=body,
                headers={
                    "api-subscription-key": key,
                    "Content-Type": f"multipart/form-data; boundary={boundary}"
                }
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                transcript = data.get("transcript", "").strip()
                lang = data.get("language_code", "hi-IN")
                prob = float(data.get("language_probability", 0.95))
                if transcript and len(transcript) >= 1:
                    return transcript, lang, prob
        except Exception as e:
            console.print(f"[dim]Sarvam STT notice: {e}[/dim]")
        return None

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
        if audio is None or len(audio) == 0:
            return "", "unknown", 0.0

        peak = float(np.max(np.abs(audio)))
        if peak < 0.0008:
            console.print("[dim]📝 STT: Audio below noise floor, skipped.[/dim]")
            return "", "unknown", 0.0

        # Automatic Gain Control: Normalize quiet mic signals up to studio level (~0.7)
        normalized_audio = (audio / peak) * 0.7

        # Tier 1: Try Sarvam AI Saaras:v3 for crystal-clear Hindi/Hinglish
        sarvam_res = self._transcribe_sarvam(normalized_audio)
        if sarvam_res and sarvam_res[0]:
            full_text, detected_lang, confidence = sarvam_res
            console.print(f'[cyan]📝 STT (Sarvam Saaras): "{full_text}" [{detected_lang}, conf: {confidence:.2f}][/cyan]')
            return full_text, detected_lang, confidence

        # Tier 2: Offline Faster-Whisper Fallback
        self._load_model()

        segments, info = self._model.transcribe(
            normalized_audio,
            language=self.language,
            initial_prompt="नमस्ते हरिओम, बातचीत हिंदी और English में हो रही है।",
            beam_size=5,
            best_of=3,
            temperature=0.0,
            condition_on_previous_text=False,
            repetition_penalty=1.2,
            without_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=400,
                speech_pad_ms=200,
            ),
        )

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
            "you", "so", "the", "a", "...", "please subscribe"
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

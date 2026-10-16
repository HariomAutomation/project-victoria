"""
Victoria - Text-to-Speech Engine
Converts text responses to natural speech using Edge-TTS or Piper TTS.
Supports both online (Edge-TTS) and offline (Piper) modes.
"""

import asyncio
import subprocess
import os
import re
import numpy as np
from typing import Optional, Any
from rich.console import Console

from victoria.config import get_config

console = Console()


def clean_text_for_speech(text: str) -> str:
    """
    Sanitize text to create smooth, natural, human-like voice synthesis without robotic glitches.
    Strips markdown formatting, code blocks, asterisks, URLs, and emojis.
    Converts Latin Hinglish shortcuts into native Devanagari phonemes.
    """
    if not text:
        return ""

    # Replace code blocks
    text = re.sub(r"```[\s\S]*?```", " कोड स्क्रीन पर उपलब्ध है। ", text)
    # Replace inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove markdown links [title](url) -> title
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)
    # Remove markdown headers #, ##, etc.
    text = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r"[*_~]{1,3}", "", text)
    # Remove bullet markers (- or * at start of line)
    text = re.sub(r"^\s*[-*•]\s+", "", text, flags=re.MULTILINE)
    # Remove emojis and Unicode pictographs
    text = re.sub(r"[\U00010000-\U0010ffff]", "", text)
    # Remove decorative special characters
    text = re.sub(r"[⚡✨💜👋🎯🔍🗄️⚙️🎙️🙏💡🚀✅❌⚠️]", "", text)

    # Phonetic mappings for common transliterations into Devanagari for natural Indian accent
    replacements = [
        (r"\bJi Malik\b", "जी हरिओम"),
        (r"\bTheek hai Malik\b", "ठीक है हरिओम"),
        (r"\bMalik\b", "हरिओम"),
        (r"\bमालिक\b", "हरिओम"),
        (r"\bkahiye, main sun rahi hoon\b", "कहिए, मैं सुन रही हूँ"),
        (r"\bMaaf kijiye\b", "माफ़ कीजिए"),
        (r"\bVictoria\b", "विक्टोरिया"),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    # Normalize multiple newlines and spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


FEMALE_VOICES = {
    "swara": {
        "id": "hi-IN-SwaraNeural",
        "name": "स्वरा (Swara - भारतीय मधुर हिंदी)",
        "rate": "+5%",
        "provider": "edge-tts",
    },
    "sarvam": {
        "id": "sarvam-simran",
        "name": "सिमरन (Sarvam AI - नेचुरल इंडियन वॉइस)",
        "rate": "+0%",
        "provider": "sarvam",
    },
    "ava": {
        "id": "en-US-AvaMultilingualNeural",
        "name": "एवा (Ava - जार्विस स्टाइल मॉडर्न AI)",
        "rate": "+0%",
        "provider": "edge-tts",
    },
    "emma": {
        "id": "en-US-EmmaMultilingualNeural",
        "name": "एम्मा (Emma - सॉफ्ट व स्पष्ट AI)",
        "rate": "+0%",
        "provider": "edge-tts",
    },
    "seraphina": {
        "id": "de-DE-SeraphinaMultilingualNeural",
        "name": "सेराफ़िना (Seraphina - रॉयल व गंभीर AI)",
        "rate": "+0%",
        "provider": "edge-tts",
    },
}


class TextToSpeech:
    """
    Text-to-Speech engine with support for:
    - Edge-TTS: Microsoft's neural TTS (online, high quality, many voices)
    - Piper TTS: Offline, local TTS (fast, good quality)
    """

    def __init__(self):
        cfg = get_config()
        tts_cfg = cfg.tts_config

        self.engine: str = tts_cfg.get("engine", "edge-tts")
        self.edge_config: dict = tts_cfg.get("edge_tts", {})
        self.piper_config: dict = tts_cfg.get("piper", {})

        # Resolve initial voice key
        configured_voice = self.edge_config.get("voice", "hi-IN-SwaraNeural")
        self.current_voice_key = "swara"
        for k, v in FEMALE_VOICES.items():
            if v["id"] == configured_voice:
                self.current_voice_key = k
                break

        # Persistent audio cache dir
        from victoria.config import PROJECT_ROOT
        self._cache_dir = PROJECT_ROOT / "data" / "audio_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        # Temp dir for generated piper/espeak wav files
        self._temp_dir = str(self._cache_dir / "tmp")
        os.makedirs(self._temp_dir, exist_ok=True)

        self._current_player: Optional[subprocess.Popen] = None

        console.print(f"[green]✅ TTS engine: {self.engine} (Voice: {self.get_current_voice_name()})[/green]")

    def set_voice(self, voice_key: str, persist: bool = True) -> tuple[str, str]:
        """Switch Victoria's female AI speaking voice."""
        v_key = voice_key.lower().strip()
        if v_key in FEMALE_VOICES:
            v_info = FEMALE_VOICES[v_key]
        else:
            matched = None
            for k, info in FEMALE_VOICES.items():
                if v_key in k or v_key in info["id"].lower() or v_key in info["name"].lower():
                    matched = (k, info)
                    break
            if matched:
                v_key, v_info = matched
            else:
                v_key = "swara"
                v_info = FEMALE_VOICES["swara"]

        self.current_voice_key = v_key
        self.edge_config["voice"] = v_info["id"]
        self.edge_config["rate"] = v_info.get("rate", "+0%")

        if persist:
            try:
                cfg = get_config()
                cfg.set("voice.tts.edge_tts.voice", v_info["id"], persist=True)
                cfg.set("voice.tts.edge_tts.rate", v_info.get("rate", "+0%"), persist=True)
                console.print(f"[green]🎙️ Switched Victoria's voice to: {v_info['name']}[/green]")
            except Exception as e:
                console.print(f"[yellow]⚠️ Could not persist voice setting: {e}[/yellow]")

        return v_key, v_info["name"]

    def reload_voice_from_config(self) -> tuple[str, str]:
        """
        Re-read the persisted voice settings from config (used by the always-on
        voice daemon when the HUD switches voices in another process).
        Does not persist anything.
        """
        cfg = get_config()
        tts_cfg = cfg.tts_config
        self.edge_config = tts_cfg.get("edge_tts", {})
        configured_voice = self.edge_config.get("voice", "hi-IN-SwaraNeural")
        self.current_voice_key = "swara"
        for k, v in FEMALE_VOICES.items():
            if v["id"] == configured_voice:
                self.current_voice_key = k
                break
        console.print(f"[cyan]🔄 Voice reloaded from config: {self.get_current_voice_name()}[/cyan]")
        return self.current_voice_key, self.get_current_voice_name()

    def cycle_next_voice(self, persist: bool = True) -> tuple[str, str]:
        """Cycle to the next available female voice."""
        keys = list(FEMALE_VOICES.keys())
        current = getattr(self, "current_voice_key", "swara")
        try:
            idx = keys.index(current)
            next_key = keys[(idx + 1) % len(keys)]
        except ValueError:
            next_key = keys[0]
        return self.set_voice(next_key, persist=persist)

    def demo_all_voices(self) -> str:
        """Play a short demo sentence in each available female AI voice one by one."""
        samples = [
            ("swara", "नमस्ते हरिओम, मैं स्वरा हूँ — भारतीय मधुर हिंदी आवाज़।"),
            ("ava", "Hello Hariom, I am Ava — your Jarvis-style modern AI voice."),
            ("emma", "नमस्ते हरिओम, मैं एम्मा हूँ — सॉफ्ट और स्पष्ट आवाज़।"),
            ("seraphina", "नमस्ते हरिओम, मैं सेराफ़िना हूँ — शांत और गंभीर आवाज़।"),
        ]
        original_voice = getattr(self, "current_voice_key", "swara")
        for v_key, sample_text in samples:
            self.set_voice(v_key, persist=False)
            self.speak(sample_text, interruptible=False)
            import time
            time.sleep(0.3)
        self.set_voice(original_voice, persist=True)
        return "हरिओम जी, मैंने स्वरा, एवा, एम्मा और सेराफ़िना चारों आवाज़ों का नमूना सुना दिया है। आपको कौन सी सबसे अच्छी लगी?"

    def get_current_voice_name(self) -> str:
        current = getattr(self, "current_voice_key", "swara")
        return FEMALE_VOICES.get(current, {}).get("name", current)

    async def _speak_edge_tts(self, text: str, output_path: Optional[str] = None) -> str:
        """Generate speech using Edge-TTS with natural human cadence."""
        import edge_tts

        clean_text = clean_text_for_speech(text)
        if not clean_text:
            clean_text = text

        voice = self.edge_config.get("voice", "hi-IN-SwaraNeural")
        rate = self.edge_config.get("rate", "+5%")
        volume = self.edge_config.get("volume", "+0%")

        if output_path is None:
            audio_hash = abs(hash(clean_text)) % 10000000
            output_path = str(self._cache_dir / f"speech_{audio_hash}.mp3")

        communicate = edge_tts.Communicate(
            text=clean_text,
            voice=voice,
            rate=rate,
            volume=volume,
        )
        await communicate.save(output_path)
        return output_path

    def _speak_piper(self, text: str, output_path: Optional[str] = None) -> str:
        """Generate speech using Piper TTS."""
        model = self.piper_config.get("model", "en_US-lessac-medium")
        speed = self.piper_config.get("speed", 1.0)

        if output_path is None:
            output_path = os.path.join(self._temp_dir, "victoria_speech.wav")

        try:
            # Try using piper CLI
            cmd = [
                "piper",
                "--model", model,
                "--output_file", output_path,
                "--length-scale", str(1.0 / speed),
            ]
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            process.communicate(input=text.encode("utf-8"))

            if process.returncode != 0:
                raise RuntimeError("Piper TTS failed")

        except FileNotFoundError:
            # Fallback to espeak-ng
            console.print("[yellow]⚠️  Piper not found, using espeak-ng fallback[/yellow]")
            subprocess.run(
                ["espeak-ng", "-w", output_path, text],
                capture_output=True,
            )

        return output_path

    def _speak_sarvam(self, text: str, output_path: Optional[str] = None) -> str:
        """Generate native Indic speech using Sarvam AI Bulbul v3."""
        import base64
        import json
        import urllib.request

        clean_text = clean_text_for_speech(text)
        if not clean_text:
            clean_text = text

        key = os.environ.get("SARVAM_API_KEY")
        if not key:
            cfg = get_config()
            key = cfg.get("brain.models.sarvam.api_key")

        if not key:
            raise ValueError("SARVAM_API_KEY is not configured.")

        if output_path is None:
            audio_hash = abs(hash(clean_text)) % 10000000
            output_path = str(self._cache_dir / f"sarvam_{audio_hash}.wav")

        payload = json.dumps({
            "inputs": [clean_text[:450]],  # Sarvam allows up to 500 chars per chunk
            "target_language_code": "hi-IN",
            "speaker": "simran",
            "model": "bulbul:v3"
        }).encode("utf-8")

        headers = {
            "api-subscription-key": key,
            "Content-Type": "application/json"
        }

        req = urllib.request.Request("https://api.sarvam.ai/text-to-speech", data=payload, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            audios = data.get("audios", [])
            if audios:
                wav_bytes = base64.b64decode(audios[0])
                with open(output_path, "wb") as f:
                    f.write(wav_bytes)
                return output_path
        raise RuntimeError("Sarvam TTS returned no audio.")

    def _start_player_process(self, filepath: str) -> Optional[subprocess.Popen]:
        """Launch the audio player subprocess asynchronously so it can be terminated immediately."""
        players = [
            ["pw-play", filepath],            # PipeWire (Instant SIGKILL termination < 5ms)
            ["paplay", filepath],            # PulseAudio
            ["aplay", filepath],              # ALSA (WAV only)
            ["gst-play-1.0", "--quiet", "--no-interactive", filepath],  # Standard GStreamer fallback
            ["ffplay", "-nodisp", "-autoexit", filepath],  # FFmpeg
            ["mpv", "--no-video", filepath],   # MPV
        ]

        for cmd in players:
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._current_player = proc
                return proc
            except (FileNotFoundError, PermissionError):
                continue
            except Exception:
                continue

        console.print("[red]❌ No audio player found! Install pulseaudio, pipewire, or mpv.[/red]")
        return None

    def stop(self):
        """Immediately stop any currently playing speech (< 15ms)."""
        proc = getattr(self, "_current_player", None)
        if proc:
            try:
                proc.kill()
                proc.poll()
            except Exception:
                pass
        self._current_player = None

    def _play_audio(self, filepath: str):
        """Play an audio file using available system player with active tracking."""
        proc = self._start_player_process(filepath)
        if proc:
            try:
                proc.wait(timeout=60)
            except Exception:
                self.stop()
            finally:
                self._current_player = None

    def play_with_barge_in(
        self,
        filepath: str,
        listener: Optional[Any] = None,
        broadcaster: Optional[Any] = None,
    ) -> Optional[np.ndarray]:
        """
        Play audio while actively monitoring microphone for user barge-in (interruption).
        If Hariom starts speaking while Victoria is talking:
          1. Immediately kill audio player (< 20ms).
          2. Transition immediately into recording user's speech.
          3. Return the captured speech audio as numpy array.
        """
        proc = self._start_player_process(filepath)
        if proc is None:
            return None

        # If no listener is provided, wait normally
        if listener is None:
            try:
                proc.wait(timeout=60)
            except Exception:
                self.stop()
            self._current_player = None
            return None

        from victoria.voice.audio_stream import AudioStream

        frame_size = int(listener.sample_rate * 0.03)  # 30ms frames
        consecutive_speech = 0
        min_speech_trigger = 3  # ~90ms of continuous voice triggers instant cutoff
        speaker_energies = []
        recent_buffer = []      # Ring buffer (~180ms) to prevent clipping first syllable
        max_buffer_frames = 6

        try:
            with AudioStream(
                sample_rate=listener.sample_rate,
                channels=listener.channels,
                device=listener.input_device,
            ) as stream:
                try:
                    stream.read(frame_size)
                except Exception:
                    pass

                chunk_idx = 0
                while proc.poll() is None:
                    chunk = stream.read(frame_size)
                    chunk_idx += 1
                    energy = float(np.sqrt(np.mean(chunk ** 2)))

                    recent_buffer.append(chunk)
                    if len(recent_buffer) > max_buffer_frames:
                        recent_buffer.pop(0)

                    # Ignore initial 12 frames (~360ms) to allow speaker output to stabilize
                    if chunk_idx <= 12:
                        speaker_energies.append(energy)
                        continue

                    speaker_floor = float(np.median(speaker_energies[-12:])) if speaker_energies else 0.05
                    speaker_energies.append(energy)
                    if len(speaker_energies) > 25:
                        speaker_energies.pop(0)

                    # Dynamic interrupt threshold: user speaking directly into mic produces energy well above speaker bleed
                    bleed_ceiling = max(0.24, speaker_floor * 1.40)

                    is_voice = False
                    if listener._vad is not None:
                        try:
                            pcm_data = (np.clip(chunk, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
                            is_voice = listener._vad.is_speech(pcm_data, listener.sample_rate)
                        except Exception:
                            is_voice = False

                    # Interruption triggers when user speaks loudly over TTS for 4 frames (~120ms)
                    if energy > bleed_ceiling and is_voice:
                        consecutive_speech += 1
                    else:
                        consecutive_speech = max(0, consecutive_speech - 1)

                    if consecutive_speech >= min_speech_trigger:
                        console.print("\n[bold yellow]🛑 [Barge-In] Hariom started speaking! Victoria stopping immediately...[/bold yellow]")
                        self.stop()

                        if broadcaster:
                            broadcaster.listening()

                        # Collect the buffered audio capturing the beginning of utterance
                        pre_audio = np.concatenate(recent_buffer) if recent_buffer else None

                        # Continue recording Hariom's speech until he finishes speaking
                        captured_audio = listener.record_until_silence(
                            pre_audio=pre_audio,
                            stream=stream,
                        )

                        # Filter out self-echo if microphone only recorded Victoria's own trailing audio
                        if captured_audio is not None and len(captured_audio) > 0:
                            try:
                                from victoria.voice.speaker_verify import SpeakerVerifier
                                sv = SpeakerVerifier()
                                if sv.is_victoria_echo(captured_audio):
                                    console.print("[dim]🔇 Filtered out self-echo from barge-in capture[/dim]")
                                    return None
                            except Exception:
                                pass

                        return captured_audio

        except Exception as e:
            console.print(f"[dim]Barge-in notice: {e}[/dim]")
            if proc.poll() is None:
                try:
                    proc.wait(timeout=30)
                except Exception:
                    self.stop()

        self._current_player = None
        return None

    def speak(
        self,
        text: str,
        blocking: bool = True,
        interruptible: bool = True,
        listener: Optional[Any] = None,
        broadcaster: Optional[Any] = None,
    ) -> Optional[np.ndarray]:
        """
        Convert text to speech and play it.
        If interruptible is True and listener is provided, monitors for user interruption (barge-in).
        Returns captured speech if interrupted, otherwise None.
        """
        if not text or not text.strip():
            return None

        console.print(f"[magenta]🗣️  Victoria: {text}[/magenta]")

        try:
            current_info = FEMALE_VOICES.get(getattr(self, "current_voice_key", "swara"), {})
            if current_info.get("provider") == "sarvam" or self.engine == "sarvam":
                try:
                    audio_path = self._speak_sarvam(text)
                except Exception as sarvam_err:
                    console.print(f"[yellow]⚠️ Sarvam TTS notice ({sarvam_err}), using Edge-TTS fallback[/yellow]")
                    loop = asyncio.new_event_loop()
                    try:
                        audio_path = loop.run_until_complete(self._speak_edge_tts(text))
                    finally:
                        loop.close()
            elif self.engine == "edge-tts":
                # Run async Edge-TTS in sync context
                loop = asyncio.new_event_loop()
                try:
                    audio_path = loop.run_until_complete(self._speak_edge_tts(text))
                finally:
                    loop.close()
            elif self.engine == "piper":
                audio_path = self._speak_piper(text)
            else:
                console.print(f"[red]❌ Unknown TTS engine: {self.engine}[/red]")
                return None

            if interruptible and listener is not None:
                return self.play_with_barge_in(audio_path, listener=listener, broadcaster=broadcaster)
            elif blocking:
                self._play_audio(audio_path)
            else:
                import threading
                t = threading.Thread(target=self._play_audio, args=(audio_path,), daemon=True)
                t.start()

        except Exception as e:
            console.print(f"[red]❌ TTS error: {e}[/red]")

        return None

    async def speak_async(self, text: str):
        """Async version of speak - for use in async contexts."""
        if not text or not text.strip():
            return

        console.print(f"[magenta]🗣️  Victoria: {text}[/magenta]")

        try:
            if self.engine == "edge-tts":
                audio_path = await self._speak_edge_tts(text)
            elif self.engine == "piper":
                # Piper is sync, run in executor
                loop = asyncio.get_event_loop()
                audio_path = await loop.run_in_executor(None, self._speak_piper, text)
            else:
                return

            # Play in executor to not block
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._play_audio, audio_path)

        except Exception as e:
            console.print(f"[red]❌ TTS error: {e}[/red]")

    def switch_engine(self, engine: str):
        """Switch between TTS engines at runtime."""
        if engine in ("edge-tts", "piper"):
            self.engine = engine
            console.print(f"[green]🔄 TTS engine switched to: {engine}[/green]")
        else:
            console.print(f"[red]❌ Unknown engine: {engine}. Use 'edge-tts' or 'piper'[/red]")


    @staticmethod
    async def list_edge_voices(language: str = "en") -> list:
        """List available Edge-TTS voices for a language."""
        import edge_tts
        voices = await edge_tts.list_voices()
        return [v for v in voices if v["Locale"].startswith(language)]

    def cleanup(self):
        """Clean up temporary files."""
        import shutil
        if hasattr(self, "_temp_dir") and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)

    def __del__(self):
        try:
            self.cleanup()
        except Exception:
            pass


# Process-wide TTS singleton: one shared player so stop_assistant_speech and
# switch_assistant_voice always act on the audio that is actually playing.
_tts_singleton: Optional["TextToSpeech"] = None


def get_tts() -> "TextToSpeech":
    """Get the shared TextToSpeech instance for this process."""
    global _tts_singleton
    if _tts_singleton is None:
        _tts_singleton = TextToSpeech()
    return _tts_singleton

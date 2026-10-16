"""
Victoria - Text-to-Speech Engine
Converts text responses to natural speech using Edge-TTS or Piper TTS.
Supports both online (Edge-TTS) and offline (Piper) modes.
"""

import asyncio
import subprocess
import os
from typing import Optional
from rich.console import Console

from victoria.config import get_config

console = Console()


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

        # Persistent audio cache dir
        from victoria.config import PROJECT_ROOT
        self._cache_dir = PROJECT_ROOT / "data" / "audio_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        console.print(f"[green]✅ TTS engine: {self.engine}[/green]")

    async def _speak_edge_tts(self, text: str, output_path: Optional[str] = None) -> str:
        """Generate speech using Edge-TTS."""
        import edge_tts

        voice = self.edge_config.get("voice", "hi-IN-SwaraNeural")
        rate = self.edge_config.get("rate", "+0%")
        volume = self.edge_config.get("volume", "+0%")

        if output_path is None:
            audio_hash = abs(hash(text)) % 10000000
            output_path = str(self._cache_dir / f"speech_{audio_hash}.mp3")

        communicate = edge_tts.Communicate(
            text=text,
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

    def _play_audio(self, filepath: str):
        """Play an audio file using available system player."""
        players = [
            ["gst-play-1.0", "--quiet", "--no-interactive", filepath],  # Standard GStreamer (Ubuntu default)
            ["pw-play", filepath],            # PipeWire
            ["paplay", filepath],            # PulseAudio
            ["aplay", filepath],              # ALSA (WAV only)
            ["ffplay", "-nodisp", "-autoexit", filepath],  # FFmpeg
            ["mpv", "--no-video", filepath],   # MPV
        ]

        for cmd in players:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=60,
                )
                if result.returncode == 0:
                    return
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        console.print("[red]❌ No audio player found! Install pulseaudio, pipewire, or mpv.[/red]")

    def speak(self, text: str, blocking: bool = True):
        """
        Convert text to speech and play it.

        Args:
            text: The text to speak
            blocking: If True, wait for speech to complete
        """
        if not text or not text.strip():
            return

        console.print(f"[magenta]🗣️  Victoria: {text}[/magenta]")

        try:
            if self.engine == "edge-tts":
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
                return

            if blocking:
                self._play_audio(audio_path)
            else:
                import threading
                t = threading.Thread(target=self._play_audio, args=(audio_path,), daemon=True)
                t.start()

        except Exception as e:
            console.print(f"[red]❌ TTS error: {e}[/red]")

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

    def set_voice(self, voice_name: str):
        """Change the Edge-TTS voice."""
        self.edge_config["voice"] = voice_name
        console.print(f"[green]🔄 Voice changed to: {voice_name}[/green]")

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
        self.cleanup()

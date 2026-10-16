"""
Victoria - Microphone Diagnostic Tool
Tests audio input hardware, measures RMS sound levels, and confirms recording capability.
"""

import sys
import numpy as np
from pathlib import Path
from rich.console import Console

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from victoria.config import get_config

console = Console()


def test_mic():
    console.print("[bold cyan]🎤 Testing Microphone Input Hardware[/bold cyan]\n")

    try:
        import sounddevice as sd
    except ImportError:
        console.print("[red]sounddevice is not installed. Run: pip install sounddevice[/red]")
        return

    # List devices
    default_in = sd.query_devices(kind="input")
    console.print(f"[green]Default Input Device:[/green] {default_in['name']} (Sample Rate: {default_in['default_samplerate']} Hz)\n")

    cfg = get_config()
    sample_rate = cfg.audio_config.get("sample_rate", 16000)
    duration = 3.0  # seconds

    console.print(f"[bold yellow]Recording 3 seconds of ambient/speech audio at {sample_rate}Hz...[/bold yellow]")
    try:
        recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="float32")
        sd.wait()
        audio = np.squeeze(recording)

        rms = np.sqrt(np.mean(audio**2))
        peak = np.max(np.abs(audio))

        console.print("[bold green]✅ Audio captured successfully![/bold green]")
        console.print(f"• RMS Level: {rms:.4f}")
        console.print(f"• Peak Level: {peak:.4f}")

        if peak < 0.01:
            console.print("[yellow]⚠️ Audio levels are very quiet. Please check microphone volume/gain in system settings.[/yellow]")
        else:
            console.print("[bold green]✨ Microphone is responsive and working normally![/bold green]")

    except Exception as e:
        console.print(f"[red]❌ Error testing microphone: {e}[/red]")


if __name__ == "__main__":
    test_mic()

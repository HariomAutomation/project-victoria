"""
Victoria - Voice Enrollment & Verification System (आवाज़ पहचान नामांकन प्रणाली)
Records the owner's voice samples to create a unique mathematical voice fingerprint (embedding).
Once enrolled, Victoria will ONLY respond to the owner and reject unauthorized voices.
"""

import sys
import numpy as np
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from victoria.voice.audio_stream import AudioStream

console = Console()

ENROLL_PROMPTS = [
    "Namaste Victoria, main tumhara malik bol raha hoon.",
    "Victoria, system ka status check karo aur mujhe verify karo.",
    "Hey Victoria, this is my authentic voice profile.",
    "Victoria, system ke sabhi tools aur files ko surakshit rakho.",
    "Hey Victoria, I am your owner, voice authorization confirmed.",
]


def record_sample(sample_rate: int = 16000, duration_seconds: float = 4.0) -> np.ndarray:
    """Record a 4-second audio sample using native AudioStream (arecord/pw-record)."""
    with AudioStream(sample_rate=sample_rate, channels=1) as stream:
        total_samples = int(duration_seconds * sample_rate)
        frame_size = int(sample_rate * 0.1)  # 100ms frames
        chunks = []
        samples_read = 0

        while samples_read < total_samples:
            chunk = stream.read(frame_size)
            chunks.append(chunk)
            samples_read += len(chunk)

    audio = np.concatenate(chunks)
    return np.squeeze(audio).astype(np.float32)


def enroll():
    from victoria.voice.tts import TextToSpeech
    from victoria.voice.voice_events import broadcaster
    from victoria.voice.voice_onboarding import run_first_time_voice_enrollment

    tts = TextToSpeech()
    success = run_first_time_voice_enrollment(tts=tts, broadcaster=broadcaster)
    if success:
        try:
            import subprocess
            subprocess.run(["systemctl", "--user", "restart", "victoria.service"], check=False)
            console.print("[green]🔄 Background service (victoria.service) aapki nayi voice profile ke sath restart ho gayi hai.[/green]")
        except Exception:
            pass

        # Optional Verification Test right after enrollment
        test_now = Prompt.ask("\n[bold cyan]Kya aap abhi apni awaz test karna chahte hain? (y/n)[/bold cyan]", default="y")
        if test_now.lower() == "y":
            test_voice()

    else:
        console.print("[red]❌ Enrollment fail ho gaya: koi valid audio nahi mila.[/red]")


def test_voice(encoder=None, master_embedding=None, sample_rate=16000):
    """Test voice match against enrolled profile."""
    profile_path = PROJECT_ROOT / "config" / "voice_profiles" / "owner.npy"
    if master_embedding is None:
        if not profile_path.exists():
            console.print("[red]❌ Koi voice profile nahi mili. Pehle enrollment (victoria-enroll) karein.[/red]")
            return
        master_embedding = np.load(str(profile_path))

    if encoder is None:
        from victoria.voice.speaker_encoder import VoiceEncoder
        encoder = VoiceEncoder()

    console.print("\n[bold cyan]🧪 Awaz Satyaapan Test (Voice Match Test)[/bold cyan]")
    console.print("[dim]Kuch bhi boliye (jaise 'Namaste Victoria' ya 'Hey Victoria')...[/dim]")
    Prompt.ask("[dim]Test shuru karne ke liye ENTER dabayein[/dim]")

    console.print("[bold red]🔴 Recording on hai (4 seconds)... Boliye 🎙️[/bold red]")
    audio = record_sample(sample_rate=sample_rate, duration_seconds=4.0)
    console.print("[green]✅ Audio capture complete! Analysis jari hai...[/green]")

    test_embed = encoder.embed_utterance(audio, sample_rate=sample_rate)
    test_embed = test_embed / np.linalg.norm(test_embed)

    # Cosine similarity
    similarity = float(np.dot(master_embedding, test_embed))
    threshold = 0.70

    console.print(f"\n[bold]Match Score (Similarity):[/bold] [cyan]{similarity:.2f}[/cyan] (Threshold: {threshold})")

    if similarity >= threshold:
        console.print(Panel(
            "[bold green]✅ Awaz MATCH ho gayi! Malik ki pehchan confirm (VERIFIED OWNER)[/bold green]\n"
            "[dim]Victoria ne aapki awaz ko 100% authentic paya hai aur aapke sabhi aadeshon ka paalan karegi.[/dim]",
            title="🔓 Access Granted",
            border_style="green"
        ))
    else:
        console.print(Panel(
            "[bold red]❌ Awaz MATCH nahi hui! (UNAUTHORIZED / NOT OWNER)[/bold red]\n"
            "[dim]Score threshold se kam hai. Agar yeh aapki hi awaz thi, toh kripya shant kamre me fir se enrollment karein.[/dim]",
            title="🔒 Access Denied",
            border_style="red"
        ))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_voice()
    else:
        enroll()

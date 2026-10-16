"""
Victoria - Voice Print Onboarding & Biometric Personalization
Guides the owner through first-time voice print enrollment with natural speech,
capturing their unique 192-dimensional voice fingerprint so Victoria responds
EXCLUSIVELY to her owner and locks out all unauthorized voices.
"""

import time
import json
import numpy as np
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

from victoria.config import get_config
from victoria.voice.audio_stream import AudioStream

console = Console()

ENROLL_PROMPTS = [
    {
        "speech": "सैंपल एक: मेरे बाद बोलिए, नमस्ते विक्टोरिया, मैं हरिओम बोल रहा हूँ।",
        "text": "नमस्ते विक्टोरिया, मैं हरिओम बोल रहा हूँ।",
        "label": "Sample 1/3 (Owner Identification)",
    },
    {
        "speech": "सैंपल दो: मेरे बाद बोलिए, विक्टोरिया, सिस्टम का स्टेटस चेक करो और मुझे वेरिफाई करो।",
        "text": "विक्टोरिया, सिस्टम का स्टेटस चेक करो और मुझे वेरिफाई करो।",
        "label": "Sample 2/3 (Command Intonation)",
    },
    {
        "speech": "सैंपल तीन: मेरे बाद बोलिए, हे विक्टोरिया, आज से तुम सिर्फ़ मेरी पर्सनल एआई असिस्टेंट हो।",
        "text": "हे विक्टोरिया, आज से तुम सिर्फ़ मेरी पर्सनल एआई असिस्टेंट हो।",
        "label": "Sample 3/3 (Wake Word Calibration)",
    },
]


def get_profile_paths() -> tuple[Path, Path]:
    cfg = get_config()
    profile_dir = cfg.voice_profiles_dir
    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir / "owner.npy", profile_dir / "owner_meta.json"


def is_owner_enrolled() -> bool:
    """Check if owner has personalized their voice print."""
    npy_path, meta_path = get_profile_paths()
    if not npy_path.exists():
        return False
    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return bool(data.get("enrolled", False))
        except Exception:
            return False
    return False


def record_sample(sample_rate: int = 16000, duration_seconds: float = 4.0) -> np.ndarray:
    """Record a voice sample using system microphone."""
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


def run_first_time_voice_enrollment(tts=None, broadcaster=None, interactive_cli: bool = True) -> bool:
    """
    Spoken, conversational voice print enrollment.
    Victoria explains the setup aloud, captures 3 voice samples, and locks the biometric fingerprint.
    """
    console.print(Panel(
        "[bold cyan]🎙️ Victoria First-Time Voice Print Enrollment (बायोमेट्रिक वॉइस प्रिंट)[/bold cyan]\n"
        "[dim]विक्टोरिया केवल आपकी आवाज़ की पहचान (192-dim CAM++ Embedding) दर्ज करेगी,\n"
        "ताकि भविष्य में वह सिर्फ़ आपकी आवाज़ सुनकर काम करे और किसी अन्य आवाज़ को अस्वीकार कर दे।[/dim]",
        title="🔐 Owner Voice Lock Onboarding",
        border_style="cyan"
    ))

    # 1. Spoken Introduction
    intro_speech = (
        "नमस्ते! मैं विक्टोरिया हूँ। पहली बार शुरू करने से पहले, "
        "मुझे केवल आपकी आवाज़ की पहचान दर्ज करनी होगी ताकि मैं हमेशा सिर्फ़ आपकी आज्ञा मानूँ "
        "और कोई दूसरा मुझे आदेश न दे सके। कृपया मेरे बाद यह वाक्य साफ़ आवाज़ में बोलिए।"
    )
    if broadcaster:
        broadcaster.speaking(text=intro_speech)
    if tts:
        tts.speak(intro_speech)
        time.sleep(0.5)

    try:
        from victoria.voice.speaker_encoder import VoiceEncoder
        encoder = VoiceEncoder()
    except Exception as e:
        console.print(f"[red]❌ Voice Encoder loading error: {e}[/red]")
        return False

    cfg = get_config()
    sample_rate = cfg.audio_config.get("sample_rate", 16000)
    npy_path, meta_path = get_profile_paths()

    embeddings = []

    for idx, prompt_info in enumerate(ENROLL_PROMPTS, 1):
        speech_text = prompt_info["speech"]
        display_text = prompt_info["text"]
        label = prompt_info["label"]

        console.print(f"\n[bold yellow]👉 {label}:[/bold yellow] [bold green]\"{display_text}\"[/bold green]")

        if broadcaster:
            broadcaster.speaking(text=speech_text)
        if tts:
            tts.speak(speech_text)
            time.sleep(0.4)

        if broadcaster:
            broadcaster.listening()

        console.print("[bold red]🔴 रिकॉर्डिंग चालू है (4 सेकंड)... अभी बोलिए! 🎙️[/bold red]")
        audio = record_sample(sample_rate=sample_rate, duration_seconds=4.0)
        console.print("[green]✅ ऑडियो रिकॉर्ड हो गया![/green]")

        if len(audio) > 0 and np.max(np.abs(audio)) > 0.005:
            embed = encoder.embed_utterance(audio, sample_rate=sample_rate)
            norm = np.linalg.norm(embed)
            if norm > 0:
                embed = embed / norm
            embeddings.append(embed)
        else:
            console.print("[yellow]⚠️ आवाज़ धीमी थी, कृपया अगले सैंपल में थोड़ा स्पष्ट बोलें।[/yellow]")

    if len(embeddings) >= 2:
        master_embedding = np.mean(embeddings, axis=0)
        master_embedding = master_embedding / np.linalg.norm(master_embedding)
        np.save(str(npy_path), master_embedding)

        # Write metadata
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "enrolled": True,
                "timestamp": time.time(),
                "samples_count": len(embeddings),
                "model": "CAM++ ONNX (192-dim)",
            }, f, indent=2)

        celebration_speech = (
            "बधाई हो हरिओम जी! आपकी वॉयस प्रिंट सुरक्षित रूप से लॉक हो गई है। "
            "अब से विक्टोरिया सिर्फ़ और सिर्फ़ आपकी आवाज़ सुनकर आपका हर आदेश पूरा करेगी!"
        )
        if broadcaster:
            broadcaster.speaking(text=celebration_speech)
        if tts:
            tts.speak(celebration_speech)
            time.sleep(0.5)

        if broadcaster:
            broadcaster.standby()

        console.print(Panel(
            "[bold green]🎉 बधाई हरिओम जी! आपकी वॉइस प्रिंट 100% लॉक हो गई है।[/bold green]\n"
            f"[dim]• बायोमेट्रिक प्रोफ़ाइल:[/dim] [cyan]{npy_path}[/cyan]\n"
            "[dim]• सुरक्षा मोड:[/dim] [green]Strict Hariom Only (केवल हरिओम की आज्ञा मान्य)[/green]",
            title="🔒 Voice Lock Active",
            border_style="green"
        ))
        return True
    else:
        fail_speech = "माफ़ कीजिए, स्पष्ट आवाज़ रिकॉर्ड नहीं हो पाई। कृपया शांत कमरे में दोबारा प्रयास करें।"
        if tts:
            tts.speak(fail_speech)
        console.print("[red]❌ पर्याप्त वॉइस सैंपल कैप्चर नहीं हो सके। कृपया शांत कमरे में पुनः प्रयास करें।[/red]")
        return False

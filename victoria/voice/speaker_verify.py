"""
Victoria - Speaker Verification (Voice Fingerprint)
Ensures only the owner's voice can control Victoria.
Uses Alibaba 3D-Speaker CAM++ ONNX for neural voice embedding and cosine similarity comparison.

Security Levels:
  1. Voice match - cosine similarity of voice embedding
  2. Passphrase - required for dangerous/sensitive commands
"""

import os
import numpy as np
from typing import Optional, Tuple
from rich.console import Console

from victoria.config import get_config

console = Console()


class SpeakerVerifier:
    """
    Speaker verification using voice embeddings.

    During enrollment:
      - Records multiple voice samples from the owner
      - Creates an average voice embedding (256-dim vector)
      - Saves it to config/voice_profiles/owner.npy

    During runtime:
      - Creates embedding from incoming audio
      - Compares with owner's embedding using cosine similarity
      - Returns True if similarity > threshold
    """

    def __init__(self):
        cfg = get_config()
        sv_cfg = cfg.speaker_verify_config

        self.enabled: bool = sv_cfg.get("enabled", True)
        self.threshold: float = sv_cfg.get("threshold", 0.75)
        self.profile_path: str = str(
            cfg.voice_profiles_dir / "owner.npy"
        )
        self.passphrase_commands: list = sv_cfg.get("passphrase_required_for", [])
        self.sample_rate: int = cfg.audio_config.get("sample_rate", 16000)

        self._encoder = None
        self._owner_embedding: Optional[np.ndarray] = None

        if self.enabled:
            self._load_profile()

    def _get_encoder(self):
        """Lazy-load the neural voice encoder."""
        if self._encoder is None:
            try:
                from victoria.voice.speaker_encoder import VoiceEncoder
                console.print("[dim]🔄 Loading neural speaker verification model (CAM++ ONNX)...[/dim]")
                self._encoder = VoiceEncoder()
                console.print("[green]✅ Speaker verification model loaded[/green]")
            except Exception as e:
                console.print(f"[yellow]⚠️  Speaker verification notice: {e}[/yellow]")
                self.enabled = False
        return self._encoder

    def _load_profile(self):
        """Load the owner's voice profile if it exists."""
        if os.path.exists(self.profile_path):
            self._owner_embedding = np.load(self.profile_path)
            console.print("[green]🔐 Owner voice profile loaded[/green]")

    def is_enrolled(self) -> bool:
        """Check if an owner voice profile is enrolled."""
        return self.enabled and self._owner_embedding is not None

    @staticmethod
    def trim_silence(audio: np.ndarray, threshold: float = 0.001) -> np.ndarray:
        """Trim leading and trailing silence so voice embeddings focus on pure speech."""
        abs_audio = np.abs(audio)
        mask = abs_audio > threshold
        if not np.any(mask):
            return audio
        start = max(0, int(np.argmax(mask) - 16000 * 0.05))
        end = min(len(audio), int(len(audio) - np.argmax(mask[::-1]) + 16000 * 0.05))
        return audio[start:end]

    def verify(self, audio: np.ndarray, threshold: Optional[float] = None) -> Tuple[bool, float]:
        """
        Verify if the audio matches the owner's voice.

        Args:
            audio: numpy array of audio (float32, 16kHz, mono)
            threshold: optional custom threshold (default: self.threshold)

        Returns:
            Tuple of (is_owner, similarity_score)
        """
        if not self.enabled:
            return True, 1.0

        if self._owner_embedding is None:
            # No profile enrolled yet - accept all voices
            console.print("[dim]🔓 No voice profile - accepting all voices[/dim]")
            return True, 1.0

        encoder = self._get_encoder()
        if encoder is None:
            return True, 1.0

        try:
            trimmed = self.trim_silence(audio)
            if len(trimmed) < int(self.sample_rate * 0.2):  # Less than 0.2s
                console.print("[dim]Audio too short after trimming for verification[/dim]")
                return True, 0.5  # Accept but with low confidence

            # Create embedding for the incoming audio
            incoming_embedding = encoder.embed_utterance(trimmed, sample_rate=self.sample_rate)
            inc_norm = np.linalg.norm(incoming_embedding)
            if inc_norm > 0:
                incoming_embedding = incoming_embedding / inc_norm

            owner_norm = np.linalg.norm(self._owner_embedding)
            normed_owner = self._owner_embedding / owner_norm if owner_norm > 0 else self._owner_embedding

            # Calculate cosine similarity
            similarity = float(np.dot(normed_owner, incoming_embedding))

            target_thresh = threshold if threshold is not None else self.threshold
            is_owner = similarity >= target_thresh
            status = "✅ VERIFIED" if is_owner else "❌ REJECTED"
            console.print(f"[{'green' if is_owner else 'red'}]🔐 Speaker {status} (similarity: {similarity:.3f}, threshold: {target_thresh})[/{'green' if is_owner else 'red'}]")

            return is_owner, similarity

        except Exception as e:
            console.print(f"[red]❌ Speaker verification error: {e}[/red]")
            return False, 0.0

    def needs_passphrase(self, command_text: str) -> bool:
        """Check if a command requires passphrase verification."""
        command_lower = command_text.lower()
        return any(keyword in command_lower for keyword in self.passphrase_commands)

    def enroll(self, audio_samples: list[np.ndarray]) -> bool:
        """
        Enroll the owner's voice using multiple audio samples.

        Args:
            audio_samples: List of numpy audio arrays from the owner

        Returns:
            True if enrollment was successful
        """
        encoder = self._get_encoder()
        if encoder is None:
            console.print("[red]❌ Cannot enroll - VoiceEncoder not available[/red]")
            return False

        try:
            embeddings = []
            for i, audio in enumerate(audio_samples):
                if len(audio) < self.sample_rate * 0.5:
                    console.print(f"[yellow]⚠️  Sample {i+1} too short, skipping[/yellow]")
                    continue

                embedding = encoder.embed_utterance(audio, sample_rate=self.sample_rate)
                embeddings.append(embedding)
                console.print(f"[green]✅ Sample {i+1} processed[/green]")

            if len(embeddings) < 3:
                console.print("[red]❌ Need at least 3 valid samples for enrollment[/red]")
                return False

            # Average all embeddings for a robust profile
            self._owner_embedding = np.mean(embeddings, axis=0)
            self._owner_embedding = self._owner_embedding / np.linalg.norm(self._owner_embedding)

            # Save profile
            os.makedirs(os.path.dirname(self.profile_path), exist_ok=True)
            np.save(self.profile_path, self._owner_embedding)

            console.print(f"[green]🔐 Voice profile enrolled and saved! ({len(embeddings)} samples)[/green]")
            console.print(f"[dim]   Profile: {self.profile_path}[/dim]")
            return True

        except Exception as e:
            console.print(f"[red]❌ Enrollment error: {e}[/red]")
            return False

    def update_threshold(self, new_threshold: float):
        """Update the verification threshold."""
        if 0.0 <= new_threshold <= 1.0:
            self.threshold = new_threshold
            console.print(f"[green]🔐 Threshold updated to: {new_threshold}[/green]")
        else:
            console.print("[red]❌ Threshold must be between 0.0 and 1.0[/red]")

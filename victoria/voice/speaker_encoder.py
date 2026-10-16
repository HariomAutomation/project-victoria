"""
Victoria - Neural Voice Biometrics Encoder (3D-Speaker CAM++ ONNX)
Extracts 192-dimensional acoustic voice embeddings for speaker verification and enrollment.
Operates 100% offline via ONNX Runtime without PyTorch or C compilation.
"""

import numpy as np
import onnxruntime as ort
from pathlib import Path
from typing import Optional

from victoria.config import PROJECT_ROOT

MODEL_PATH = PROJECT_ROOT / "data" / "models" / "campplus_speaker.onnx"


def compute_fbank(
    audio: np.ndarray,
    sample_rate: int = 16000,
    n_mels: int = 80,
    n_fft: int = 512,
    hop_length: int = 160,
    win_length: int = 400,
) -> np.ndarray:
    """
    Compute 80-dimensional log-Mel filterbank energies with CMVN normalization.
    """
    audio = np.squeeze(audio).astype(np.float32)
    if len(audio) < win_length:
        audio = np.pad(audio, (0, win_length - len(audio)), mode="constant")

    # 1. Pre-emphasis
    audio = np.append(audio[0], audio[1:] - 0.97 * audio[:-1])

    # 2. Framing
    num_frames = 1 + int(np.floor((len(audio) - win_length) / hop_length))
    pad_audio = np.pad(audio, (0, int(hop_length * num_frames + win_length - len(audio))), mode="constant")

    indices = np.tile(np.arange(0, win_length), (num_frames, 1)) + np.tile(
        np.arange(0, num_frames * hop_length, hop_length), (win_length, 1)
    ).T
    frames = pad_audio[indices.astype(np.int32, copy=False)]

    # 3. Windowing (Hamming)
    window = np.hamming(win_length)
    frames = frames * window

    # 4. FFT & Power spectrum
    mag_frames = np.absolute(np.fft.rfft(frames, n_fft))
    pow_frames = (1.0 / n_fft) * (mag_frames ** 2)

    # 5. Mel filterbank
    low_freq_mel = 0
    high_freq_mel = 2595 * np.log10(1 + (sample_rate / 2) / 700)
    mel_points = np.linspace(low_freq_mel, high_freq_mel, n_mels + 2)
    hz_points = 700 * (10 ** (mel_points / 2595) - 1)
    bin_points = np.floor((n_fft + 1) * hz_points / sample_rate)

    fbank = np.zeros((n_mels, int(np.floor(n_fft / 2 + 1))))
    for m in range(1, n_mels + 1):
        f_m_minus = int(bin_points[m - 1])
        f_m = int(bin_points[m])
        f_m_plus = int(bin_points[m + 1])
        for k in range(f_m_minus, f_m):
            fbank[m - 1, k] = (k - bin_points[m - 1]) / max(1, (bin_points[m] - bin_points[m - 1]))
        for k in range(f_m, f_m_plus):
            fbank[m - 1, k] = (bin_points[m + 1] - k) / max(1, (bin_points[m + 1] - bin_points[m]))

    filter_banks = np.dot(pow_frames, fbank.T)
    filter_banks = np.where(filter_banks == 0, np.finfo(float).eps, filter_banks)
    filter_banks = 10 * np.log10(filter_banks)

    # 6. CMVN (Cepstral Mean Normalization)
    filter_banks -= (np.mean(filter_banks, axis=0) + 1e-8)
    return filter_banks.astype(np.float32)


class VoiceEncoder:
    """
    Deep Speaker Encoder producing 192-dim normalized speaker vectors.
    """

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or MODEL_PATH
        if not self.model_path.exists():
            raise FileNotFoundError(f"Speaker model not found at {self.model_path}")

        # Optimize session for fast CPU inference
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 2
        self.session = ort.InferenceSession(str(self.model_path), sess_options=opts)

    def embed_utterance(self, audio: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
        """
        Compute normalized 192-dim speaker embedding vector for an audio sample.
        """
        feats = compute_fbank(audio, sample_rate=sample_rate)
        # Input shape: [batch, time, 80]
        inputs = {"feats": np.expand_dims(feats, axis=0)}
        embs = self.session.run(["embs"], inputs)[0]
        vec = embs[0].astype(np.float32)

        # L2 Normalization
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

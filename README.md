# 👑 Project Victoria (विक्टोरिया)

> **Personal AI Assistant for Linux | Full OS Control | REA Engine | 3D Holographic HUD | Hindi Core**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Three.js](https://img.shields.io/badge/Three.js-r128-black.svg?logo=three.js)](https://threejs.org)

Victoria is an advanced, autonomous personal AI assistant and digital twin built specifically for Linux power users. She features deep operating system integration, an always-on conversational voice pipeline with biometric speaker verification, a 3D holographic web HUD, and the **REA (Reverse Engineer Anything)** engine.

---

## ✨ Key Features

- 🧠 **Pluggable AI Brain Controller**:
  - Native integration with **Google Gemini (2.0 Flash / 1.5 Pro)**.
  - Multi-provider support: **OpenRouter**, **Groq (LPU)**, **OpenAI (GPT-4o)**, **Sarvam AI**, and offline local **Ollama** models.
  - Built-in multi-model fallback and runtime provider switching.

- 🎙️ **Conversational Two-Way Voice Loop**:
  - **Wake Word Detection**: Responds to *"Hey Victoria"* or *"विक्टोरिया"*.
  - **Biometric Speaker Verification**: CAM++ ONNX neural voice verification ensures only the owner can control the assistant.
  - **Edge-TTS & Whisper STT**: Ultra-low latency voice synthesis in natural Hindi / Hinglish.

- 🌐 **3D Holographic Cyberpunk HUD Deck**:
  - Runs on `http://localhost:7860`.
  - Interactive Three.js particle neural core and real-time audio oscilloscope.
  - Live system telemetry gauges (CPU, RAM, Disk, Battery).
  - One-click AI brain connection and model selector modal.

- ⚡ **REA (Reverse Engineer Anything) Engine**:
  - Deep automated analysis and teardown of websites, web applications, local APIs, Linux services, databases, and network devices.
  - Generates comprehensive architectural reports and security teardowns in Markdown & JSON.

- 🛠️ **Deep Linux OS Control**:
  - Over 45+ native system tools: audio volume control, display brightness, process monitoring, network tools, screenshot capture, file management, and terminal command execution.

---

## 🚀 Quick Start

### 1. Prerequisites
- Linux OS (Ubuntu 22.04+ / Debian / Fedora / Arch)
- Python 3.10+
- Audio input & output devices (Microphone & Speakers)

### 2. Installation

Clone the repository and set up the environment:
```bash
git clone https://github.com/HariomAutomation/project-victoria.git
cd project-victoria

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

Copy the example environment configuration:
```bash
cp .env.example .env
```
Edit `.env` or easily configure your API keys directly through the **3D HUD Web Deck**.

### 4. Running Victoria

#### Option A: 3D Holographic HUD Web Deck
```bash
python3 -m victoria --mode hud
# Open http://localhost:7860 in your browser
```

#### Option B: Always-On Voice Mode
```bash
python3 -m victoria --mode voice
```

#### Option C: Interactive CLI Mode
```bash
python3 -m victoria
```

#### Option D: Reverse Engineer a Target (REA Mode)
```bash
python3 -m victoria --rea https://example.com
```

---

## 📁 Project Architecture

```
PROJECT VICTORIA/
├── config/                  # Configuration files & voice profiles
│   └── victoria.yaml        # Main Victoria configuration
├── data/                    # Dynamic data, caches & models
│   ├── assets/              # UI icons and graphics
│   ├── models/              # Pretrained ONNX models (CAM++)
│   └── memory/              # SQLite conversation & owner memory vault
├── scripts/                 # System launchers and installation scripts
├── victoria/                # Core Python package
│   ├── brain/               # Model Router, Providers & Memory Vault
│   ├── hud/                 # FastAPI server & 3D Web Deck (HTML/JS/CSS)
│   ├── rea/                 # Reverse Engineer Anything teardown engine
│   ├── tools/               # 45+ Linux system automation tools
│   └── voice/               # Wake word, STT, TTS & Speaker verification
├── .env.example             # Environment template
├── pyproject.toml           # Project package configuration
└── requirements.txt         # Python dependencies
```

---

## 🛡️ License

Distributed under the MIT License. See `LICENSE` for more information.

---

<p align="center">
  <b>Project Victoria</b> &bull; Built with ❤️ for Autonomous Linux Computing
</p>

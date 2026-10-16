"""
Victoria - Master Entry Point
Starts the personal AI assistant:
- Interactive Text Mode (Chat & Linux control via terminal)
- Voice Mode (Wake word 'Hey Victoria', VAD, Speaker Verification, STT, TTS)
- REA Mode (Reverse Engineer Anything CLI for websites, apps, databases, devices)
- System Diagnostics & Tools Inspector
"""

import sys
import os
import time
import argparse
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from victoria.config import get_config
from victoria.brain.tools import build_tool_registry
from victoria.brain.router import BrainRouter
from victoria.brain.memory import ConversationMemory
from victoria.rea.teardown import ReverseEngineerEngine

console = Console()


def print_banner():
    banner = """[bold cyan]
██╗   ██╗██╗ ██████╗████████╗ ██████╗ ██████╗ ██╗ █████╗ 
██║   ██║██║██╔════╝╚══██╔══╝██╔═══██╗██╔══██╗██║██╔══██╗
██║   ██║██║██║        ██║   ██║   ██║██████╔╝██║███████║
╚██╗ ██╔╝██║██║        ██║   ██║   ██║██╔══██╗██║██╔══██║
 ╚████╔╝ ██║╚██████╗   ██║   ╚██████╔╝██║  ██║██║██║  ██║
  ╚═══╝  ╚═╝ ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚═╝╚═╝  ╚═╝
[/bold cyan]
[dim]Personal AI Assistant for Linux | Full OS Control | REA Engine | Pluggable AI[/dim]
"""
    console.print(banner)


def run_text_mode(router: BrainRouter, memory: ConversationMemory):
    """Interactive text REPL mode."""
    print_banner()
    cfg = get_config()
    active_model = cfg.get_active_model_name()
    tools_count = len(router.tool_registry.list_tools())

    console.print(
        Panel(
            f"[bold green]Victoria is online and ready.[/bold green]\n"
            f"[dim]• Active Brain:[/dim] [cyan]{active_model}[/cyan]\n"
            f"[dim]• System & REA Tools Loaded:[/dim] [yellow]{tools_count} tools[/yellow]\n"
            f"[dim]• Type [bold]exit[/bold] or [bold]quit[/bold] to leave.[/dim]\n"
            f"[dim]• Type [bold]rea <target>[/bold] to reverse engineer any website, app, db, or device.[/dim]",
            title="✨ Victoria Console",
            border_style="cyan",
        )
    )

    session_id = f"cli_{os.getpid()}"

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]").strip()
            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit", "q"]:
                console.print("[dim]Victoria signing off. Goodbye![/dim]")
                break

            # Handle quick REA shortcut
            if user_input.lower().startswith("rea "):
                target = user_input[4:].strip()
                console.print(f"[bold yellow]⚡ REA shortcut triggered for '{target}'...[/bold yellow]")
                engine = ReverseEngineerEngine()
                report = engine.teardown(target)
                console.print(f"[bold green]✅ Report saved at:[/bold green] {report['markdown_report_path']}")
                continue

            # Pass into Victoria's Brain Router
            with console.status("[bold green]Victoria is thinking & acting...[/bold green]"):
                response = router.think(user_input)

            console.print(f"\n[bold magenta]Victoria[/bold magenta]: {response}")

            # Save in SQLite Memory
            if memory.enabled:
                memory.save_message(
                    session_id=session_id,
                    role="user",
                    content=user_input,
                )
                memory.save_message(
                    session_id=session_id,
                    role="assistant",
                    content=response,
                    model_used=router._active_model,
                )

        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted. Type 'exit' to quit.[/dim]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def run_voice_mode(router: BrainRouter, memory: ConversationMemory):
    """Voice interaction loop."""
    print_banner()
    console.print("[yellow]🎙️ Starting Voice Pipeline (Wake Word + VAD + STT + TTS)...[/yellow]")

    try:
        from victoria.voice.wake_word import WakeWordDetector
        from victoria.voice.listener import AudioListener
        from victoria.voice.stt import SpeechToText
        from victoria.voice.tts import TextToSpeech
        from victoria.voice.speaker_verify import SpeakerVerifier
        from victoria.voice.voice_events import broadcaster

        cfg = get_config()
        wake_detector = WakeWordDetector()
        listener = AudioListener()
        stt = SpeechToText()
        tts = TextToSpeech()
        verifier = SpeakerVerifier()

        # Auto-launch JARVIS Floating Holographic Arc Reactor widget if display is available
        if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
            try:
                import subprocess
                check = subprocess.run(["pgrep", "-f", "victoria.hud.floating_widget"], capture_output=True)
                if check.returncode != 0:
                    console.print("[bold cyan]🚀 Launching JARVIS Floating Hologram Widget on screen...[/bold cyan]")
                    subprocess.Popen([sys.executable, "-m", "victoria.hud.floating_widget"])
            except Exception as e:
                console.print(f"[dim]Widget launch notice: {e}[/dim]")

        from victoria.voice.voice_model_manager import (
            detect_model_choice, is_confirm_current, format_model_greeting,
            format_model_switched, format_model_retained, get_friendly_model_name,
            extract_task_after_model, detect_voice_choice
        )

        from victoria.voice.voice_onboarding import is_owner_enrolled, run_first_time_voice_enrollment
        if not is_owner_enrolled():
            console.print("[bold yellow]🎙️ First-time Voice Print setup required: Victoria needs to learn your authentic voice print.[/bold yellow]")
            success = run_first_time_voice_enrollment(tts=tts, broadcaster=broadcaster)
            if success:
                verifier._load_profile()

        wake_phrase = cfg.wake_phrase
        console.print(f"[bold green]🎤 Listening for wake word: '{wake_phrase}' or 'विक्टोरिया'...[/bold green]")
        session_id = f"voice_{os.getpid()}"
        import threading
        stop_event = threading.Event()

        # Emit initial standby event
        broadcaster.standby()

        while not stop_event.is_set():
            # 1. Wait for wake word to initiate conversation
            console.print(f"[dim]Waiting for '{wake_phrase}' / 'विक्टोरिया'...[/dim]")
            wake_audio = wake_detector.wait_for_wake_word(stop_event)
            if wake_audio is None:
                continue

            console.print("[bold cyan]⚡ Wake word detected! Entering active two-way conversation mode...[/bold cyan]")
            broadcaster.wake()

            # Speaker verification on wake word: Ensure it is Hariom waking Victoria (threshold 0.45)
            if verifier.is_enrolled():
                is_owner, similarity = verifier.verify(wake_audio, threshold=0.45)
                console.print(f"[dim]Wake speaker similarity: {similarity:.2f}[/dim]")
                if not is_owner:
                    console.print(f"[bold yellow]🚫 Background wake ignored (similarity: {similarity:.2f} < 0.45). Standing by for Hariom...[/bold yellow]")
                    broadcaster.standby()
                    continue

            # Greet owner and report current active model, inquiring which AI model they want to connect with
            welcome_msg = format_model_greeting(router._active_model)
            broadcaster.speaking(text=welcome_msg)
            interrupted_audio = tts.speak(
                welcome_msg,
                interruptible=True,
                listener=listener,
                broadcaster=broadcaster,
            )
            time.sleep(0.1)

            # 2. Continuous Two-Way Conversation Session
            in_dialogue = True
            silence_count = 0
            MAX_SILENCE_BEFORE_SLEEP = 6  # Allows ~15-20 seconds of thinking pauses

            while in_dialogue and not stop_event.is_set():
                if interrupted_audio is not None:
                    console.print("[bold yellow]⚡ Handling Hariom's interruption immediately...[/bold yellow]")
                    audio_data = interrupted_audio
                    interrupted_audio = None
                else:
                    console.print("[bold green]👂 Victoria is listening (Two-way dialogue active)...[/bold green]")
                    broadcaster.listening()
                    audio_data = listener.record_until_silence()

                if audio_data is None or len(audio_data) < int(listener.sample_rate * 0.35):
                    silence_count += 1
                    if silence_count >= MAX_SILENCE_BEFORE_SLEEP:
                        console.print("[dim]Dialogue paused. Victoria returning to standby...[/dim]")
                        broadcaster.standby()
                        in_dialogue = False
                    continue

                # Speech detected, reset silence counter
                silence_count = 0

                # 3. Speaker verification check: Listen exclusively to Hariom, silently ignore background chatter & self-echo
                if verifier.is_enrolled():
                    # Reject Victoria's own speaker output immediately!
                    if verifier.is_victoria_echo(audio_data):
                        console.print("[dim]🔇 Victoria speaker echo filtered out. Staying in dialogue...[/dim]")
                        continue

                    dur_sec = len(audio_data) / listener.sample_rate
                    # Adaptive threshold: Short utterances (< 2.2s) or barge-in interruptions get 0.40 to prevent false rejects; longer get 0.44
                    req_thresh = 0.40 if (interrupted_audio is not None or dur_sec < 2.2) else 0.44
                    is_owner, similarity = verifier.verify(audio_data, threshold=req_thresh)
                    console.print(f"[dim]Speaker similarity: {similarity:.2f} (threshold: {req_thresh})[/dim]")
                    if not is_owner:
                        console.print(f"[bold yellow]🚫 Background voice ignored (similarity: {similarity:.2f} < {req_thresh}). Listening only for Hariom...[/bold yellow]")
                        continue

                # 4. Speech-to-Text
                text, detected_lang, confidence = stt.transcribe(audio_data)
                console.print(f"[bold cyan]You ({detected_lang}):[/bold cyan] {text}")

                if not text.strip() or len(text.strip()) < 2:
                    continue

                # Filter out isolated passive acknowledgments ("जी हां", "हाँ", "अच्छा", "ok", "hmm", "हम्म", "ठीक")
                # so Victoria doesn't keep looping with "जी हरिओम, मैं तैयार हूँ। बताइए क्या करना है?"
                passive_words = ["जी हां", "जी हाँ", "हाँ", "अच्छा", "ok", "hmm", "हम्म", "ठीक", "जी", "हां", "ना"]
                cleaned_clean = "".join(c for c in text.lower().strip() if c.isalnum() or c.isspace()).strip()
                if cleaned_clean in passive_words:
                    console.print(f"[dim]Passive acknowledgment '{text}' acknowledged silently.[/dim]")
                    broadcaster.listening()
                    continue

                # Check for pause / wait phrases (e.g. "रुको", "रुक जाओ", "सुनो", "अरे सुनो", "wait", "hold on", "चुप")
                pause_phrases = ["रुको", "रुक जाओ", "ठहरो", "सुनो", "अरे सुनो", "wait", "hold on", "pause", "ek minute", "एक मिनट", "रुको रुको", "चुप", "चुप रहो", "stop", "shant", "शांत"]
                cleaned_text = text.strip().lower()
                if (any(cleaned_text == p or cleaned_text.startswith(p + " ") for p in pause_phrases)) and len(cleaned_text.split()) <= 3:
                    ack_msg = "जी हरिओम, मैं रुक गई।"
                    broadcaster.speaking(text=ack_msg)
                    interrupted_audio = tts.speak(
                        ack_msg,
                        interruptible=True,
                        listener=listener,
                        broadcaster=broadcaster,
                    )
                    broadcaster.listening()
                    time.sleep(0.3)
                    continue

                # Check for explicit goodbye / dismissal / mic-off phrases
                dismiss_phrases = [
                    "बाय", "अलविदा", "बस विक्टोरिया", "बाद में बात करते हैं", "शांत रहो", "शांत हो जाओ", "शांत",
                    "चुप रहो", "माइक बंद", "माइक ऑफ", "माइक बंद करो", "माइक ऑफ करो", "मत सुनो",
                    "मेरी बात मत सुनो", "साइलेंट मोड", "bye", "goodbye", "go to sleep", "standby",
                    "mic off", "turn off mic", "silent mode", "sleep", "stop listening", "chup raho",
                    "shant raho", "shant ho jao", "shaant", "shant", "bas victoria", "kuch mat bolo",
                    "baat mat suno", "mat suno", "band karo", "band kar do", "so jao", "sojao", "stop",
                ]
                if any(p in text.lower() for p in dismiss_phrases):
                    farewell = "जी हरिओम! माइक बंद कर रही हूँ। जब भी ज़रूरत हो, बस 'हे विक्टोरिया' बोल दीजिएगा।"
                    broadcaster.speaking(text=farewell)
                    tts.speak(farewell, interruptible=False)
                    broadcaster.standby()
                    in_dialogue = False
                    break

                # Voice Print Re-enrollment command
                if any(k in text.lower() for k in ["voice print", "वॉइस प्रिंट", "आवाज़ रिकॉर्ड", "voice profile", "re-enroll"]):
                    tts.speak("जी हरिओम, चलिए आपकी वॉयस प्रिंट दोबारा रिकॉर्ड करते हैं।")
                    run_first_time_voice_enrollment(tts=tts, broadcaster=broadcaster)
                    verifier._load_profile()
                    continue

                # B. Check if user requested Victoria to research & acquire a new skill/knowledge
                from victoria.brain.skill_rnd import detect_skill_request, get_skill_rnd_engine
                skill_topic = detect_skill_request(text)
                if skill_topic:
                    progress_msg = f"जी हरिओम! मैं अभी इंटरनेट पर '{skill_topic}' को लेकर गहन R&D कर रही हूँ और यह नई स्किल अपने अंदर जोड़ रही हूँ। कृपया कुछ क्षण प्रतीक्षा करें..."
                    broadcaster.thinking(text=f"R&D: {skill_topic}...")
                    broadcaster.speaking(text=progress_msg)
                    tts.speak(progress_msg, interruptible=False)

                    try:
                        rnd_engine = get_skill_rnd_engine()
                        res = rnd_engine.acquire_skill(topic=skill_topic)
                        acquired_speech = res.get(
                            "speech",
                            f"जी हरिओम! मैंने इंटरनेट से R&D करके '{skill_topic}' की स्किल और नॉलेज अपने अंदर सफलतापूर्वक शामिल कर ली है। अब यह स्किल मेरे पास उपलब्ध है—इस स्किल का उपयोग करके आप मुझसे क्या काम करवाना चाहते हैं?",
                        )
                    except Exception as rnd_err:
                        console.print(f"[red]Skill R&D error: {rnd_err}[/red]")
                        acquired_speech = f"माफ़ कीजिए हरिओम, '{skill_topic}' पर R&D करते समय कुछ समस्या आई। क्या मैं दोबारा प्रयास करूँ?"

                    broadcaster.speaking(text=acquired_speech)
                    interrupted_audio = tts.speak(
                        acquired_speech,
                        interruptible=False,
                        listener=listener,
                        broadcaster=broadcaster,
                    )
                    broadcaster.listening()
                    time.sleep(0.3)
                    continue

                # A. Check if user requested to switch or connect to a specific AI model
                model_detected = detect_model_choice(text)
                if model_detected:
                    model_key, display_name = model_detected
                    router.switch_model(model_key)
                    cfg.set_active_model(model_key, persist=True)
                    broadcaster.emit("model_switched", state="connected", model=display_name)

                    # Check if user also gave a task in the same sentence
                    followup_task = extract_task_after_model(text)
                    if followup_task:
                        confirm_msg = f"जी हरिओम! मैंने {display_name} से वॉइस कनेक्शन जोड़ दिया है। अब आपका काम कर रही हूँ।"
                        broadcaster.speaking(text=confirm_msg)
                        interrupted_audio = tts.speak(
                            confirm_msg,
                            interruptible=False,
                            listener=listener,
                            broadcaster=broadcaster,
                        )
                        task_to_run = followup_task
                    else:
                        confirm_msg = format_model_switched(display_name)
                        broadcaster.speaking(text=confirm_msg)
                        interrupted_audio = tts.speak(
                            confirm_msg,
                            interruptible=False,
                            listener=listener,
                            broadcaster=broadcaster,
                        )
                        broadcaster.listening()
                        time.sleep(0.3)
                        continue
                elif is_confirm_current(text):
                    # B. Check if user confirmed to keep the current active model
                    cur_name = get_friendly_model_name(router._active_model)
                    confirm_msg = format_model_retained(cur_name)
                    broadcaster.speaking(text=confirm_msg)
                    interrupted_audio = tts.speak(
                        confirm_msg,
                        interruptible=False,
                        listener=listener,
                        broadcaster=broadcaster,
                    )
                    broadcaster.listening()
                    time.sleep(0.3)
                    continue
                elif detect_voice_choice(text):
                    # C. Check if user requested to switch Victoria's AI speaking voice
                    v_key, v_name = detect_voice_choice(text)
                    if v_key == "cycle":
                        new_key, new_name = tts.cycle_next_voice(persist=True)
                    else:
                        new_key, new_name = tts.set_voice(v_key, persist=True)
                    voice_msg = f"जी हरिओम! मैंने अपनी आवाज़ बदलकर {new_name} कर ली है। क्या अब यह आवाज़ आपको पसंद आ रही है?"
                    broadcaster.speaking(text=voice_msg)
                    interrupted_audio = tts.speak(
                        voice_msg,
                        interruptible=False,
                        listener=listener,
                        broadcaster=broadcaster,
                    )
                    broadcaster.listening()
                    time.sleep(0.3)
                    continue
                else:
                    task_to_run = text

                # 5. Think & Formulate Conversational Response using the connected model
                broadcaster.thinking(text=task_to_run)
                try:
                    response = router.think(task_to_run)
                    if not response or not response.strip():
                        response = "जी हरिओम, मैंने आपकी बात नोट कर ली है।"
                except Exception as brain_err:
                    console.print(f"[red]Brain error: {brain_err}[/red]")
                    response = "माफ़ कीजिए हरिओम, मॉडल से जवाब नहीं मिल पाया। क्या मैं दूसरे मॉडल से कोशिश करूँ?"

                cur_model_label = get_friendly_model_name(router._active_model)
                console.print(f"[bold magenta]Victoria ({cur_model_label}):[/bold magenta] {response}")

                # 6. Speak response in Hindi back to owner with Barge-In monitoring
                try:
                    broadcaster.speaking(text=response)
                    interrupted_audio = tts.speak(
                        response,
                        interruptible=True,
                        listener=listener,
                        broadcaster=broadcaster,
                    )
                    broadcaster.listening()
                    time.sleep(0.1)
                except Exception as tts_err:
                    console.print(f"[red]TTS error: {tts_err}[/red]")
                    broadcaster.listening()

                # 7. Record in persistent memory
                if memory.enabled:
                    try:
                        memory.save_message(
                            session_id=session_id,
                            role="user",
                            content=text,
                            language=detected_lang,
                        )
                        memory.save_message(
                            session_id=session_id,
                            role="assistant",
                            content=response,
                            model_used=router._active_model,
                        )
                    except Exception:
                        pass

    except KeyboardInterrupt:
        console.print("\n[yellow]Voice mode stopped.[/yellow]")
    except Exception as e:
        console.print(f"[red]Voice mode error: {e}[/red]")
        time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description="Victoria - Personal AI Assistant for Linux with REA Power")
    parser.add_argument("--mode", choices=["text", "voice", "hud", "widget", "floating"], default="text", help="Operating mode: text, voice, hud, or widget")
    parser.add_argument("--widget", action="store_true", help="Launch JARVIS Floating Arc Reactor On-Screen Widget")
    parser.add_argument("--hud", action="store_true", help="Launch Victoria Holographic 3D HUD Web Server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="HUD server host (default 127.0.0.1; use 0.0.0.0 to expose on the LAN)")
    parser.add_argument("--port", type=int, default=7860, help="HUD server port (default 7860)")
    parser.add_argument("--rea", type=str, default=None, help="Reverse engineer a target directly (URL, binary, db, device)")
    parser.add_argument("--rea-type", type=str, default="auto", choices=["auto", "website", "app", "database", "device"], help="Target type for REA")
    parser.add_argument("--status", action="store_true", help="Print Victoria configuration and loaded tools")
    parser.add_argument("--enroll", action="store_true", help="Enroll owner voice profile for biometric speaker verification")
    parser.add_argument("--test-voice", action="store_true", help="Test voice match against enrolled owner profile")

    args = parser.parse_args()

    # Handle voice enrollment
    if args.enroll:
        print_banner()
        from scripts.enroll_voice import enroll
        enroll()
        sys.exit(0)

    # Handle voice match testing
    if args.test_voice:
        print_banner()
        from scripts.enroll_voice import test_voice
        test_voice()
        sys.exit(0)

    # Handle direct Floating JARVIS Arc Reactor widget execution
    if args.widget or args.mode in ("widget", "floating"):
        from victoria.hud.floating_widget import run_floating_widget
        run_floating_widget()
        sys.exit(0)

    # Handle direct HUD Web Dashboard execution
    if args.hud or args.mode == "hud":
        print_banner()
        console.print(Panel(
            f"[bold green]Starting Victoria 3D Holographic HUD on:[/bold green] [bold cyan]http://{args.host}:{args.port}[/bold cyan]\n"
            f"[dim]• 3D Neural Core Holograph (Three.js)[/dim]\n"
            f"[dim]• Audio Waveform Oscilloscope & Hindi Voice (Edge-TTS)[/dim]\n"
            f"[dim]• Hardware Gauges (CPU, RAM, Disk, Battery)[/dim]\n"
            f"[dim]• REA (Reverse Engineer Anything) Control Deck[/dim]",
            title="🌐 Victoria Holographic HUD",
            border_style="magenta",
        ))
        from victoria.hud.server import start_hud_server
        start_hud_server(host=args.host, port=args.port)
        sys.exit(0)

    # Handle direct REA execution
    if args.rea:
        print_banner()
        engine = ReverseEngineerEngine()
        report = engine.teardown(args.rea, target_type=args.rea_type)
        console.print(Panel(
            f"[bold green]Teardown Complete for:[/bold green] {args.rea}\n"
            f"[cyan]Type:[/cyan] {report['target_type']}\n"
            f"[cyan]Duration:[/cyan] {report['duration_seconds']}s\n"
            f"[yellow]Markdown Report:[/yellow] {report['markdown_report_path']}\n"
            f"[yellow]JSON Report:[/yellow] {report['json_report_path']}",
            title="🔍 REA Report Generated",
            border_style="green",
        ))
        sys.exit(0)

    # Initialize Victoria Subsystems
    tool_registry = build_tool_registry()
    router = BrainRouter(tool_registry=tool_registry)
    memory = ConversationMemory()

    if args.status:
        print_banner()
        cfg = get_config()
        console.print(Panel(
            f"[bold green]Assistant:[/bold green] {cfg.assistant_name}\n"
            f"[bold cyan]Active Brain:[/bold cyan] {cfg.get_active_model_name()}\n"
            f"[bold yellow]Registered Tools ({len(tool_registry.list_tools())}):[/bold yellow]\n"
            + "\n".join([f"  • {name}" for name in tool_registry.list_tools()]),
            title="ℹ️ Victoria System Status",
            border_style="cyan",
        ))
        sys.exit(0)

    # Run chosen mode
    if args.mode == "voice":
        run_voice_mode(router, memory)
    else:
        run_text_mode(router, memory)


if __name__ == "__main__":
    main()

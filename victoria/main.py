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

        cfg = get_config()
        wake_detector = WakeWordDetector()
        listener = AudioListener()
        stt = SpeechToText()
        tts = TextToSpeech()
        verifier = SpeakerVerifier()

        wake_phrase = cfg.wake_phrase
        console.print(f"[bold green]🎤 Listening for wake word: '{wake_phrase}' or 'विक्टोरिया'...[/bold green]")
        session_id = f"voice_{os.getpid()}"
        import threading
        stop_event = threading.Event()

        while not stop_event.is_set():
            # 1. Wait for wake word to initiate conversation
            console.print(f"[dim]Waiting for '{wake_phrase}' / 'विक्टोरिया'...[/dim]")
            wake_audio = wake_detector.wait_for_wake_word(stop_event)
            if wake_audio is None:
                continue

            console.print("[bold cyan]⚡ Wake word detected! Entering active two-way conversation mode...[/bold cyan]")

            # Speaker verification on wake word itself if enrolled
            if verifier.is_enrolled():
                is_owner, similarity = verifier.verify(wake_audio)
                if not is_owner:
                    console.print(f"[bold red]🚫 Unauthorized voice detected ({similarity:.2f} < {verifier.threshold:.2f})! Victoria is ignoring this request.[/bold red]")
                    continue

            tts.speak("Ji Malik, kahiye, main sun rahi hoon.")
            time.sleep(0.5)

            # 2. Continuous Two-Way Conversation Session
            # Stays in active dialogue loop so the owner does NOT need to repeat the wake word after each sentence!
            in_dialogue = True
            silence_count = 0
            MAX_SILENCE_BEFORE_SLEEP = 2  # Allows ~6-8 seconds of thinking pauses

            while in_dialogue and not stop_event.is_set():
                console.print("[bold green]👂 Victoria is listening (Two-way dialogue active)...[/bold green]")
                audio_data = listener.record_until_silence()

                if audio_data is None or len(audio_data) < int(listener.sample_rate * 0.35):
                    silence_count += 1
                    if silence_count >= MAX_SILENCE_BEFORE_SLEEP:
                        console.print("[dim]Dialogue paused. Victoria returning to standby...[/dim]")
                        tts.speak("Theek hai Malik, main background me hoon. Jab bhi zaroorat ho, bas awaz dijiyega.")
                        time.sleep(0.5)
                        in_dialogue = False
                    continue

                # Speech detected, reset silence counter
                silence_count = 0

                # 3. Speaker verification (security check)
                if verifier.is_enrolled():
                    is_owner, similarity = verifier.verify(audio_data)
                    console.print(f"[dim]Speaker similarity: {similarity:.2f}[/dim]")
                    if not is_owner:
                        console.print(f"[bold red]🚫 Voice did not match owner ({similarity:.2f} < {verifier.threshold:.2f}). Exiting dialogue.[/bold red]")
                        tts.speak("Maaf kijiye, awaz match nahi hui.")
                        time.sleep(0.6)
                        in_dialogue = False
                        break

                # 4. Speech-to-Text
                text, detected_lang, confidence = stt.transcribe(audio_data)
                console.print(f"[bold cyan]You ({detected_lang}):[/bold cyan] {text}")

                if not text.strip() or len(text.strip()) < 2:
                    continue

                # Check for explicit goodbye / dismissal phrases
                dismiss_phrases = ["बाय", "अलविदा", "बस विक्टोरिया", "बाद में बात करते हैं", "शांत रहो", "bye", "goodbye", "go to sleep", "standby"]
                if any(p in text.lower() for p in dismiss_phrases):
                    tts.speak("जी मालिक, अलविदा! जब भी याद करेंगे मैं तुरंत हाजिर हो जाऊँगी।")
                    in_dialogue = False
                    break

                # 5. Think & Formulate Conversational Two-Way Response
                try:
                    response = router.think(text)
                except Exception as brain_err:
                    console.print(f"[red]Brain error: {brain_err}[/red]")
                    response = f"Malik, error aaya: {str(brain_err)[:80]}."

                console.print(f"[bold magenta]Victoria:[/bold magenta] {response}")

                # 6. Speak response in Hindi back to owner
                try:
                    tts.speak(response)
                    time.sleep(0.5)
                except Exception as tts_err:
                    console.print(f"[red]TTS error: {tts_err}[/red]")

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
    parser.add_argument("--mode", choices=["text", "voice", "hud"], default="text", help="Operating mode: text, voice, or hud")
    parser.add_argument("--hud", action="store_true", help="Launch Victoria Holographic 3D HUD Web Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="HUD server host (default 0.0.0.0)")
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

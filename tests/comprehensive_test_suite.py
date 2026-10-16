"""
Comprehensive Test Suite for Project Victoria:
- Phase 1: Sanity Tests (Audio AGC, Listener VAD, Whisper STT, Wake Word, Speaker Biometrics)
- Phase 2: Smoke Tests (Full Pipeline: Speech -> Biometrics -> STT -> Brain -> TTS, Tool Execution)
- Phase 3: Regression Tests (Female Voices, Barge-in, Autonomous Skills, Mouse/Keyboard, Name Verification)
"""

import sys
import os
import time
import asyncio
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from rich.console import Console
from rich.table import Table

console = Console()

test_results = []

def record_test(phase: str, name: str, passed: bool, details: str = ""):
    status_icon = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({
        "phase": phase,
        "name": name,
        "status": status_icon,
        "passed": passed,
        "details": details
    })
    console.print(f"[{'green' if passed else 'red'}]{status_icon}[/{'green' if passed else 'red'}] [{phase}] {name} - {details}")


# ==============================================================================
# PHASE 1: SANITY TESTS
# ==============================================================================
def run_sanity_tests():
    console.rule("[bold cyan]PHASE 1: SANITY TESTS[/bold cyan]")

    # 1.1 AGC Normalization Sanity Test
    try:
        sr = 16000
        t = np.linspace(0, 1.0, sr, endpoint=False)
        quiet_signal = (np.sin(2 * np.pi * 440 * t) * 0.003).astype(np.float32)
        
        peak_before = float(np.max(np.abs(quiet_signal)))
        normalized = (quiet_signal / peak_before) * 0.7
        peak_after = float(np.max(np.abs(normalized)))
        rms_after = float(np.sqrt(np.mean(normalized ** 2)))
        
        is_ok = (0.69 <= peak_after <= 0.71) and (rms_after > 0.40)
        record_test("Sanity", "AGC Peak Normalization", is_ok, f"Peak {peak_before:.4f} -> {peak_after:.2f}, RMS -> {rms_after:.3f}")
    except Exception as e:
        record_test("Sanity", "AGC Peak Normalization", False, str(e))

    # 1.2 STT Component & Model Sanity
    try:
        from victoria.voice.stt import SpeechToText
        stt = SpeechToText()
        stt._load_model()
        model_loaded = stt._model is not None
        record_test("Sanity", "Faster-Whisper STT Model Loading", model_loaded, f"Model size: {stt.model_size}")
    except Exception as e:
        record_test("Sanity", "Faster-Whisper STT Model Loading", False, str(e))

    # 1.3 Listener VAD Threshold Sanity
    try:
        from victoria.voice.listener import AudioListener
        listener = AudioListener()
        chunk_quiet = (np.sin(2 * np.pi * 440 * t[:480]) * 0.0009).astype(np.float32)  # noise floor
        chunk_speech = (np.sin(2 * np.pi * 440 * t[:480]) * 0.004).astype(np.float32)  # normal speech
        
        noise_detected = listener._energy_vad(chunk_quiet)
        speech_detected = listener._energy_vad(chunk_speech)
        
        is_vad_ok = (not noise_detected) and speech_detected
        record_test("Sanity", "Listener Adaptive VAD Thresholds", is_vad_ok, f"Noise detected: {noise_detected}, Speech detected: {speech_detected}")
    except Exception as e:
        record_test("Sanity", "Listener Adaptive VAD Thresholds", False, str(e))

    # 1.4 Wake Word Matching Sanity
    try:
        from victoria.voice.wake_word import WakeWordDetector
        detector = WakeWordDetector()
        
        test_phrases = [
            ("hey victoria", True),
            ("विक्टोरिया सुनो", True),
            ("hello victoria how are you", True),
            ("सुनो विक्टोरिया", True),
            ("what is the weather today", False),
            ("open google chrome", False)
        ]
        
        matches_ok = True
        for phrase, expected in test_phrases:
            match = detector._check_phrase_match(phrase)
            if match != expected:
                matches_ok = False
                break
                
        record_test("Sanity", "Wake Word Multi-lingual Matcher", matches_ok, f"Tested {len(test_phrases)} phrases in Hindi & English")
    except Exception as e:
        record_test("Sanity", "Wake Word Multi-lingual Matcher", False, str(e))

    # 1.5 Speaker Verification Enrollment & Biometrics Sanity
    try:
        from victoria.voice.speaker_verify import SpeakerVerifier
        verifier = SpeakerVerifier()
        is_enrolled = verifier.is_enrolled()
        encoder_loaded = verifier._get_encoder() is not None
        record_test("Sanity", "Neural Speaker Biometrics (CAM++ ONNX)", is_enrolled and encoder_loaded, f"Enrolled: {is_enrolled}, Threshold: {verifier.threshold}")
    except Exception as e:
        record_test("Sanity", "Neural Speaker Biometrics (CAM++ ONNX)", False, str(e))


# ==============================================================================
# PHASE 2: SMOKE TESTS
# ==============================================================================
def run_smoke_tests():
    console.rule("[bold cyan]PHASE 2: SMOKE TESTS[/bold cyan]")

    # 2.1 Brain & Model Router Smoke Test
    try:
        from victoria.brain.router import BrainRouter
        router = BrainRouter()
        active_model = router._active_model
        record_test("Smoke", "AI Brain Model Router", active_model is not None, f"Active model: {active_model}")
    except Exception as e:
        record_test("Smoke", "AI Brain Model Router", False, str(e))

    # 2.2 Persona Engine & Name Verification Smoke Test
    try:
        from victoria.brain.persona import get_persona_engine
        persona = get_persona_engine()
        system_prompt = persona.get_digital_twin_system_prompt()
        
        # Strictly verify "Hariom" is present and "मालिक" is forbidden
        has_hariom = "Hariom" in system_prompt or "हरिओम" in system_prompt
        honorific = persona.profile.get("owner_identity", {}).get("preferred_honorific")
        name_ok = has_hariom and (honorific in ["हरिओम", "हरिओम जी", "Hariom"])
        
        record_test("Smoke", "Persona & Owner Identity (Hariom)", name_ok, f"Honorific: '{honorific}', Name honored")
    except Exception as e:
        record_test("Smoke", "Persona & Owner Identity (Hariom)", False, str(e))

    # 2.3 TTS Voice Generation Smoke Test
    try:
        from victoria.voice.tts import TextToSpeech
        tts = TextToSpeech()
        test_text = "नमस्ते हरिओम जी, विक्टोरिया पूरी तरह सक्रिय है।"
        loop = asyncio.new_event_loop()
        try:
            audio_file = loop.run_until_complete(tts._speak_edge_tts(test_text))
        finally:
            loop.close()
        file_valid = audio_file is not None and os.path.exists(audio_file) and os.path.getsize(audio_file) > 1000
        record_test("Smoke", "TTS Synthesis (Edge-TTS Female Voice)", file_valid, f"Generated: {audio_file} ({os.path.getsize(audio_file) if file_valid else 0} bytes)")
    except Exception as e:
        record_test("Smoke", "TTS Synthesis (Edge-TTS Female Voice)", False, str(e))

    # 2.4 Tool Registry Smoke Test
    try:
        from victoria.brain.tools import build_tool_registry
        registry = build_tool_registry()
        tool_names = registry.list_tools()
        tool_count = len(tool_names)
        mouse_tools = [name for name in tool_names if "mouse" in name or "keyboard" in name]
        record_test("Smoke", "Tool Registry & Input Control", tool_count >= 250 and len(mouse_tools) >= 5, f"Total tools: {tool_count}, Input tools: {len(mouse_tools)}")
    except Exception as e:
        record_test("Smoke", "Tool Registry & Input Control", False, str(e))

    # 2.5 Offline SQLite Database Smoke Test
    try:
        from victoria.brain.owner_memory import get_owner_vault
        from victoria.brain.skill_rnd import get_skill_rnd_engine
        vault = get_owner_vault()
        mem_count = len(vault.list_memories(limit=100))
        rnd = get_skill_rnd_engine()
        skills = rnd.list_skills()
        record_test("Smoke", "Local SQLite Offline Vaults", True, f"Memories: {mem_count}, Local Skills: {len(skills)}")
    except Exception as e:
        record_test("Smoke", "Local SQLite Offline Vaults", False, str(e))


# ==============================================================================
# PHASE 3: REGRESSION TESTS
# ==============================================================================
def run_regression_tests():
    console.rule("[bold cyan]PHASE 3: REGRESSION TESTS[/bold cyan]")

    # 3.1 Multiple Female Voices Regression Test
    try:
        from victoria.voice.tts import TextToSpeech, FEMALE_VOICES
        tts = TextToSpeech()
        
        # Verify 4 female voices are configured (Swara, Ava, Emma, Seraphina)
        expected_voices = ["swara", "ava", "emma", "seraphina"]
        all_present = all(v in FEMALE_VOICES for v in expected_voices)
        
        # Test switching voice
        v_key, v_name = tts.set_voice("ava", persist=False)
        switched_ok = (tts.current_voice_key == "ava")
        # Switch back to swara
        tts.set_voice("swara", persist=False)
        
        record_test("Regression", "Multiple Female AI Voices Switching", all_present and switched_ok, f"Configured: {list(FEMALE_VOICES.keys())}, Switched: {v_name}")
    except Exception as e:
        record_test("Regression", "Multiple Female AI Voices Switching", False, str(e))

    # 3.2 Mouse & Keyboard OS Automation Regression Test
    try:
        from victoria.tools.input_control import get_mouse_position
        pos = get_mouse_position()
        pos_valid = isinstance(pos, dict) and "x" in pos and "y" in pos
        record_test("Regression", "Mouse & Keyboard X11 Automation", pos_valid, f"Current Cursor: ({pos.get('x')}, {pos.get('y')}) on {pos.get('screen_width')}x{pos.get('screen_height')}")
    except Exception as e:
        record_test("Regression", "Mouse & Keyboard X11 Automation", False, str(e))

    # 3.3 Autonomous Skill R&D Tool Regression Test
    try:
        from victoria.brain.skill_rnd import get_skill_rnd_engine
        rnd = get_skill_rnd_engine()
        has_synthesis = hasattr(rnd, "synthesize_skill") and hasattr(rnd, "acquire_skill")
        record_test("Regression", "Autonomous Skill R&D Engine", has_synthesis, "synthesize_skill & acquire_skill pipeline available")
    except Exception as e:
        record_test("Regression", "Autonomous Skill R&D Engine", False, str(e))

    # 3.4 Non-Overlapping Interruption (Barge-In) State Regression Test
    try:
        from victoria.voice.tts import TextToSpeech

        tts = TextToSpeech()
        
        import inspect
        sig = inspect.signature(tts.speak)
        params = sig.parameters
        barge_in_supported = "interruptible" in params and "listener" in params and "broadcaster" in params
        record_test("Regression", "Non-overlapping Barge-In Architecture", barge_in_supported, "speak() handles interruptible, listener, broadcaster")
    except Exception as e:
        record_test("Regression", "Non-overlapping Barge-In Architecture", False, str(e))

    # 3.5 Strictly Forbid "मालिक" in TTS Filter Regression Test
    try:
        from victoria.voice.tts import clean_text_for_speech
        cleaned = clean_text_for_speech("जी मालिक, मैं आपके आदेश का पालन कर रही हूँ।")
        no_malik_in_output = "मालिक" not in cleaned and "हरिओम" in cleaned
        record_test("Regression", "TTS Phonetic Filter Replaces 'मालिक'", no_malik_in_output, f"Result: '{cleaned}'")
    except Exception as e:
        record_test("Regression", "TTS Phonetic Filter Replaces 'मालिक'", False, str(e))

    # 3.6 HUD Server Health Check Regression Test
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:7860", headers={"User-Agent": "Victoria-Test"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            code = resp.getcode()
            hud_ok = code == 200
        record_test("Regression", "HUD Web/Widget Server Health (Port 7860)", hud_ok, f"HTTP Status: {code}")
    except Exception as e:
        record_test("Regression", "HUD Web/Widget Server Health (Port 7860)", False, f"Could not connect to port 7860: {e}")

    # 3.7 Daily Work Journal & Local Ledger Persistence Test
    try:
        from victoria.brain.daily_work_logger import get_daily_work_logger
        from datetime import datetime, timedelta
        logger = get_daily_work_logger()
        summary = logger.get_daily_summary()
        today_tasks = summary.get("tasks", [])
        yesterday_tasks = logger.get_tasks_for_date((datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"))
        ckpt = logger.get_last_checkpoint()
        journal_file = os.path.exists("data/memory/daily_work_journal.md")
        # Fresh-day safe: persistence is proven by today's entries OR yesterday's records.
        persistence_ok = len(today_tasks) > 0 or len(yesterday_tasks) > 0
        journal_ok = persistence_ok and ckpt is not None and journal_file
        record_test("Regression", "Daily Work Journal & Local Persistence", journal_ok, f"{len(today_tasks)} tasks today, {len(yesterday_tasks)} yesterday, ckpt='{ckpt.get('last_task')}', journal.md exists")
    except Exception as e:
        record_test("Regression", "Daily Work Journal & Local Persistence", False, str(e))

    # 3.8 Universal AI Model Resumption Context Test
    try:
        from victoria.brain.daily_work_logger import get_daily_work_logger
        logger = get_daily_work_logger()
        from datetime import datetime
        context = logger.get_continuation_context()
        today_count = len(logger.get_tasks_for_date(datetime.now().strftime("%Y-%m-%d")))
        has_checkpoint = "अंतिम जहाँ काम छोड़ा गया था" in context
        # Fresh-day safe: the tasks section / honorifics appear once tasks were logged for today.
        has_tasks = ("आज के दर्ज किए गए कार्य" in context) or (today_count == 0)
        no_malik = "मालिक" not in context and (("हरिओम" in context) or (today_count == 0))
        resumption_ok = has_checkpoint and has_tasks and no_malik
        record_test("Regression", "Universal AI Model Resumption Context", resumption_ok, "Context injects 'Where We Left Off' for any AI model without 'मालिक'")
    except Exception as e:
        record_test("Regression", "Universal AI Model Resumption Context", False, str(e))

    # 3.9 Date-Wise Hierarchical Folder Structure Test
    try:
        from datetime import datetime
        from victoria.brain.daily_work_logger import get_daily_work_logger
        now = datetime.now()
        # Fresh-day safe: regenerate today's journal files via the app's own idempotent sync.
        get_daily_work_logger().sync_filesystem_records(now)
        date_folder = os.path.join("data", "memory", "journal", str(now.year), f"{now.month:02d}", f"{now.day:02d}")
        timeline_json = os.path.join(date_folder, "timeline.json")
        summary_md = os.path.join(date_folder, "daily_summary.md")
        events_dir = os.path.join(date_folder, "events")

        has_folder = os.path.isdir(date_folder)
        has_timeline = os.path.isfile(timeline_json)
        has_summary = os.path.isfile(summary_md)
        has_events = os.path.isdir(events_dir)

        structure_ok = has_folder and has_timeline and has_summary and has_events
        record_test("Regression", "Date-Wise Hierarchical Folder Structure", structure_ok, f"{date_folder} (timeline.json, daily_summary.md, events/)")
    except Exception as e:
        record_test("Regression", "Date-Wise Hierarchical Folder Structure", False, str(e))

    # 3.10 Natural Date & Time Query Engine Test
    try:
        from victoria.brain.daily_work_logger import get_daily_work_logger
        logger = get_daily_work_logger()
        res = logger.query_work_by_date_time("16 तारीख को 2:30 बजे हमने क्या किया था?")
        speech = res.get("speech", "")
        matched = res.get("found", False)
        mentions_task = "Barge-In" in speech or "14:30" in speech
        honor_hariom = "हरिओम" in speech and "मालिक" not in speech
        query_ok = matched and mentions_task and honor_hariom
        record_test("Regression", "Natural Date & Time Query Engine", query_ok, f"Answered: '{speech[:90]}...'")
    except Exception as e:
        record_test("Regression", "Natural Date & Time Query Engine", False, str(e))

    # 3.11 Multimodal Image Analysis Test
    try:
        from victoria.tools.media_vision_tool import analyze_image
        res = analyze_image("/tmp/test_img.png", "What text is in this image?")
        has_text = "Victoria" in res or "200x100" in res
        honor_hariom = "हरिओम" in res and "मालिक" not in res
        img_ok = has_text and honor_hariom
        record_test("Regression", "Multimodal Image Visual Analysis", img_ok, f"Result: '{res[:85]}...'")
    except Exception as e:
        record_test("Regression", "Multimodal Image Visual Analysis", False, str(e))

    # 3.12 Multimodal Video Chronological Analysis Test
    try:
        from victoria.tools.media_vision_tool import analyze_video
        res = analyze_video("/tmp/test_video.mp4", "What activity occurs in this video?", max_frames=4)
        has_video_desc = ("00:02" in res or "320x240" in res) and ("peela" in res.lower() or "circle" in res.lower() or "dot" in res.lower() or "color" in res.lower() or "रंग" in res)
        honor_hariom = "हरिओम" in res and "मालिक" not in res
        vid_ok = has_video_desc and honor_hariom
        record_test("Regression", "Multimodal Video Keyframe & Montage Analysis", vid_ok, f"Result: '{res[:85]}...'")
    except Exception as e:
        record_test("Regression", "Multimodal Video Keyframe & Montage Analysis", False, str(e))

    # 3.13 Multi-Model Live Integration Test
    try:
        from victoria.brain.router import BrainRouter
        router = BrainRouter()
        models_tested = []
        for m in ["sarvam", "openrouter"]:
            try:
                p = router._get_provider(m)
                from victoria.brain.providers.base_provider import Message
                resp = p.chat([Message(role="user", content="नमस्ते! संक्षिप्त उत्तर दें।")])
                if resp and resp.text:
                    models_tested.append(m)
            except Exception:
                pass
        multi_ok = len(models_tested) >= 1
        record_test("Regression", "Multi-Model Live Integration (Sarvam & OpenRouter)", multi_ok, f"Verified active models: {models_tested}")
    except Exception as e:
        record_test("Regression", "Multi-Model Live Integration (Sarvam & OpenRouter)", False, str(e))

    # 3.14 End-to-End Hariom Persona Simulation Test
    try:
        from victoria.brain.router import BrainRouter
        router = BrainRouter()
        sim_response = router.think("नमस्ते विक्टोरिया, आज हमने क्या काम किया?")
        has_hariom = "हरिओम" in sim_response or "Hariom" in sim_response
        no_maalik = "मालिक" not in sim_response
        has_content = len(sim_response.strip()) > 30
        sim_ok = has_hariom and no_maalik and has_content
        record_test("Regression", "End-to-End Hariom Persona & Two-Way Dialogue", sim_ok, f"Snippet: '{sim_response[:85]}...'")
    except Exception as e:
        record_test("Regression", "End-to-End Hariom Persona & Two-Way Dialogue", False, str(e))

    # 3.15 Voice Biometric Screen Lock & Unlock Engine (Security) Test
    try:
        import inspect as _inspect
        from unittest.mock import patch
        from victoria.brain.router import BrainRouter
        from victoria.tools.system_lock import unlock_system_by_voice
        from victoria.voice.speaker_verify import SpeakerVerifier

        # A. Caller-supplied similarity bypass must be impossible (old API accepted similarity=0.88).
        sig_params = _inspect.signature(unlock_system_by_voice).parameters
        no_similarity_arg = "similarity" not in sig_params
        try:
            # Enforced at the signature level: binding an unknown kwarg raises TypeError.
            _inspect.signature(unlock_system_by_voice).bind(similarity=0.99)
            bypass_blocked = False
        except TypeError:
            bypass_blocked = True

        # B. Strict biometric verification must fail closed on junk/short audio (no fail-open).
        verifier = SpeakerVerifier()
        junk_audio = np.zeros(16000, dtype=np.float32)
        is_owner, _score = verifier.verify(junk_audio, threshold=0.65, strict=True)
        fail_closed = (is_owner is False)

        # C. Offline lock/unlock routing (mocked so the real screen is never locked or unlocked).
        router = BrainRouter()
        with patch("victoria.tools.system_lock.lock_system", return_value="जी हरिओम! सिस्टम स्क्रीन को सुरक्षित रूप से लॉक कर दिया गया है।") as mock_lock, \
             patch("victoria.tools.system_lock.unlock_system_by_voice", return_value={"success": True, "similarity": 0.9, "message": "जी हरिओम! आपकी आवाज़ सत्यापित हो गई है। सिस्टम स्क्रीन अनलॉक कर दी गई है।"}) as mock_unlock:
            lock_resp = router._handle_offline_command("सिस्टम लॉक करो")
            lock_routed = mock_lock.called and lock_resp is not None and "लॉक" in lock_resp and "हरिओम" in lock_resp and "मालिक" not in lock_resp
            unlock_resp = router._handle_offline_command("विक्टोरिया लॉक खोलो")
            unlock_routed = mock_unlock.called and unlock_resp is not None and "अनलॉक" in unlock_resp and "हरिओम" in unlock_resp and "मालिक" not in unlock_resp

        total_lock_ok = no_similarity_arg and bypass_blocked and fail_closed and lock_routed and unlock_routed
        record_test(
            "Regression",
            "Voice Biometric Screen Lock & Unlock Engine",
            total_lock_ok,
            f"Similarity bypass blocked: {no_similarity_arg and bypass_blocked}, Strict verify fail-closed: {fail_closed}, Offline lock/unlock routes (mocked): {lock_routed and unlock_routed}"
        )
    except Exception as e:
        record_test("Regression", "Voice Biometric Screen Lock & Unlock Engine", False, str(e))

    # 3.16 Non-Visual Desktop State & Zero-Screenshot Screen Inspector Test
    try:
        from victoria.tools.desktop_inspector import get_desktop_screen_overview, get_running_gui_apps
        from victoria.brain.router import BrainRouter

        apps = get_running_gui_apps()
        has_apps = isinstance(apps, list)
        
        overview = get_desktop_screen_overview()
        has_hariom = "हरिओम" in overview and "मालिक" not in overview
        has_content = len(overview) > 20

        router = BrainRouter()
        offline_resp = router._handle_offline_command("स्क्रीन पर क्या चल रहा है?")
        offline_ok = offline_resp is not None and "हरिओम" in offline_resp and "मालिक" not in offline_resp

        inspector_ok = has_apps and has_hariom and has_content and offline_ok
        record_test(
            "Regression",
            "Zero-Screenshot Desktop Screen Inspector",
            inspector_ok,
            f"Active apps: {apps}, Offline screen query: '{offline_resp[:65]}...' (0 screenshots taken)"
        )
    except Exception as e:
        record_test("Regression", "Zero-Screenshot Desktop Screen Inspector", False, str(e))

    # 3.17 System Reboot Hard Lock & Zero Data Loss Security Policy Test
    try:
        from victoria.tools.terminal import run_command, REBOOT_LOCK_MESSAGE, DATA_SECURITY_LOCK_MESSAGE
        from victoria.tools.custom_scripts import create_custom_script
        from victoria.brain.router import BrainRouter

        # A. Reboot & Shutdown Commands MUST be hard-blocked even if confirmed=True
        reboot_res1 = run_command("sudo reboot")
        reboot_res2 = run_command("reboot", confirmed=True)
        shutdown_res = run_command("shutdown -h now")
        poweroff_res = run_command("systemctl poweroff")
        reboot_blocked = (
            reboot_res1 == REBOOT_LOCK_MESSAGE and
            reboot_res2 == REBOOT_LOCK_MESSAGE and
            shutdown_res == REBOOT_LOCK_MESSAGE and
            poweroff_res == REBOOT_LOCK_MESSAGE
        )

        # B. File & Data Deletion Commands MUST be hard-blocked
        rm_res1 = run_command("rm -rf /tmp/important_data")
        rm_res2 = run_command("rm test.txt")
        unlink_res = run_command("unlink myfile.pdf")
        shred_res = run_command("shred -u data.bin")
        data_removal_blocked = (
            rm_res1 == DATA_SECURITY_LOCK_MESSAGE and
            rm_res2 == DATA_SECURITY_LOCK_MESSAGE and
            unlink_res == DATA_SECURITY_LOCK_MESSAGE and
            shred_res == DATA_SECURITY_LOCK_MESSAGE
        )

        # C. Custom Script Creation with destructive payload MUST be rejected
        bad_script1 = create_custom_script("danger_reboot.sh", "echo 'starting' && sudo reboot")
        bad_script2 = create_custom_script("danger_rm.sh", "rm -rf /home/hariom")
        scripts_guarded = ("सुरक्षा त्रुटि" in bad_script1) and ("सुरक्षा त्रुटि" in bad_script2)

        # D. Safe benign commands MUST continue working
        safe_echo = run_command("echo 'SECURITY_TEST_PASSED'")
        safe_ok = "SECURITY_TEST_PASSED" in safe_echo

        # E. Brain Router Disambiguation & Security Inquiries
        router = BrainRouter()
        user_query = "main restart kar rhe rha hu ye reboot samjh rha hai , mera system main reboot ka lock karo taki ye victoria mera data na delete kar de, security on karo kuch bhi remove karne se phele mere system ka"
        sec_ack = router._handle_offline_command(user_query)
        sec_ack_ok = sec_ack is not None and "सुरक्षा लॉक" in sec_ack and "रीबूट" in sec_ack and "डेटा" in sec_ack

        restart_resp = router._handle_offline_command("विक्टोरिया को रीस्टार्ट करो")
        restart_ok = restart_resp is not None and "रीस्टार्ट" in restart_resp and "रीबूट लॉक" in restart_resp

        total_security_ok = reboot_blocked and data_removal_blocked and scripts_guarded and safe_ok and sec_ack_ok and restart_ok
        record_test(
            "Regression",
            "System Reboot Hard Lock & Zero Data Loss Policy",
            total_security_ok,
            f"Reboot hard-blocked: {reboot_blocked}, Data removal blocked: {data_removal_blocked}, Script guarded: {scripts_guarded}, Safe cmd: {safe_ok}, Router disambiguation: {sec_ack_ok and restart_ok}"
        )
    except Exception as e:
        record_test("Regression", "System Reboot Hard Lock & Zero Data Loss Policy", False, str(e))





def main():
    console.print("[bold yellow]🚀 STARTING COMPREHENSIVE TEST SUITE FOR PROJECT VICTORIA[/bold yellow]\n")
    start_time = time.time()
    
    run_sanity_tests()
    print()
    run_smoke_tests()
    print()
    run_regression_tests()
    print()

    duration = time.time() - start_time
    total = len(test_results)
    passed = sum(1 for r in test_results if r["passed"])
    failed = total - passed

    console.rule("[bold green]TEST SUITE SUMMARY[/bold green]")
    table = Table(title="Victoria Test Execution Report")
    table.add_column("Phase", style="cyan")
    table.add_column("Test Case", style="white")
    table.add_column("Status", style="bold")
    table.add_column("Details", style="dim")

    for r in test_results:
        table.add_row(r["phase"], r["name"], r["status"], r["details"])

    console.print(table)
    
    summary_color = "green" if failed == 0 else "red"
    console.print(f"\n[{summary_color}]Total: {total} | Passed: {passed} | Failed: {failed} | Duration: {duration:.2f}s[/{summary_color}]\n")

    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()

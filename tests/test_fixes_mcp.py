"""
Regression tests for the bug-fix batch + Victoria MCP server.

Run:
    python3 -m pytest tests/test_fixes_mcp.py -v
"""

import inspect
import io
import json
import socket
from unittest import mock

from victoria.brain.providers.base_provider import Message
from victoria.brain.router import BrainRouter, _response_is_provider_error
from victoria.mcp import server as mcp_server
from victoria.tools.terminal import check_command_safety
from victoria.voice.voice_model_manager import detect_model_choice, is_confirm_current


# ---------------------------------------------------------------------------
# Router: provider-error failover must not hijack normal answers
# ---------------------------------------------------------------------------

class TestProviderErrorDetection:
    def test_real_provider_errors_detected(self):
        assert _response_is_provider_error("API error: 429 quota exceeded") is True
        assert _response_is_provider_error("Gemini connection error: timed out") is True
        assert _response_is_provider_error("Ollama error: model not found") is True
        assert _response_is_provider_error("OpenCode provider error: 503") is True
        assert _response_is_provider_error("Provider error: bad gateway") is True

    def test_normal_answers_are_not_errors(self):
        assert _response_is_provider_error("") is False
        assert _response_is_provider_error(None) is False
        # A normal answer mentioning error-ish words must NOT be treated as an error
        assert _response_is_provider_error(
            "Token limit aur 503 ka matlab server overload hota hai"
        ) is False
        assert _response_is_provider_error("429 quota ke bare mein jaanna hai?") is False


# ---------------------------------------------------------------------------
# Router: conversation trim must not start with orphaned tool messages
# ---------------------------------------------------------------------------

class TestConversationTrim:
    def test_trim_drops_leading_tool_messages(self):
        router = BrainRouter.__new__(BrainRouter)
        router._conversation = [
            Message(role="user", content="m1"),
            Message(role="tool", content="t1", tool_call_id="1"),
            Message(role="tool", content="t2", tool_call_id="2"),
            Message(role="user", content="m2"),
        ]
        with mock.patch("victoria.brain.router.get_config") as mcfg:
            mcfg.return_value.get.return_value = 3
            router._trim_conversation()
        # Slice keeps the last 3 => [tool, tool, user]; leading tool msgs dropped.
        assert [m.role for m in router._conversation] == ["user"]
        assert router._conversation[0].content == "m2"


# ---------------------------------------------------------------------------
# Router: dangerous-tool confirmation gate (fail-closed)
# ---------------------------------------------------------------------------

class TestDangerousToolGate:
    def test_fail_closed_without_callback(self):
        router = BrainRouter.__new__(BrainRouter)
        router.confirm_callback = None
        assert router._confirm_dangerous_tool("delete_file", {}) is False

    def test_callback_decides(self):
        router = BrainRouter.__new__(BrainRouter)
        router.confirm_callback = lambda name, args: True
        assert router._confirm_dangerous_tool("delete_file", {}) is True
        router.confirm_callback = lambda name, args: False
        assert router._confirm_dangerous_tool("delete_file", {}) is False

    def test_callback_exception_denies(self):
        router = BrainRouter.__new__(BrainRouter)

        def boom(name, args):
            raise RuntimeError("no confirmation channel")

        router.confirm_callback = boom
        assert router._confirm_dangerous_tool("delete_file", {}) is False


# ---------------------------------------------------------------------------
# Voice model manager: no accidental model switches / false confirmations
# ---------------------------------------------------------------------------

class TestVoiceModelGuards:
    def test_detect_model_choice_positive(self):
        assert detect_model_choice("gemini") is not None
        got = detect_model_choice("deepseek se baat karo")
        assert got is not None and got[0] == "opencode_deepseek"

    def test_detect_model_choice_ignores_questions(self):
        assert detect_model_choice("gemini kya hota hai") is None
        assert detect_model_choice("flash lite ka matlab kya hai") is None
        assert detect_model_choice("google kya hota hai") is None

    def test_confirm_current_positive(self):
        assert is_confirm_current("theek hai") is True
        assert is_confirm_current("यही ठीक है") is True
        assert is_confirm_current("continue karo") is True

    def test_confirm_current_rejects_tasks_and_long_sentences(self):
        assert is_confirm_current("start") is False
        assert is_confirm_current("terminal kholo") is False
        assert is_confirm_current("theek hai, ab chrome kholo aur search karo") is False


# ---------------------------------------------------------------------------
# Terminal / script safety patterns
# ---------------------------------------------------------------------------

class TestTerminalSafety:
    def test_safe_commands_allowed(self):
        assert check_command_safety("ls -la") is None
        assert check_command_safety("echo hello world") is None
        assert check_command_safety("cat notes.txt") is None

    def test_reboot_shutdown_locked(self):
        assert check_command_safety("sudo reboot") is not None
        assert check_command_safety("systemctl poweroff") is not None

    def test_data_removal_locked(self):
        assert check_command_safety("rm -rf /tmp/data") is not None
        assert check_command_safety("git clean -fd") is not None
        assert check_command_safety(": > important.txt") is not None
        assert check_command_safety("cp /dev/null notes.txt") is not None


class TestCustomScriptContainment:
    def test_relative_escape_rejected(self, tmp_path, monkeypatch):
        import victoria.tools.custom_scripts as cs
        monkeypatch.setattr(cs, "SCRIPTS_DIR", tmp_path / "custom")
        out = cs.run_custom_script("../../etc/passwd")
        assert "सुरक्षा" in out  # containment error, never executed

    def test_absolute_path_rejected(self, tmp_path, monkeypatch):
        import victoria.tools.custom_scripts as cs
        monkeypatch.setattr(cs, "SCRIPTS_DIR", tmp_path / "custom")
        out = cs.run_custom_script("/bin/echo")
        assert "सुरक्षा" in out


# ---------------------------------------------------------------------------
# Voice unlock: real biometrics only, no caller-supplied score
# ---------------------------------------------------------------------------

class TestVoiceUnlock:
    def test_signature_has_no_caller_similarity(self):
        from victoria.tools.system_lock import unlock_system_by_voice
        params = inspect.signature(unlock_system_by_voice).parameters
        assert "similarity" not in params
        assert "required_threshold" in params

    def test_fails_closed_without_enrollment(self):
        from victoria.tools import system_lock
        with mock.patch(
            "victoria.voice.speaker_verify.SpeakerVerifier.is_enrolled",
            return_value=False,
        ):
            res = system_lock.unlock_system_by_voice()
        assert res["success"] is False


# ---------------------------------------------------------------------------
# Wake word: word-boundary matching (no false wakes from "victory", etc.)
# ---------------------------------------------------------------------------

class TestWakeWord:
    def test_word_boundaries(self):
        from victoria.voice.wake_word import WakeWordDetector
        det = WakeWordDetector()
        assert det._check_phrase_match("hey victoria are you there") is True
        assert det._check_phrase_match("हाय विक्टोरिया") is True
        # STT commonly hears "Victoria" as "viktor" — accepted variant by design
        assert det._check_phrase_match("hey viktor") is True
        # Substrings of bigger words must never wake her
        assert det._check_phrase_match("we won a great victory today") is False
        assert det._check_phrase_match("history of the victorian era") is False
        assert det._check_phrase_match("") is False


# ---------------------------------------------------------------------------
# Voice events: widget + HUD ports and cross-process commands
# ---------------------------------------------------------------------------

class TestVoiceEventsPorts:
    def test_ports_are_distinct(self):
        from victoria.voice import voice_events as ve
        assert len({ve.EVENT_PORT, ve.HUD_EVENT_PORT, ve.COMMAND_PORT}) == 3

    def test_broadcaster_fans_out_to_both_listener_ports(self):
        from victoria.voice.voice_events import (
            VoiceEventBroadcaster, VoiceEventListener, EVENT_PORT, HUD_EVENT_PORT,
        )
        received_widget, received_hud = [], []
        l1 = VoiceEventListener(on_event=received_widget.append, port=EVENT_PORT)
        l2 = VoiceEventListener(on_event=received_hud.append, port=HUD_EVENT_PORT)
        l1.start()
        l2.start()
        try:
            VoiceEventBroadcaster().standby()
            import time
            for _ in range(20):
                if received_widget and received_hud:
                    break
                time.sleep(0.05)
        finally:
            l1.stop()
            l2.stop()
        assert received_widget, "widget listener got no event"
        assert received_hud, "HUD listener got no event"


# ---------------------------------------------------------------------------
# TTS singleton
# ---------------------------------------------------------------------------

class TestTTSSingleton:
    def test_get_tts_is_singleton(self):
        from victoria.voice.tts import get_tts
        assert get_tts() is get_tts()


# ---------------------------------------------------------------------------
# HUD: dangerous tools fail-closed unless explicitly allowed
# ---------------------------------------------------------------------------

class TestHUDSafety:
    def test_hud_confirm_matches_config(self):
        import victoria.hud.server as srv
        from victoria.config import get_config
        allowed = bool(get_config().get("tools.allow_dangerous_in_hud", False))
        assert srv.brain_router.confirm_callback("terminal", {}) is allowed

    def test_audio_filename_traversal_rejected(self):
        import victoria.hud.server as srv
        from fastapi.testclient import TestClient
        client = TestClient(srv.app)
        resp = client.get("/api/audio/..%2F..%2Fvictoria%2Fconfig.py")
        assert resp.status_code in (400, 404)


# ---------------------------------------------------------------------------
# Live preview server binds to localhost only
# ---------------------------------------------------------------------------

class TestPreviewLocalhostBinding:
    def test_binds_127_0_0_1(self, tmp_path):
        from victoria.builder.preview import LivePreviewServer
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        server = LivePreviewServer()
        msg = server.start(str(tmp_path), port=port)
        try:
            assert server._server is not None, msg
            assert server._server.server_address[0] == "127.0.0.1"
        finally:
            server.stop()


# ---------------------------------------------------------------------------
# Config: custom-model env persistence map
# ---------------------------------------------------------------------------

class TestCustomModelPersistence:
    def test_env_map(self):
        from victoria.config import CUSTOM_MODEL_ENV
        assert CUSTOM_MODEL_ENV["groq"] == "GROQ_CUSTOM_MODEL"
        assert CUSTOM_MODEL_ENV["gemini_pro"] == "GEMINI_CUSTOM_MODEL"
        assert CUSTOM_MODEL_ENV["openrouter"] == "OPENROUTER_CUSTOM_MODEL"


# ---------------------------------------------------------------------------
# MCP server protocol
# ---------------------------------------------------------------------------

class TestMCPServer:
    def _server(self):
        out = io.StringIO()
        return mcp_server.MCPServer(out_stream=out), out

    def test_initialize_handshake(self):
        srv, out = self._server()
        srv.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        resp = json.loads(out.getvalue().strip())
        assert resp["result"]["protocolVersion"] == mcp_server.PROTOCOL_VERSION
        assert resp["result"]["serverInfo"]["name"] == "victoria"
        assert "tools" in resp["result"]["capabilities"]

    def test_tools_list_contains_all_eight(self):
        srv, out = self._server()
        srv.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        resp = json.loads(out.getvalue().strip())
        tools = resp["result"]["tools"]
        names = {t["name"] for t in tools}
        assert names == {
            "victoria_chat", "victoria_list_models", "victoria_switch_model",
            "victoria_status", "victoria_run_tool", "victoria_remember",
            "victoria_recall", "victoria_speak",
        }
        for t in tools:
            assert t["inputSchema"]["type"] == "object"
            assert t["description"]

    def test_unknown_method_error(self):
        srv, out = self._server()
        srv.handle_message({"jsonrpc": "2.0", "id": 3, "method": "bogus/method"})
        resp = json.loads(out.getvalue().strip())
        assert resp["error"]["code"] == -32601

    def test_unknown_tool_call_errors(self):
        srv, out = self._server()
        srv.handle_message({
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "nope", "arguments": {}},
        })
        resp = json.loads(out.getvalue().strip())
        assert resp["error"]["code"] == -32602

    def test_bad_arguments_reported_not_crashed(self):
        srv, out = self._server()
        srv.handle_message({
            "jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {"name": "victoria_recall", "arguments": {"bogus": 1}},
        })
        resp = json.loads(out.getvalue().strip())
        assert resp["result"]["isError"] is True

    def test_notifications_get_no_response(self):
        srv, out = self._server()
        srv.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"})
        assert out.getvalue() == ""

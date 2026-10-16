"""
Victoria - JARVIS / Iron Man Floating Hologram Arc Reactor Widget
A futuristic, transparent, floating on-screen desktop widget that reacts
in real-time when Victoria is awakened, listening, thinking, and speaking.
"""

import sys
import math
import random
import webbrowser
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QWidget, QMenu
)
from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QPointF, QRectF
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QRadialGradient, QFont, QAction, QCursor
)

from victoria.voice.voice_events import VoiceEventListener, EVENT_PORT


class JarvisArcReactorWidget(QWidget):
    """
    Floating, frameless, translucent Iron Man Arc Reactor / JARVIS HUD widget.
    Always stays on top of desktop windows and animates audio waveforms in real time.
    """

    def __init__(self, size: int = 240):
        super().__init__()

        self.widget_size = size
        self.state = "standby"  # standby | listening | thinking | speaking
        self.sub_text = "STANDBY // स्लीप मोड"
        self.active_model_name = "opencode"

        # Animation states
        self.angle_outer = 0.0
        self.angle_inner = 0.0
        self.pulse_phase = 0.0
        self.waveform_phases = [random.random() * math.pi * 2 for _ in range(16)]
        self.audio_level = 0.2

        # Dragging support
        self._dragging = False
        self._drag_start_pos = QPoint()

        self._setup_window()
        self._setup_timer()
        self._setup_ipc()

    def _setup_window(self):
        """Configure frameless, translucent, always-on-top window attributes."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.SubWindow
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.resize(self.widget_size, self.widget_size + 40)

        # Position at bottom-right corner of primary screen by default
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            x = geom.width() - self.width() - 30
            y = geom.height() - self.height() - 40
            self.move(x, y)

    def _setup_timer(self):
        """60 FPS smooth rendering loop."""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_animation)
        self.timer.start(16)  # ~60 FPS

    def _setup_ipc(self):
        """Subscribe to Victoria's voice events over local UDP."""
        self.listener = VoiceEventListener(on_event=self._handle_voice_event, port=EVENT_PORT)
        try:
            self.listener.start()
        except Exception as e:
            print(f"Widget IPC start note: {e}")

    def _handle_voice_event(self, data: dict):
        """Called asynchronously when Victoria broadcasts an event."""
        event_type = data.get("event")
        new_state = data.get("state", self.state)

        if event_type == "model_switched":
            m_name = data.get("model", "")
            self.set_state("listening", f"⚡ CONNECTED: {m_name.upper()}")
        elif event_type == "wake" or new_state == "listening":
            self.set_state("listening", "🎙️ LISTENING // सुन रही हूँ...")
        elif event_type == "thinking" or new_state == "thinking":
            self.set_state("thinking", "🧠 PROCESSING // सोच रही हूँ...")
        elif event_type == "speaking" or new_state == "speaking":
            text_preview = data.get("text", "")
            if len(text_preview) > 30:
                text_preview = text_preview[:27] + "..."
            self.set_state("speaking", f"🗣️ SPEAKING // {text_preview or 'जवाब दे रही हूँ...'}")
        elif event_type == "standby" or new_state == "standby":
            self.set_state("standby", "⚡ STANDBY // स्लीप मोड")

    def set_state(self, state: str, text: str = ""):
        self.state = state
        self.sub_text = text or self.sub_text
        if state == "listening":
            self.audio_level = 0.8
        elif state == "speaking":
            self.audio_level = 0.7
        elif state == "thinking":
            self.audio_level = 0.4
        else:
            self.audio_level = 0.1
        self.update()

    def _update_animation(self):
        """Advance rotation angles and sine wave phases."""
        speed = 2.0 if self.state == "thinking" else (1.2 if self.state in ("listening", "speaking") else 0.4)

        self.angle_outer = (self.angle_outer + speed * 0.8) % 360.0
        self.angle_inner = (self.angle_inner - speed * 1.2) % 360.0
        self.pulse_phase = (self.pulse_phase + 0.05) % (math.pi * 2)

        for i in range(len(self.waveform_phases)):
            self.waveform_phases[i] = (self.waveform_phases[i] + 0.1 + (i * 0.02)) % (math.pi * 2)

        self.update()

    # ---------------- Mouse Events (Drag & Click) ----------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if self._dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_start_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            # If clicked without significant drag, toggle listening state
            center_x = self.width() / 2.0
            center_y = self.widget_size / 2.0
            click_dist = math.hypot(event.position().x() - center_x, event.position().y() - center_y)
            if click_dist < (self.widget_size / 2.8):
                self._toggle_listen_click()
            event.accept()

    def _toggle_listen_click(self):
        """User clicked the central Arc Reactor directly."""
        if self.state == "standby":
            self.set_state("listening", "🎙️ LISTENING // सुन रही हूँ...")
            # Trigger voice listener via IPC command port if active
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.sendto(b'{"command": "trigger_listen"}', ("127.0.0.1", 49381))
                sock.close()
            except Exception:
                pass
        else:
            self.set_state("standby", "⚡ STANDBY // स्लीप मोड")

    def _show_context_menu(self, global_pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(10, 15, 30, 0.95);
                border: 1px solid #00f0ff;
                border-radius: 8px;
                color: #e0f2fe;
                padding: 6px;
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 13px;
            }
            QMenu::item {
                padding: 8px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background: rgba(0, 240, 255, 0.25);
                color: #ffffff;
            }
        """)

        talk_action = QAction("🎙️ बात करें (Talk to Victoria)", self)
        talk_action.triggered.connect(lambda: self.set_state("listening", "🎙️ LISTENING // सुन रही हूँ..."))
        menu.addAction(talk_action)

        hud_action = QAction("🌐 3D Web HUD खोलें (Open Web HUD)", self)
        hud_action.triggered.connect(lambda: webbrowser.open("http://127.0.0.1:7860"))
        menu.addAction(hud_action)

        standby_action = QAction("💤 स्लीप मोड (Standby)", self)
        standby_action.triggered.connect(lambda: self.set_state("standby", "⚡ STANDBY // स्लीप मोड"))
        menu.addAction(standby_action)

        menu.addSeparator()

        quit_action = QAction("✖️ विजेट बंद करें (Hide)", self)
        quit_action.triggered.connect(self.close)
        menu.addAction(quit_action)

        menu.exec(global_pos)

    # ---------------- Paint Event (Iron Man Arc Reactor) ----------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        center_x = self.width() / 2.0
        center_y = self.widget_size / 2.0
        radius = (self.widget_size - 30) / 2.0

        # Dynamic color theme based on state
        if self.state == "listening":
            core_cyan = QColor(0, 240, 255)
            glow_purple = QColor(168, 85, 247, 180)
            glow_intensity = 0.9 + 0.1 * math.sin(self.pulse_phase * 2)
            alpha_mult = 1.0
        elif self.state == "thinking":
            core_cyan = QColor(168, 85, 247)
            glow_purple = QColor(0, 240, 255, 180)
            glow_intensity = 0.9 + 0.1 * math.sin(self.pulse_phase * 3)
            alpha_mult = 1.0
        elif self.state == "speaking":
            core_cyan = QColor(0, 255, 200)
            glow_purple = QColor(255, 180, 0, 180)
            glow_intensity = 0.95 + 0.05 * math.sin(self.pulse_phase * 2.5)
            alpha_mult = 1.0
        else:  # standby
            core_cyan = QColor(0, 200, 230)
            glow_purple = QColor(90, 40, 180, 100)
            glow_intensity = 0.4 + 0.15 * math.sin(self.pulse_phase)
            alpha_mult = 0.55

        # 1. Background Ambient Radial Halo
        glow_grad = QRadialGradient(QPointF(center_x, center_y), radius * 1.3)
        glow_grad.setColorAt(0.0, QColor(core_cyan.red(), core_cyan.green(), core_cyan.blue(), int(140 * glow_intensity * alpha_mult)))
        glow_grad.setColorAt(0.5, QColor(glow_purple.red(), glow_purple.green(), glow_purple.blue(), int(60 * glow_intensity * alpha_mult)))
        glow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(glow_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(center_x, center_y), radius * 1.3, radius * 1.3)

        # 2. Outer Segmented Rotating Ring (HUD Sectors)
        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(self.angle_outer)

        outer_pen = QPen(QColor(core_cyan.red(), core_cyan.green(), core_cyan.blue(), int(220 * alpha_mult)), 2.5)
        outer_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(outer_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        num_segments = 6
        segment_span = 44  # degrees
        for i in range(num_segments):
            start_angle = int((i * 60 - segment_span / 2) * 16)
            span_angle = int(segment_span * 16)
            outer_rect = QRectF(-radius, -radius, radius * 2, radius * 2)
            painter.drawArc(outer_rect, start_angle, span_angle)

        # Draw HUD Tick Marks on outer ring
        tick_pen = QPen(QColor(255, 255, 255, int(180 * alpha_mult)), 1.5)
        painter.setPen(tick_pen)
        for i in range(24):
            deg = math.radians(i * 15)
            r1 = radius - 4
            r2 = radius + (4 if i % 6 == 0 else 1)
            x1 = r1 * math.cos(deg)
            y1 = r1 * math.sin(deg)
            x2 = r2 * math.cos(deg)
            y2 = r2 * math.sin(deg)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        painter.restore()

        # 3. Middle Counter-Rotating Ring with Arc Cutouts
        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(self.angle_inner)

        mid_radius = radius * 0.76
        mid_pen = QPen(QColor(glow_purple.red(), glow_purple.green(), glow_purple.blue(), int(200 * alpha_mult)), 1.8)
        painter.setPen(mid_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        for i in range(4):
            start_deg = int((i * 90 + 10) * 16)
            span_deg = int(70 * 16)
            painter.drawArc(QRectF(-mid_radius, -mid_radius, mid_radius * 2, mid_radius * 2), start_deg, span_deg)

        # 8 Concentric Reactor Nodes
        for i in range(8):
            deg = math.radians(i * 45)
            nx = mid_radius * math.cos(deg)
            ny = mid_radius * math.sin(deg)
            node_color = QColor(255, 255, 255, int(220 * alpha_mult))
            painter.setBrush(QBrush(node_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(nx, ny), 3, 3)

        painter.restore()

        # 4. Central Glowing Arc Reactor Core
        core_radius = radius * 0.48
        core_grad = QRadialGradient(QPointF(center_x, center_y), core_radius)
        core_grad.setColorAt(0.0, QColor(255, 255, 255, int(255 * alpha_mult)))
        core_grad.setColorAt(0.35, QColor(core_cyan.red(), core_cyan.green(), core_cyan.blue(), int(220 * alpha_mult)))
        core_grad.setColorAt(0.75, QColor(glow_purple.red(), glow_purple.green(), glow_purple.blue(), int(160 * alpha_mult)))
        core_grad.setColorAt(1.0, QColor(10, 15, 30, int(240 * alpha_mult)))

        painter.setBrush(QBrush(core_grad))
        painter.setPen(QPen(QColor(core_cyan.red(), core_cyan.green(), core_cyan.blue(), int(240 * alpha_mult)), 2))
        painter.drawEllipse(QPointF(center_x, center_y), core_radius, core_radius)

        # 5. Dynamic Audio Soundwave Bars (Reactive Equalizer across the Core)
        if self.state in ("listening", "speaking", "thinking"):
            painter.save()
            bars_count = 12
            total_wave_width = core_radius * 1.5
            bar_w = total_wave_width / (bars_count * 1.5)
            start_x = center_x - (total_wave_width / 2.0)

            for b_i in range(bars_count):
                b_phase = self.waveform_phases[b_i]
                # Center-weighted bell curve multiplier
                bell = math.sin((b_i + 1) / (bars_count + 1) * math.pi)
                h = 6 + (28.0 * bell * (0.35 + 0.65 * math.sin(b_phase) ** 2) * self.audio_level)
                bx = start_x + (b_i * bar_w * 1.5)
                by = center_y - (h / 2.0)

                bar_color = QColor(255, 255, 255, 240) if b_i in (5, 6) else core_cyan
                painter.setBrush(QBrush(bar_color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(QRectF(bx, by, bar_w, h), 2, 2)
            painter.restore()
        else:
            # Standby central emblem: Elegant "V" logo
            painter.save()
            font = QFont("Segoe UI", 16, QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255, int(220 * glow_intensity)))
            text_rect = QRectF(center_x - 20, center_y - 18, 40, 36)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, "⚡")
            painter.restore()

        # 6. Bottom Holographic Status Subtitle
        painter.save()
        label_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        label_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
        painter.setFont(label_font)

        badge_rect = QRectF(10, self.widget_size + 4, self.width() - 20, 26)
        painter.setBrush(QBrush(QColor(10, 15, 30, int(220 * alpha_mult))))
        painter.setPen(QPen(QColor(core_cyan.red(), core_cyan.green(), core_cyan.blue(), int(180 * alpha_mult)), 1))
        painter.drawRoundedRect(badge_rect, 13, 13)

        painter.setPen(QColor(core_cyan.red(), core_cyan.green(), core_cyan.blue(), int(255 * alpha_mult)))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, self.sub_text)
        painter.restore()


def run_floating_widget():
    """Launch the standalone JARVIS Floating Widget."""
    app = QApplication.instance() or QApplication(sys.argv)
    widget = JarvisArcReactorWidget()
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_floating_widget()

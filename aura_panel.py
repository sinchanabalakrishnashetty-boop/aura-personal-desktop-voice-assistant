"""
Aura panel UI module (clean, non-circular).
Provides:
 - AuraPanel(QWidget) : main interactive panel (chat + voice)
 - MainWindow(QWidget) : top-level window that hosts AuraPanel
Integrated with:
 - EnhancedCommandEngine (NLP + fuzzy)
 - Wake-word listener ("Hey Aura")
 - Speech recognition (OpenAI Whisper + Google Speech Recognition fallback)
 - Natural TTS voice with speaking animation
"""

import math
import random
import os
import re
import time

from PyQt6.QtCore import (
    Qt, QRectF, QPointF, QTimer, pyqtSignal, QThread,
    QPropertyAnimation, QEasingCurve, QSize
)
from PyQt6.QtGui import (
    QPainter, QPaintEvent, QColor, QPen, QBrush, QFont,
    QLinearGradient, QRadialGradient, QPainterPath, QRegion
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QHBoxLayout, QVBoxLayout,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton, QGraphicsOpacityEffect
)

import speech_recognition as sr
HAVE_WHISPER = False
try:
    from openai import OpenAI
    HAVE_WHISPER = True
except Exception:
    HAVE_WHISPER = False

whisper_client = None
_ai_client = None
if HAVE_WHISPER:
    try:
        _ai_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not _ai_key or _ai_key.endswith("-here"):
            try:
                from aura.config import OPENAI_API_KEY as _cfg_key  # type: ignore
                if _cfg_key and not _cfg_key.endswith("-here"):
                    _ai_key = _cfg_key.strip()
            except Exception:
                pass
        if _ai_key:
            _ai_client = OpenAI(api_key=_ai_key)
    except Exception:
        _ai_client = None
from aura import get_engine
from aura.voice import is_speaking as voice_is_speaking
from aura.command_engine import generate_ai_response

try:
    from aura.intelligence_stack import InputProcessingModule
except Exception:
    InputProcessingModule = None
try:
    from history import save_history
except Exception:
    def save_history(id, t, r, m): 
        pass
BG_DARK   = QColor(18, 20, 28, 255)
PILL_BG   = QColor(28, 32, 42, 230)
NEON_CYAN = QColor(90, 240, 255)
NEON_BLUE = QColor(110, 116, 255)
NEON_PINK = QColor(255, 120, 210)
TEXT_WHITE = QColor(238, 242, 248)
CARD_BG   = QColor(22, 26, 38, 245)

def set_aa(p: QPainter):
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
class StatusBar(QWidget):
    """Thin animated status bar shown beneath the AURA header."""

    STATES = {
        "idle":      (QColor(60,  65,  80,   0), ""),
        "listening": (NEON_CYAN,               "Listening…"),
        "thinking":  (NEON_BLUE,               "Thinking…"),
        "speaking":  (NEON_PINK,               "Speaking…"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(22)
        self._state = "idle"
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def set_state(self, state: str):
        if state != self._state:
            self._state = state
            self.update()

    def _tick(self):
        self._t += 0.03
        if self._state != "idle":
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        set_aa(p)
        w, h = self.width(), self.height()
        color, label = self.STATES.get(self._state, self.STATES["idle"])

        if self._state == "idle":
            p.end()
            return
        bar_w = 4
        gap = 5
        n_bars = 7
        total = n_bars * bar_w + (n_bars - 1) * gap
        x0 = (w - total) / 2
        for i in range(n_bars):
            phase = self._t * 3.5 + i * 0.7
            ht = int(6 + 8 * abs(math.sin(phase)))
            if self._state == "thinking":
                ht = int(3 + 3 * abs(math.sin(self._t * 1.5 + i * 0.4)))
            alpha = 180 + int(60 * abs(math.sin(phase)))
            c = QColor(color)
            c.setAlpha(alpha)
            p.setBrush(QBrush(c))
            p.setPen(Qt.PenStyle.NoPen)
            bx = int(x0 + i * (bar_w + gap))
            by = (h - ht) // 2
            p.drawRoundedRect(bx, by, bar_w, ht, 2, 2)
        c2 = QColor(color)
        c2.setAlpha(160)
        p.setPen(QPen(c2))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label)
        p.end()
class ResponseCard(QWidget):
    """Siri/Alexa-style response overlay card."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setVisible(False)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)
        self._fade = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade.setDuration(220)
        self._fade.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.dismiss)
        self._you_lbl = QLabel("", self)
        self._you_lbl.setWordWrap(True)
        self._you_lbl.setStyleSheet(
            "color: rgba(150,200,255,200); font-size: 11px; font-style: italic;"
        )

        self._resp_lbl = QLabel("", self)
        self._resp_lbl.setWordWrap(True)
        self._resp_lbl.setStyleSheet(
            "color: rgba(230,240,255,255); font-size: 14px; font-weight: 500;"
        )
        self._wave = StatusBar(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(6)
        layout.addWidget(self._you_lbl)
        layout.addWidget(self._resp_lbl)
        layout.addWidget(self._wave)

    def show_response(self, user_text: str, aura_text: str, speaking: bool = False):
        """Populate and reveal the card."""
        self._dismiss_timer.stop()
        clean_resp = re.sub(r"[^\x00-\x7F\u00C0-\u024F\u2019\u2018\u2013\u2014]", "", aura_text).strip()
        if not clean_resp:
            clean_resp = aura_text

        self._you_lbl.setText(f"You:  {user_text}" if user_text else "")
        self._resp_lbl.setText(clean_resp)
        self._wave.set_state("speaking" if speaking else "thinking")

        self.setVisible(True)
        self.adjustSize()
        self._do_fade(1.0)

    def set_wave_state(self, state: str):
        self._wave.set_state(state)

    def dismiss(self, delay_ms: int = 0):
        if delay_ms > 0:
            self._dismiss_timer.start(delay_ms)
            return
        self._do_fade(0.0)
        QTimer.singleShot(240, lambda: self.setVisible(False))

    def _do_fade(self, target: float):
        self._fade.stop()
        self._fade.setStartValue(self._opacity_effect.opacity())
        self._fade.setEndValue(target)
        self._fade.start()

    def paintEvent(self, _):
        p = QPainter(self)
        set_aa(p)
        r = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(QRectF(r), 16, 16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(CARD_BG)
        p.drawPath(path)
        grad = QLinearGradient(QPointF(0, 0), QPointF(self.width(), 0))
        grad.setColorAt(0.0, NEON_CYAN)
        grad.setColorAt(0.5, NEON_BLUE)
        grad.setColorAt(1.0, NEON_PINK)
        p.setPen(QPen(QBrush(grad), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(int(r.left() + 16), int(r.top()),
                   int(r.right() - 16), int(r.top()))
        p.end()
class AuraLogoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 44)
        self._t = 0.0
        self._speaking = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

        self._particles = []
        self._seed_particles()

    def set_speaking(self, on: bool):
        self._speaking = bool(on)
        self.update()

    def _seed_particles(self):
        random.seed(42)
        self._particles.clear()
        for _ in range(22):
            ang = random.uniform(0, math.tau)
            rad = random.uniform(0.6, 0.95)
            spd = random.uniform(-0.002, 0.002)
            size = random.uniform(0.9, 1.6)
            alpha = random.randint(120, 200)
            self._particles.append([ang, rad, spd, size, alpha])

    def _tick(self):
        self._t += 0.016 * (1.7 if self._speaking else 1.0)
        for p in self._particles:
            p[0] = (p[0] + p[2]) % math.tau
            p[4] = max(80, min(220, p[4] + random.randint(-4, 4)))
        self.update()

    def paintEvent(self, e: QPaintEvent):
        p = QPainter(self)
        set_aa(p)
        w, h = self.width(), self.height()
        cx, cy = w/2.0, h/2.0
        R = min(w, h) * (0.5 if self._speaking else 0.46)
        halo = QRadialGradient(QPointF(cx, cy), R * 1.3)
        halo.setColorAt(0.0, QColor(0, 0, 0, 0))
        halo.setColorAt(0.9, QColor(135, 150, 255, 90 if self._speaking else 60))
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(halo))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), R * 1.25, R * 1.25)
        path = QPainterPath()
        steps = 120
        ring_width = max(2.2, R * 0.28)
        wave_amp = R * (0.11 if self._speaking else 0.08)
        wave_freq = 2.8
        for i in range(steps + 1):
            a = (i / steps) * math.tau
            r = R - ring_width / 2.0 + wave_amp * math.sin(wave_freq * a + self._t * 2.1)
            x = cx + r * math.cos(a)
            y = cy + r * math.sin(a)
            if i == 0: 
                path.moveTo(x, y)
            else: 
                path.lineTo(x, y)
        path.closeSubpath()

        grad = QLinearGradient(QPointF(0, 0), QPointF(w, h))
        grad.setColorAt(0.0, NEON_CYAN)
        grad.setColorAt(0.5, NEON_BLUE)
        grad.setColorAt(1.0, NEON_PINK)
        p.setPen(QPen(QBrush(grad), ring_width))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        for ang, rad, spd, size, alpha in self._particles:
            r = R * rad + (2.0 if self._speaking else 1.0) * math.sin(self._t * 1.7 + ang * 2.0)
            x = cx + r * math.cos(ang)
            y = cy + r * math.sin(ang)
            a2 = min(255, alpha + (40 if self._speaking else 0))
            p.setBrush(QColor(200, 210, 255, a2))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(x, y), size, size)

        p.end()
class MicButton(QWidget):
    toggled = pyqtSignal(bool)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self.listening = False
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_listening(self, on: bool):
        self.listening = on
        self.update()

    def mousePressEvent(self, _):
        self.listening = not self.listening
        self.toggled.emit(self.listening)
        self.update()

    def _tick(self):
        if self.listening:
            self._t += 0.016
            self.update()

    def paintEvent(self, e: QPaintEvent):
        p = QPainter(self)
        set_aa(p)
        w, h = self.width(), self.height()
        cx, cy = w/2, h/2
        base = min(w, h) * 0.42

        if self.listening:
            for i in range(3):
                phase = (self._t * 1.6 + i * 0.35) % 1.0
                r_ring = base + phase * (base * 0.9)
                alpha_ring = int(90 * (1 - phase))
                p.setPen(QPen(QColor(120,150,255,alpha_ring), 1.2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(cx, cy), r_ring, r_ring)

        grad = QLinearGradient(QPointF(0,0), QPointF(w,h))
        grad.setColorAt(0.0, NEON_BLUE)
        grad.setColorAt(1.0, NEON_CYAN)

        mic_w = base * 0.9
        mic_h = base * 1.15
        path = QPainterPath()
        path.addRoundedRect(QRectF(cx-mic_w/2, cy-mic_h/2, mic_w, mic_h*0.8), mic_w/2, mic_w/2)
        path.addRect(QRectF(cx-mic_w/2, cy-mic_h/2 + mic_h*0.4, mic_w, mic_h*0.6))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(path)
        p.end()
class SendButton(QWidget):
    def __init__(self, on_click, parent=None):
        super().__init__(parent)
        self.setFixedSize(30, 30)
        self.hover = False
        self.press = False
        self.on_click = on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, _): 
        self.hover = True; self.update()
    def leaveEvent(self, _): 
        self.hover = False; self.press = False; self.update()
    def mousePressEvent(self, _): 
        self.press = True; self.update()
    def mouseReleaseEvent(self, e):
        if self.press and self.rect().contains(e.position().toPoint()):
            if self.on_click: 
                self.on_click()
        self.press = False; self.update()

    def paintEvent(self, e: QPaintEvent):
        p = QPainter(self)
        set_aa(p)
        w, h = self.width(), self.height()

        if self.hover or self.press:
            glow = QRadialGradient(QPointF(w*0.5,h*0.5), w*0.8)
            glow.setColorAt(0.0, QColor(NEON_BLUE).lighter(150))
            glow.setColorAt(1.0, QColor(0,0,0,0))
            p.setBrush(QBrush(glow))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(w*0.5,h*0.5), w*0.8, h*0.8)

        grad = QLinearGradient(QPointF(0,0), QPointF(w,h))
        grad.setColorAt(0.0, NEON_BLUE)
        grad.setColorAt(1.0, NEON_CYAN)
        p.setPen(QPen(QBrush(grad), 1.8))
        p.setBrush(Qt.BrushStyle.NoBrush)

        path = QPainterPath()
        path.moveTo(w*0.2, h*0.75)
        path.lineTo(w*0.8, h*0.5)
        path.lineTo(w*0.2, h*0.25)
        path.lineTo(w*0.35, h*0.5)
        path.closeSubpath()
        path.moveTo(w*0.8, h*0.5)
        path.lineTo(w*0.35, h*0.5)
        p.drawPath(path)
        p.end()
class VoiceThread(QThread):
    transcript = pyqtSignal(str)
    listening_state = pyqtSignal(bool)
    partial_transcript = pyqtSignal(str)  # New signal for real-time transcription
    capture_state = pyqtSignal(str)

    def __init__(self, model_path=None, parent=None):
        super().__init__(parent)
        self._running = True
        self._want_once = False
        self.debug = os.getenv("AURA_DEBUG", "0") == "1"

        self._recognizer = sr.Recognizer()
        self._recognizer.energy_threshold = int(
            os.getenv("AURA_ENERGY_THRESHOLD", "300")
        )
        self._recognizer.dynamic_energy_threshold = True
        self._recognizer.pause_threshold = float(
            os.getenv("AURA_PAUSE_THRESHOLD", "1.5")
        )
        self._recognizer.non_speaking_duration = float(
            os.getenv("AURA_NON_SPEAKING_DURATION", "0.8")
        )
        self._recognizer.phrase_threshold = float(os.getenv("AURA_PHRASE_THRESHOLD", "0.12"))
        self._recognizer.operation_timeout = None
        self.engine = "google"

        self._input_processor = None
        if InputProcessingModule is not None:
            try:
                self._input_processor = InputProcessingModule()
            except Exception:
                self._input_processor = None

    def _dprint(self, msg: str):
        if self.debug:
            print(msg)

    def stop(self):
        self._running = False

    def request_once(self, on: bool):
        self._want_once = bool(on)

    def run(self):
        try:
            try:
                from aura.mic_fix import MicrophoneFix
                source = MicrophoneFix(sample_rate=16000)
                self._dprint("[DEBUG] Using MicrophoneFix (PyAudio primary)")
            except Exception as _mic_err:
                self._dprint(f"[DEBUG] MicrophoneFix unavailable ({_mic_err}), using sr.Microphone inline")
                source = None   # handled in the capture block below

            self._dprint("[DEBUG] Voice recognition ready")

            while self._running:
                if not self._want_once:
                    self.msleep(50)
                    continue

                self.listening_state.emit(True)
                try:
                    from aura.mic_fix import _CAPTURE_ACTIVE
                    _CAPTURE_ACTIVE.set()
                except Exception:
                    pass
                try:
                    phrase_limit = float(os.getenv("AURA_PHRASE_LIMIT_SECONDS", "35.0") or "35.0")
                    listen_timeout = float(os.getenv("AURA_LISTEN_TIMEOUT_SECONDS", "8.0") or "8.0")
                    if self._input_processor is not None:
                        try:
                            cfg = self._input_processor.get_voice_capture_settings()
                            phrase_limit = float(cfg.get("phrase_time_limit", phrase_limit))
                            listen_timeout = float(cfg.get("listen_timeout", listen_timeout))
                        except Exception:
                            pass

                    if source is not None:
                        audio = source.listen(
                            self._recognizer,
                            timeout=listen_timeout,
                            phrase_time_limit=phrase_limit,
                        )
                    else:
                        mic_idx_raw = os.getenv("AURA_MIC_INDEX", "").strip()
                        mic_idx = int(mic_idx_raw) if mic_idx_raw else None
                        with sr.Microphone(device_index=mic_idx) as src:
                            self._recognizer.adjust_for_ambient_noise(src, duration=0.5)
                            audio = self._recognizer.listen(
                                src, timeout=listen_timeout, phrase_time_limit=phrase_limit
                            )
                except sr.WaitTimeoutError:
                    self._dprint("[DEBUG] Listen timeout — no speech detected")
                    self.capture_state.emit("no_speech")
                    self.listening_state.emit(False)
                    self._want_once = False
                    continue
                except Exception as e:
                    self._dprint(f"[DEBUG] Audio capture error: {e}")
                    self.capture_state.emit("mic_error")
                    self.listening_state.emit(False)
                    self._want_once = False
                    continue
                finally:
                    try:
                        from aura.mic_fix import _CAPTURE_ACTIVE
                        _CAPTURE_ACTIVE.clear()
                    except Exception:
                        pass

                self.listening_state.emit(False)
                self._want_once = False  # consume the one-shot flag
                text = None
                try:
                    self._dprint("[DEBUG] Google Speech Recognition...")
                    try:
                        text = self._recognizer.recognize_google(audio, language='en-US')
                        self._dprint(f"[DEBUG] Google recognized: '{text}'")
                    except sr.UnknownValueError:
                        self._dprint("[DEBUG] en-US failed, retrying with en-IN...")
                        try:
                            text = self._recognizer.recognize_google(audio, language='en-IN')
                            self._dprint(f"[DEBUG] Google (en-IN) recognized: '{text}'")
                        except sr.UnknownValueError:
                            self._dprint("[DEBUG] Both recognition attempts failed")
                            text = None
                        except sr.RequestError as e:
                            self._dprint(f"[DEBUG] Google en-IN request error: {e}")
                            text = None
                except sr.RequestError as e:
                    self._dprint(f"[DEBUG] Google request error: {e}")
                    self.capture_state.emit("service_error")
                    text = None
                except Exception as e:
                    self._dprint(f"[DEBUG] Recognition error: {e}")
                    self.capture_state.emit("recognition_error")
                    text = None

                self._want_once = False
                if text and len(text.strip()) > 0:
                    if self._input_processor is not None:
                        try:
                            text = self._input_processor.normalize_text(text, source="voice")
                        except Exception:
                            pass
                    self.transcript.emit(text)
                else:
                    self._dprint("[DEBUG] No text recognized")
                    self.capture_state.emit("no_speech")
        except Exception as e:
            print(f"Voice thread error: {e}")
            pass
class PillInput(QWidget):
    send_requested = pyqtSignal(str)
    voice_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(62)

        self.mic = MicButton(self)
        self.mic.toggled.connect(self._on_mic)

        self.edit = QLineEdit(self)
        self.edit.setPlaceholderText("Ask me anything - 'What time is it?', 'Open Chrome', etc.")
        self.edit.setFrame(False)
        self.edit.setStyleSheet("QLineEdit{border:0;background:transparent;color:white;font-size:16px;padding:2px;}")
        self.edit.returnPressed.connect(self._send_clicked)

        self.send = SendButton(self._send_clicked, self)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(18,12,18,12)
        lay.setSpacing(12)
        lay.addWidget(self.mic)
        lay.addWidget(self.edit, 1)
        lay.addWidget(self.send)

    def _on_mic(self, on: bool):
        self.set_listening(on)
        self.voice_toggled.emit(on)

    def set_listening(self, on: bool):
        self.mic.set_listening(on)
        ph = "Listening... Speak clearly!" if on else "Ask me anything - 'What time is it?', 'Open Chrome', etc."
        self.edit.setPlaceholderText(ph)

    def set_processing(self, on: bool):
        """Show 'Thinking...' state in the input field"""
        if on:
            self.edit.setPlaceholderText("AURA is thinking...")
            self.edit.setEnabled(False)
            self.send.setEnabled(False)
            self.mic.setEnabled(False)
            self.edit.setStyleSheet("QLineEdit{border:0;background:transparent;color:rgba(255,255,255,100);font-size:16px;font-style:italic;padding:2px;}")
        else:
            ph = "Ask me anything - 'What time is it?', 'Open Chrome', etc."
            self.edit.setPlaceholderText(ph)
            self.edit.setEnabled(True)
            self.send.setEnabled(True)
            self.mic.setEnabled(True)
            self.edit.setStyleSheet("QLineEdit{border:0;background:transparent;color:white;font-size:16px;padding:2px;}")
            self.edit.setFocus()

    def fill_from_voice_and_send(self, text):
        self.edit.setText(text)
        self._send_clicked()

    def _send_clicked(self):
        text = self.edit.text().strip()
        lowered = text.lower()
        if text.startswith("🎤"):
            text = text.lstrip("🎤").strip(" .")
            lowered = text.lower()

        blocked = [
            "processing speech",
            "processing with",
            "listening",
            "could not understand",
            "service error",
            "recognition failed",
        ]
        if any(marker in lowered for marker in blocked):
            text = ""

        if text:
            self.send_requested.emit(text)
        self.edit.clear()

    def paintEvent(self, e):
        p = QPainter(self)
        set_aa(p)
        r = self.rect().adjusted(1,1,-1,-1)
        rad = r.height()/1.8
        path = QPainterPath()
        path.addRoundedRect(QRectF(r), rad, rad)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(PILL_BG)
        p.drawPath(path)
        p.end()
class AuraPanel(QWidget):
    auto_enable_voice_signal = pyqtSignal()

    def __init__(self, parent=None, corner_radius=32, model_path=None, user_name="Guest", user_email="", user_role="user"):
        super().__init__(parent)
        self.corner_radius = corner_radius
        self.user_name = (user_name or "Guest").strip()
        self.user_email = (user_email or "").strip().lower()
        self.user_role = (user_role or "user").strip().lower()
        self.auto_enable_voice_signal.connect(self._auto_enable_voice)
        self._last_voice_cmd = ""
        self._last_voice_ts = 0.0
        self._next_voice_earliest_ts = 0.0
        self._pending_listen_prompt = False
        self._voice_feedback_ts = {}
        self._conversation_history = []  # [{role: ..., content: ...}, ...]
        self.logo = AuraLogoWidget(self)

        self.title = QLabel("AURA", self)
        self.title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.title.setStyleSheet("color:white;")

        self.subtitle = QLabel("Ready to assist", self)
        self.subtitle.setStyleSheet("color:gray; font-size:11px;")
        self.subtitle.hide()  # Hidden for minimal design

        hl = QVBoxLayout()
        hl.addWidget(self.title)
        hl.addWidget(self.subtitle)

        self.logout_btn = QPushButton("⎋", self)
        self.logout_btn.setFixedSize(30, 30)
        self.logout_btn.setToolTip("Logout")
        self.logout_btn.setStyleSheet(
            "QPushButton{ color: rgba(255,140,140,210); background: transparent; border: none; font: 700 16px 'Segoe UI'; }"
            "QPushButton:hover { color: rgb(255,90,90); }"
        )
        self.logout_btn.clicked.connect(self._logout)

        self.close_btn = QPushButton("✕", self)
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setStyleSheet(
            "QPushButton{ color: rgba(200,205,215,210); background: transparent; border: none; font: 700 16px 'Segoe UI'; }"
            "QPushButton:hover { color: rgb(240,244,250); }"
        )
        self.close_btn.clicked.connect(lambda: self.window().close())

        header = QHBoxLayout()
        header.addWidget(self.logo)
        header.addLayout(hl)
        header.addStretch()
        header.addWidget(self.logout_btn)
        header.addWidget(self.close_btn)
        self.status_bar = StatusBar(self)
        self.pill = PillInput(self)
        self.pill.setFixedHeight(66)
        self.pill.send_requested.connect(self._handle_text_command)
        self.pill.voice_toggled.connect(self._toggle_voice)
        self.chat = QListWidget(self)
        self.chat.setObjectName("AuraChat")
        self.chat.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.chat.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chat.setSpacing(2)
        self.chat.setStyleSheet(
            "QListWidget{"
            "background: rgba(11, 15, 26, 235);"
            "color:#EAF1FF;"
            "border:1px solid rgba(116,168,255,45);"
            "border-radius:16px;"
            "font-size:17px;"
            "padding:10px;"
            "}"
            "QListWidget::item{border:0; margin:0; padding:0;}"
            "QScrollBar:vertical{"
            "background: transparent; width: 9px; margin: 4px 2px 4px 0;"
            "}"
            "QScrollBar::handle:vertical{"
            "background: rgba(120, 180, 255, 138); border-radius: 4px; min-height: 24px;"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical{height:0;}"
        )
        self._chat_hidden_height = 0
        self._chat_min_height = 86
        self.chat.setMinimumHeight(self._chat_min_height)
        screen = QApplication.primaryScreen()
        self._chat_max_height = 320
        if screen is not None:
            max_h = int(screen.availableGeometry().height() * 0.50)
            self._chat_max_height = max(260, min(560, max_h))
        self.chat.setMaximumHeight(self._chat_max_height)
        self.chat.setFixedHeight(self._chat_hidden_height)
        self.chat.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.chat.hide()

        self._chat_auto_hide_ms = 12000
        self._chat_timer = QTimer(self)
        self._chat_timer.setSingleShot(True)
        self._chat_timer.timeout.connect(self._hide_chat_panel)

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 20, 26, 20)
        root.setSpacing(10)
        root.addLayout(header)
        root.addWidget(self.status_bar)
        root.addWidget(self.pill)
        root.addWidget(self.chat)
        root.addStretch(1)
        self._response_card = ResponseCard(self)
        self._response_card.hide()
        self._popup_response_enabled = False
        self.enhanced_engine = get_engine()
        try:
            if hasattr(self.enhanced_engine, "set_active_user"):
                self.enhanced_engine.set_active_user(self.user_email, self.user_role, self.user_name)
        except Exception:
            pass
        self.voice_assistant_enabled = os.getenv("AURA_CONTINUOUS_VOICE", "0") == "1"
        self.voice = VoiceThread(model_path=None, parent=self)
        self.voice.listening_state.connect(self._on_listening)
        self.voice.transcript.connect(self._on_voice_text)
        self.voice.partial_transcript.connect(self._on_partial_voice_text)
        self.voice.capture_state.connect(self._on_capture_state)
        self.voice.start()
        if self.voice_assistant_enabled:
            QTimer.singleShot(450, self._auto_enable_voice)
        self._speak_anim_timer = QTimer(self)
        self._speak_anim_timer.timeout.connect(self._poll_speaking_state)
        self._speak_anim_timer.start(80)
    def _logout(self):
        """Stop voice thread, clear auto-login and show login window again."""
        try:
            if hasattr(self, "voice") and self.voice.isRunning():
                self.voice.stop()
                self.voice.wait(500)
        except Exception:
            pass
        from aura_login import AuraLoginWindow, user_memory
        user_memory.clear_user()

        win = self.window()
        if win is not None:
            win.close()
        self.login_window = AuraLoginWindow()
        self.login_window.show()

    def _bring_to_front(self):
        win = self.window()
        if win is not None:
            win.showNormal()
            win.raise_()
            win.activateWindow()
    def _toggle_voice(self, on: bool):
        if on:
            self._pending_listen_prompt = True
            self.voice.request_once(on)
        self.pill.set_listening(on)

    def listen_command(self):
        """Public hook used by wake-word trigger to start listening once."""
        self._toggle_voice(True)

    def _on_listening(self, is_on: bool):
        self.pill.set_listening(is_on)
        if is_on:
            self.status_bar.set_state("listening")
            if self._pending_listen_prompt:
                self._pending_listen_prompt = False
                if os.getenv("AURA_LISTEN_PROMPT_TTS", "0") == "1":
                    self._speak_status("listening", "I'm listening.", cooldown=2.5)
        else:
            if self.status_bar._state == "listening":
                self.status_bar.set_state("idle")

    def _on_capture_state(self, state: str):
        if state == "no_speech":
            self.status_bar.set_state("idle")
        elif state == "service_error":
            self.status_bar.set_state("idle")
        elif state == "mic_error":
            self.status_bar.set_state("idle")
            self._speak_status("mic_error", "Microphone unavailable.", cooldown=30.0)
        elif state == "recognition_error":
            self.status_bar.set_state("idle")

    def _speak_status(self, key: str, message: str, cooldown: float = 4.0):
        now = time.monotonic()
        last_ts = self._voice_feedback_ts.get(key, 0.0)
        if (now - last_ts) < cooldown:
            return
        self._voice_feedback_ts[key] = now
        self._speak_async(message)

    def _speak_async(self, message: str):
        if not message:
            return
        try:
            from aura.voice import speak
            import threading

            threading.Thread(
                target=lambda: speak(message, lang="auto", async_=False),
                daemon=True,
            ).start()
        except Exception as e:
            print(f"TTS error: {e}")

    def _speak_response(
        self,
        message: str,
        resume_voice: bool = False,
        user_command: str = "",
        from_voice: bool = False,
    ):
        if not message:
            self.status_bar.set_state("idle")
            if self._popup_response_enabled:
                self._response_card.dismiss(delay_ms=1200)
            if resume_voice:
                QTimer.singleShot(0, self._auto_enable_voice)
            return

        try:
            from aura.voice import speak_with_pauses, speak
            import threading
            self.status_bar.set_state("speaking")
            if self._popup_response_enabled:
                self._response_card.set_wave_state("speaking")

            speak_user_cmd = os.getenv("AURA_SPEAK_USER_COMMAND", "1") == "1"
            speak_typed_cmd = os.getenv("AURA_SPEAK_TYPED_COMMAND", "0") == "1"
            should_echo_user = bool(user_command) and speak_user_cmd and (from_voice or speak_typed_cmd)

            def worker():
                try:
                    if should_echo_user:
                        speak_with_pauses(f"You said: {user_command}.")
                    speak_with_pauses(message)
                except Exception as e:
                    print(f"TTS error: {e}")
                    try:
                        speak(message, lang="auto", async_=False)
                    except Exception as e2:
                        print(f"TTS fallback error: {e2}")
                finally:
                    try:
                        self.auto_enable_voice_signal.emit()  # also triggers idle state
                    except RuntimeError:
                        pass

            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            print(f"TTS error: {e}")
            self.status_bar.set_state("idle")
            if self._popup_response_enabled:
                self._response_card.dismiss(delay_ms=2000)
            if resume_voice:
                QTimer.singleShot(0, self._auto_enable_voice)

    def _on_voice_text(self, text: str):
        cleaned = (text or "").strip()
        if not cleaned:
            return
        lowered = cleaned.lower()
        noise_markers = [
            "processing speech",
            "processing with",
            "listening",
            "could not understand",
            "service error",
            "recognition failed",
        ]
        if any(marker in lowered for marker in noise_markers):
            return
        normalized = self._preprocess_command(cleaned)
        now_ts = time.monotonic()
        if normalized == self._last_voice_cmd and (now_ts - self._last_voice_ts) < 8.0:
            return
        words = normalized.split()
        if len(words) == 1:
            one = words[0]
            if one in {"uh", "um", "hmm", "huh", "ah", "hey", "hi", "hello"}:
                return
            if one in {"chrome", "notepad", "calculator", "spotify", "youtube"}:
                cleaned = f"open {one}"
            else:
                self.respond(
                    f"I heard '{one}'. Please say a full command, for example: open chrome or search for dogs.",
                    user_text=cleaned,
                    resume_voice=bool(self.voice_assistant_enabled),
                    mode="SYSTEM",
                )
                return

        self._last_voice_cmd = normalized
        self._last_voice_ts = now_ts

        self._handle_text_command(cleaned, from_voice=True)
        
    def _on_partial_voice_text(self, partial_text: str):
        """Handle partial voice transcription for real-time display"""
        pt = (partial_text or "").strip()
        if not pt:
            return
        low = pt.lower()
        hidden_markers = [
            "processing",
            "listening",
            "could not understand",
            "service error",
            "recognition failed",
        ]
        if pt.startswith("🎤") or any(marker in low for marker in hidden_markers):
            return
        current_text = self.pill.edit.text().strip()
        if self.pill.edit.hasFocus() and current_text and not current_text.startswith("🎤"):
            return
    def _poll_speaking_state(self):
        speaking = voice_is_speaking()
        self.logo.set_speaking(speaking)
        if speaking:
            if self.status_bar._state not in ("speaking",):
                self.status_bar.set_state("speaking")
                if self._popup_response_enabled:
                    self._response_card.set_wave_state("speaking")
    def _toggle_chat(self):
        self._set_chat_visible(not self.chat.isVisible())

    def classify_command(self, command: str) -> str:
        """Classify command as SYSTEM or CHAT for Bixby-style routing."""
        text = (command or "").lower().strip()
        if not text:
            return "CHAT"
        email_flow_patterns = (
            r"\b(send|compose|write)\b.*\b(mail|email|emaill)\b",
            r"^send\s+a\s*(ma|mai|mail|emaill)?$",
            r"^send\s+ma$",
            r"^yes$",
            r"^leave$",
        )
        if any(re.search(p, text) for p in email_flow_patterns):
            return "CHAT"

        chat_patterns = (
            r"\b(joke|riddle|story|poem|quote|funny|cheer me up)\b",
            r"\b(question|explain|define|why|how|what is|what are|meaning|difference)\b",
            r"\b(chat|talk|conversation|tell me)\b",
            r"\b(mail|email|emaill|compose|write)\b",
        )
        if any(re.search(p, text) for p in chat_patterns):
            return "CHAT"
        if re.search(r"^(open|launch|start|turn on|turn off|close|shutdown|restart|play|pause)\b", text):
            return "SYSTEM"
        if re.search(r"\b(volume|mute|unmute|screenshot|brightness|wifi|bluetooth)\b", text):
            return "SYSTEM"

        return "CHAT"

    def _set_chat_visible(self, visible: bool):
        if visible:
            self.chat.setVisible(True)
            if self.chat.count() <= 0:
                self.chat.setFixedHeight(self._chat_min_height)
            self._adjust_chat_height()
        else:
            self.chat.setFixedHeight(self._chat_hidden_height)
            self.chat.setVisible(False)
        win = self.window()
        if win is not None and hasattr(win, "set_chat_mode"):
            try:
                win.set_chat_mode(visible)
            except Exception:
                pass

    def _adjust_chat_height(self):
        """Grow/shrink chat panel to match message content up to max height."""
        try:
            count = self.chat.count()
            if count <= 0:
                self.chat.setFixedHeight(self._chat_min_height)
                win = self.window()
                if win is not None and hasattr(win, "set_chat_content_height"):
                    try:
                        win.set_chat_content_height(self._chat_min_height)
                    except Exception:
                        pass
                return
            content_h = 0
            for i in range(count):
                row_h = self.chat.sizeHintForRow(i)
                content_h += max(52, row_h)
            content_h += 28
            target = max(self._chat_min_height, min(self._chat_max_height, content_h))
            self.chat.setFixedHeight(target)
            win = self.window()
            if win is not None and hasattr(win, "set_chat_content_height"):
                try:
                    win.set_chat_content_height(target)
                except Exception:
                    pass
        except Exception:
            pass

    def _show_chat_panel(self):
        self._set_chat_visible(True)
        self._schedule_chat_auto_hide()

    def _hide_chat_panel(self):
        self._chat_timer.stop()
        self.chat.setFixedHeight(self._chat_hidden_height)
        self._set_chat_visible(False)

    def _schedule_chat_auto_hide(self):
        self._chat_timer.start(self._chat_auto_hide_ms)

    def add_user_message(self, text: str):
        self._append_chat("user", text)
        if self.chat.isVisible():
            self._schedule_chat_auto_hide()

    def add_assistant_message(self, text: str):
        self._show_chat_panel()
        self._append_chat("assistant", text)
        self._schedule_chat_auto_hide()

    def _append_chat(self, who, msg):
        text = str(msg or "")
        is_user = str(who).lower() in {"you", "you (voice)", "user"}

        row = QWidget()
        row_lay = QHBoxLayout(row)
        row_lay.setContentsMargins(2, 3, 2, 3)
        row_lay.setSpacing(0)

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble.setMaximumWidth(560)
        if is_user:
            bubble.setStyleSheet(
                "QLabel{"
                "background:#2E93FF; color:#FFFFFF;"
                "padding:10px 14px; border-radius:15px;"
                "font-size:18px; line-height:1.40;"
                "}"
            )
            row_lay.addStretch(1)
            row_lay.addWidget(bubble, 0, Qt.AlignmentFlag.AlignRight)
        else:
            bubble.setStyleSheet(
                "QLabel{"
                "background:#1D2638; color:#EAF1FF;"
                "padding:10px 14px; border-radius:15px;"
                "font-size:18px; line-height:1.40;"
                "border:1px solid rgba(137,173,255,0.24);"
                "}"
            )
            row_lay.addWidget(bubble, 0, Qt.AlignmentFlag.AlignLeft)
            row_lay.addStretch(1)

        item = QListWidgetItem(self.chat)
        self.chat.addItem(item)
        self.chat.setItemWidget(item, row)
        item.setSizeHint(row.sizeHint())

        self._adjust_chat_height()
        self.chat.scrollToBottom()

    def respond(
        self,
        text: str,
        user_text: str = "",
        resume_voice: bool = True,
        mode: str = "SYSTEM",
        from_voice: bool = False,
    ):
        """Single response path for all commands: main status/card or chat + voice."""
        final = (text or "").strip() or "I am here. Please try that once more."
        route = (mode or "SYSTEM").upper()
        if route == "CHAT":
            self.add_assistant_message(final)
        else:
            self._hide_chat_panel()
        if user_text:
            self._show_response_card(user_text, final, speaking=True)
        self._speak_response(
            final,
            resume_voice=resume_voice,
            user_command=user_text,
            from_voice=from_voice,
        )
        print(f"Aura: {final}")
    def _handle_text_command(self, text: str, from_voice=False):
        if not text:
            return

        command_mode = self.classify_command(text)
        if command_mode == "CHAT":
            self.add_user_message(text)
        else:
            self._hide_chat_panel()
        if from_voice:
            if self.pill.edit.text().strip().startswith("🎤"):
                self.pill.edit.clear()
            self.pill.edit.setStyleSheet("")
        lowered_text = text.lower().strip()
        exit_phrases = ("exit", "goodbye", "bye", "quit", "close aura", "stop aura",
                        "shut down", "good bye", "see you", "farewell")
        if any(lowered_text == p or lowered_text.startswith(p + " ") for p in exit_phrases):
            farewell = "Goodbye! Have a great day. I'm always here when you need me."
            self.respond(farewell, user_text=text, resume_voice=False, mode="SYSTEM", from_voice=from_voice)
            return
        self.status_bar.set_state("thinking")
        self.pill.set_processing(True)
        self._show_response_card(text, "…", speaking=False)
        QApplication.processEvents()

        processed_text = text.lower().strip()
        try:
            processed_text = self._preprocess_command(text)
            resp = self.enhanced_engine.execute(processed_text, min_confidence=0.15)
            resp = self._make_response_conversational(resp, text)
        except Exception as e:
            resp = self._get_helpful_error_response(str(e))
            processed_text = text.lower().strip()
        finally:
            self.pill.set_processing(False)
        if self._is_weak_response(resp):
            ai_resp = self._call_ai_response(text)
            if ai_resp:
                resp = ai_resp
        self._conversation_history.append({"role": "user", "content": text})
        self._conversation_history.append({"role": "assistant", "content": resp})
        if len(self._conversation_history) > 20:
            self._conversation_history = self._conversation_history[-20:]

        is_launch = processed_text.startswith(("open ", "launch ", "start ", "run "))
        speak_text = self._build_voice_ack(processed_text, resp) if is_launch else resp

        rearm_delay = 2.2 if is_launch else 0.0
        if rearm_delay > 0:
            self._next_voice_earliest_ts = time.monotonic() + rearm_delay
        self.respond(
            speak_text,
            user_text=text,
            resume_voice=True,  # Always speak the response for text commands
            mode=command_mode,
            from_voice=from_voice,
        )
        try:
            win = self.window()
            uid = getattr(win, "user_id", None)
            if uid is not None:
                save_history(uid, text, resp, "voice" if from_voice else "text")
        except Exception:
            pass
    def _show_response_card(self, user_text: str, aura_text: str, speaking: bool = False):
        if not self._popup_response_enabled:
            return
        card = self._response_card
        card_h = 96
        card_w = min(self.width() - 52, 360)
        card_x = 26
        card_y = max(8, self.height() - card_h - 8)
        card.setGeometry(card_x, card_y, card_w, card_h)
        card.raise_()
        card.show_response(user_text, aura_text, speaking)
    
    def _auto_enable_voice(self):
        """Auto-enable voice (Siri/Alexa continuous-listen cycle)"""
        try:
            if self._popup_response_enabled:
                self._response_card.dismiss(delay_ms=2200)
            self.status_bar.set_state("idle")

            if self.voice_assistant_enabled and self.voice:
                now_ts = time.monotonic()
                if now_ts < self._next_voice_earliest_ts:
                    delay_ms = int((self._next_voice_earliest_ts - now_ts) * 1000)
                    QTimer.singleShot(max(60, delay_ms), self._auto_enable_voice)
                    return
                QTimer.singleShot(180, lambda: self.voice.request_once(True))
                self.pill.set_listening(True)
        except Exception as e:
            print(f"Auto-enable voice error: {e}")
    
    def _preprocess_command(self, text: str) -> str:
        """Preprocess commands for better understanding"""
        text = text.lower().strip()
        replacements = {
            "what's": "what is",
            "can't": "cannot", 
            "won't": "will not",
            "i'd like": "i want",
            "could you": "please",
            "would you": "please",
            "turn on": "open",
            "turn off": "close",
            "opening ": "open ",
            "play some": "play",
            "tell me about": "search for",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)
        text = re.sub(r"\b(.+?)\s+\1\b", r"\1", text).strip()
        if " open " in text and text.count("open") > 1:
            text = text[text.rfind("open"):].strip()

        return text

    def _make_response_conversational(self, response: str, original_command: str) -> str:
        """Make responses more conversational and Alexa-like"""
        if not response or "Error" in response:
            return response
        greeting_commands = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]
        if any(greeting in original_command.lower() for greeting in greeting_commands):
            responses = [
                f"Hi there! {response}",
                f"Hello! {response}", 
                f"Hey! {response}",
                f"Good to see you! {response}"
            ]
            import random
            return random.choice(responses)
        request_words = ["please", "can you", "could you", "would you"]
        if any(word in original_command.lower() for word in request_words):
            acknowledgments = ["Sure!", "Of course!", "Absolutely!", "Right away!", "No problem!"]
            import random
            return f"{random.choice(acknowledgments)} {response}"
            
        return response

    def _build_voice_ack(self, processed_text: str, default_response: str) -> str:
        if not processed_text:
            return default_response
        m = re.match(r"^(open|launch|start|run)\s+(.+)$", processed_text.strip(), re.IGNORECASE)
        if not m:
            return default_response
        target = (m.group(2) or "").strip()
        if not target:
            return default_response
        cleaned_target = re.sub(r"\s+", " ", target)
        return f"Opening {cleaned_target}."
    
    def _get_helpful_error_response(self, error: str) -> str:
        """Provide helpful error responses"""
        helpful_responses = [
            "I'm sorry, I didn't quite catch that. Could you try rephrasing?",
            "Hmm, I'm not sure about that one. Can you be more specific?",
            "I'm having trouble with that request. Could you try a different way?",
            "Sorry, that's a bit tricky for me right now. Try asking differently?"
        ]
        import random
        return random.choice(helpful_responses)
    def _call_ai_response(self, user_text: str) -> "str | None":
        """Call configured AI providers (OpenAI/Gemini) for weak responses."""
        try:
            system = (
                "You are Aura, a helpful voice assistant like Bixby or Alexa. "
                "Give concise, conversational answers in 1-3 sentences max. "
                "Do not use markdown, bullet points, or emojis."
            )
            return generate_ai_response(
                user_input=user_text,
                context=self._conversation_history[-8:],
                system_prompt=system,
            )
        except Exception as e:
            if os.getenv("AURA_DEBUG", "0") == "1":
                print(f"[AI] Error: {e}")
            return None

    def _is_weak_response(self, resp: str) -> bool:
        """Detect when the command engine returned a generic/unhelpful response."""
        if not resp:
            return True
        weak_phrases = (
            "i'm not sure", "i don't know", "i didn't understand",
            "not supported", "couldn't understand", "didn't catch",
            "try rephrasing", "more specific", "trouble with that",
            "bit tricky", "unknown command", "no pending",
            "i'm having trouble", "i am not sure",
            "i couldn't", "i can't help with that",
        )
        lower = resp.lower()
        return any(p in lower for p in weak_phrases)
    def paintEvent(self, e: QPaintEvent):
        p = QPainter(self)
        set_aa(p)
        r = self.rect().adjusted(1,1,-1,-1)
        path = QPainterPath()
        path.addRoundedRect(QRectF(r), self.corner_radius, self.corner_radius)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(BG_DARK)
        p.drawPath(path)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255,255,255,18), 1))
        p.drawPath(path)
        p.end()
class MainWindow(QWidget):
    def __init__(self, user_id=0, user_name="Guest", user_email="", user_role="user"):
        super().__init__()
        self.user_id = user_id
        self.user_name = user_name
        self.user_email = (user_email or "").strip().lower()
        self.user_role = (user_role or "user").strip().lower()
        self.corner_radius = 34
        self._compact_size = QSize(790, 190)
        self._chat_content_height = 230
        self._chat_size = QSize(790, self._compact_size.height() + self._chat_content_height)
        self._chat_mode = False

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(self._compact_size.width())
        self.setFixedHeight(self._compact_size.height())

        self.panel = AuraPanel(
            self,
            corner_radius=self.corner_radius,
            user_name=self.user_name,
            user_email=self.user_email,
            user_role=self.user_role,
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0)
        lay.addWidget(self.panel)

        self._drag = None
        self._apply_mask()

    def showEvent(self, e):
        self._position_bottom_sheet()

    def _position_bottom_sheet(self):
        scr = QApplication.primaryScreen().availableGeometry()
        x = scr.center().x() - self.width() // 2
        y = scr.bottom() - self.height() - 20
        self.move(x, y)

    def set_chat_mode(self, enabled: bool):
        enabled = bool(enabled)
        self._chat_mode = enabled
        if enabled:
            self._chat_size = QSize(self._compact_size.width(), self._compact_size.height() + self._chat_content_height)
        target = self._chat_size if enabled else self._compact_size
        self.setFixedHeight(target.height())
        self._apply_mask()
        self._position_bottom_sheet()

    def set_chat_content_height(self, chat_height: int):
        try:
            h = int(chat_height)
        except Exception:
            return
        self._chat_content_height = max(86, min(560, h))
        if self._chat_mode:
            self.set_chat_mode(True)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._apply_mask()

    def _apply_mask(self):
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, self.corner_radius, self.corner_radius)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag and (e.buttons() & Qt.MouseButton.LeftButton):
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def closeEvent(self, e):
        try:
            if hasattr(self.panel, "voice"):
                self.panel.voice.stop()
                self.panel.voice.wait(12000)
        except Exception:
            pass
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    app.setApplicationName("AURA Panel")
    app.setFont(QFont("Segoe UI", 10))
    w = MainWindow(0, "Guest")
    w.show()
    sys.exit(app.exec())

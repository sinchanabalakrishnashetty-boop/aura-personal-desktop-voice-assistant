"""
aura_login.py
Login + Registration UI for AURA (PyQt6) with Auto-Login Feature.
"""

import sys
import re
import json
import random
from pathlib import Path
from typing import Tuple
from datetime import datetime
from time import monotonic

from PyQt6.QtCore import Qt, QRectF, QTimer, QByteArray
from PyQt6.QtGui import QPainter, QColor, QFont, QPainterPath, QPixmap, QIcon, QRegion
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QGraphicsDropShadowEffect, QPushButton, QLineEdit, QSizePolicy,
    QSpacerItem, QDialog
)
class UserMemory:
    """Saves user login info for auto-login"""
    def __init__(self):
        self.memory_file = Path("user_memory.json")
   
    def save_user(self, email: str, password: str, user_id: int, user_name: str) -> bool:
        """Save user credentials"""
        try:
            data = {
                "email": email,
                "password_hash": hash_password(password),
                "user_id": user_id,
                "user_name": user_name,
                "last_login": str(datetime.now())
            }
            with open(self.memory_file, 'w') as f:
                json.dump(data, f)
            print("SUCCESS: User saved for auto-login!")
            return True
        except Exception as e:
            print(f"ERROR saving user: {e}")
            return False
   
    def get_saved_user(self) -> dict:
        """Get saved user credentials"""
        try:
            if self.memory_file.exists():
                with open(self.memory_file, 'r') as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    return None
                required = ["email", "user_id", "user_name"]
                if not all(key in data for key in required):
                    return None
                if not isinstance(data.get("email"), str):
                    return None
                if not isinstance(data.get("user_id"), int) or not isinstance(data.get("user_name"), str):
                    return None
                has_hash = isinstance(data.get("password_hash"), str) and bool(data.get("password_hash").strip())
                has_legacy_password = isinstance(data.get("password"), str) and bool(data.get("password").strip())
                if not (has_hash or has_legacy_password):
                    return None
                return data
            return None
        except Exception as e:
            print(f"ERROR reading user: {e}")
            return None
   
    def clear_user(self) -> bool:
        """Clear saved user (logout)"""
        try:
            if self.memory_file.exists():
                self.memory_file.unlink()
            print("SUCCESS: User cleared!")
            return True
        except Exception as e:
            print(f"ERROR clearing user: {e}")
            return False
user_memory = UserMemory()
try:
    from auth import (
        login_user,
        login_user_with_hash,
        get_user_role,
        register_user,
        reset_password,
        send_password_reset_otp,
        validate_email,
        validate_password,
        validate_name,
        hash_password,
    )
except Exception:
    try:
        from auth import login_user
    except Exception:
        def login_user(email, password):
            return False, "auth.login_user not available", None, None
    def register_user(name, email, password):
        return False, "register_user not implemented in auth.py"
    def reset_password(email, new_password):
        return False, "reset_password not implemented in auth.py"
    def login_user_with_hash(email, password_hash_value):
        return False, "login_user_with_hash not available", None, None
    def get_user_role(email):
        return "user"
    def hash_password(password):
        import hashlib
        return hashlib.sha256((password or "").encode()).hexdigest()
    def send_password_reset_otp(to_email, otp_code):
        return False, "Email sender is not configured."
    def validate_email(email):
        e = (email or "").strip()
        if not e:
            return False, "Email required.", e
        if not re.match(r"[^@]+@[^@]+\.[^@]+", e):
            return False, "Invalid email format.", e
        return True, "", e
    def validate_password(password):
        p = password or ""
        if len(p) < 8:
            return False, "Password must be at least 8 characters."
        return True, ""
    def validate_name(name):
        n = (name or "").strip()
        if len(n) < 2:
            return False, "Name must be at least 2 characters."
        return True, ""
try:
    from aura_panel import MainWindow, AuraLogoWidget
except Exception:
    from PyQt6.QtWidgets import QWidget
    class AuraLogoWidget(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setFixedSize(44, 44)
    class MainWindow(QWidget):
        def __init__(self, user_id: int = 0, user_name: str = "Guest"):
            super().__init__()
NEON_CYAN = QColor(90, 240, 255)
TEXT_WHITE = QColor(238, 242, 248)
BUTTON_WIDTH = 420
BUTTON_HEIGHT = 48
INPUT_WIDTH = BUTTON_WIDTH
INPUT_HEIGHT = 44
EYE_OUTLINE_SVG = b"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path fill='white' d='M12 5c-7 0-11 6-11 7s4 7 11 7 11-6 11-7-4-7-11-7zm0 12c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z'/></svg>"""
EYE_SLASH_OUTLINE_SVG = b"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path fill='white' d='M2 3l2 2 3.1 3.1C4.9 10.1 2.7 12 1 12c0 0 4 7 11 7 2.1 0 4.1-.4 6-1.2L19 19l2 2 1-1L3 2 2 3zM12 7c1.6 0 3 .7 4 1.8L9.8 15C8.7 14 8 12.6 8 11c0-2.8 2.2-4 4-4z'/></svg>"""

def svg_to_icon(svg_bytes: bytes, size: int = 18) -> QIcon:
    renderer = QSvgRenderer(QByteArray(svg_bytes))
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    return QIcon(pix)

def set_aa(p: QPainter):
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
class RegistrationDialog(QDialog):
    """Modal registration dialog styled to match the login UI."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.corner_radius = 20
        self.setModal(True)
        self.setWindowTitle("Create account")
        self.setFixedSize(560, 480)
        self._input_w = 480
        self._input_h = INPUT_HEIGHT
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 18, 28, 18)
        root.setSpacing(10)
        logo_row = QHBoxLayout()
        logo_row.addStretch(1)
        self.logo = AuraLogoWidget(self)
        logo_row.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignCenter)
        logo_row.addStretch(1)
        root.addLayout(logo_row)

        title = QLabel("Create account")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.DemiBold))
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        subtitle = QLabel("Fill details to create your AURA account")
        subtitle.setFont(QFont("Segoe UI", 9))
        subtitle.setStyleSheet("color: rgba(200,210,230,200);")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subtitle)

        root.addSpacerItem(QSpacerItem(20, 6, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        self.name_field = QLineEdit()
        self.name_field.setPlaceholderText("Full name")
        self.name_field.setMaxLength(80)
        self._style_field(self.name_field)
        root.addWidget(self.name_field, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.email_field = QLineEdit()
        self.email_field.setPlaceholderText("you@example.com")
        self.email_field.setMaxLength(254)
        self._style_field(self.email_field)
        root.addWidget(self.email_field, alignment=Qt.AlignmentFlag.AlignHCenter)
        pwd_box = QHBoxLayout()
        pwd_box.setContentsMargins(0, 0, 0, 0)
        pwd_box.setSpacing(6)

        self.password_field = QLineEdit()
        self.password_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_field.setPlaceholderText("Password")
        self.password_field.setMaxLength(128)
        self._style_field(self.password_field, reserve_right=46)

        self.eye_btn = QPushButton()
        self.eye_btn.setCheckable(True)
        self.eye_btn.setFixedSize(38, self._input_h)
        self.eye_btn.setIcon(svg_to_icon(EYE_OUTLINE_SVG))
        self.eye_btn.setStyleSheet("border:0;background:transparent;")
        self.eye_btn.clicked.connect(self._toggle_eye)

        pwd_box.addWidget(self.password_field, 1)
        pwd_box.addWidget(self.eye_btn, 0)
        pwd_widget = QWidget()
        pwd_widget.setLayout(pwd_box)
        pwd_widget.setFixedWidth(self._input_w)
        root.addWidget(pwd_widget, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.confirm_field = QLineEdit()
        self.confirm_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_field.setPlaceholderText("Confirm password")
        self.confirm_field.setMaxLength(128)
        self._style_field(self.confirm_field)
        root.addWidget(self.confirm_field, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.msg_label = QLabel("")
        self.msg_label.setStyleSheet("color:#ff7070;font-size:13px;")
        self.msg_label.setVisible(False)
        self.msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.msg_label)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.register_btn = QPushButton("Create account")
        self.register_btn.setFixedSize(220, 44)
        self._style_button(self.register_btn)
        self.register_btn.clicked.connect(self._do_register)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(120, 44)
        cancel_btn.setStyleSheet(
            "QPushButton{background:transparent;color:rgba(200,210,230,200);"
            "border:1px solid rgba(255,255,255,8);border-radius:12px;}"
        )
        cancel_btn.clicked.connect(self.reject)

        btn_row.addStretch(1)
        btn_row.addWidget(self.register_btn)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        root.addSpacerItem(QSpacerItem(20, 12, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

    def _style_field(self, w: QLineEdit, reserve_right: int = 0):
        w.setFixedHeight(self._input_h)
        w.setFixedWidth(self._input_w)
        right_margin = reserve_right if reserve_right else 14
        w.setTextMargins(14, 0, right_margin, 0)
        w.setStyleSheet(f"""
            QLineEdit {{
                border:2px solid rgba(110,116,255,120);
                border-radius:{self._input_h//2}px;
                padding-left:14px;
                color:white;
                background-color:rgba(40,45,58,240);
                font-size:14px;
            }}
        """)

    def _style_button(self, btn: QPushButton):
        btn.setStyleSheet("""
            QPushButton {
                border:0;
                border-radius:12px;
                color:white;
                font-weight:600;
                background-color:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 rgba(110,116,255,255), stop:1 rgba(90,240,255,255));
            }
            QPushButton:hover { filter: brightness(1.05); }
        """)

    def _toggle_eye(self):
        if self.eye_btn.isChecked():
            self.password_field.setEchoMode(QLineEdit.EchoMode.Normal)
            self.confirm_field.setEchoMode(QLineEdit.EchoMode.Normal)
            self.eye_btn.setIcon(svg_to_icon(EYE_SLASH_OUTLINE_SVG))
        else:
            self.password_field.setEchoMode(QLineEdit.EchoMode.Password)
            self.confirm_field.setEchoMode(QLineEdit.EchoMode.Password)
            self.eye_btn.setIcon(svg_to_icon(EYE_OUTLINE_SVG))

    def _validate(self) -> Tuple[bool, str]:
        name = self.name_field.text().strip()
        email = self.email_field.text().strip()
        pwd = self.password_field.text()
        conf = self.confirm_field.text()
        ok, msg = validate_name(name)
        if not ok:
            return False, msg
        ok, msg, _ = validate_email(email)
        if not ok:
            return False, msg
        ok, msg = validate_password(pwd)
        if not ok:
            return False, msg
        if pwd != conf:
            return False, "Passwords do not match."
        return True, ""

    def _do_register(self):
        valid, msg = self._validate()
        if not valid:
            self.msg_label.setText(msg)
            self.msg_label.setStyleSheet("color:#ff7070;")
            self.msg_label.setVisible(True)
            return

        name = self.name_field.text().strip()
        email = self.email_field.text().strip()
        pwd = self.password_field.text().strip()

        try:
            ok, message = register_user(name, email, pwd)
        except Exception as e:
            ok, message = False, str(e)

        if not ok:
            self.msg_label.setText(message or "Registration failed")
            self.msg_label.setStyleSheet("color:#ff7070;")
            self.msg_label.setVisible(True)
            return

        self.msg_label.setText(message or "Registered successfully")
        self.msg_label.setStyleSheet("color:#80ff9a;")
        self.msg_label.setVisible(True)
        QTimer.singleShot(700, self.accept)

    def paintEvent(self, e):
        p = QPainter(self)
        set_aa(p)
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, self.corner_radius, self.corner_radius)
        p.setBrush(QColor(24, 28, 38))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)
        p.end()

class ForgotPasswordDialog(QDialog):
    """Modal dialog to reset account password by email."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.corner_radius = 20
        self.setModal(True)
        self.setWindowTitle("Forgot password")
        self.setFixedSize(560, 500)
        self._input_w = 480
        self._input_h = INPUT_HEIGHT
        self._otp_code = None
        self._otp_expires_at = 0.0
        self._otp_email = ""
        self._otp_attempts_left = 5
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 18, 28, 18)
        root.setSpacing(10)

        title = QLabel("Reset Password")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.DemiBold))
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        subtitle = QLabel("Step 1: Send OTP to your email. Step 2: Verify OTP and set new password")
        subtitle.setFont(QFont("Segoe UI", 9))
        subtitle.setStyleSheet("color: rgba(200,210,230,200);")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subtitle)

        root.addSpacerItem(QSpacerItem(20, 8, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

        self.email_field = QLineEdit()
        self.email_field.setPlaceholderText("you@example.com")
        self.email_field.setMaxLength(254)
        self._style_field(self.email_field)
        root.addWidget(self.email_field, alignment=Qt.AlignmentFlag.AlignHCenter)

        send_otp_btn = QPushButton("Send OTP")
        send_otp_btn.setFixedSize(180, 40)
        self._style_button(send_otp_btn)
        send_otp_btn.clicked.connect(self._send_otp)
        root.addWidget(send_otp_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.otp_field = QLineEdit()
        self.otp_field.setPlaceholderText("Enter 6-digit OTP")
        self.otp_field.setMaxLength(6)
        self._style_field(self.otp_field)
        root.addWidget(self.otp_field, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.new_password_field = QLineEdit()
        self.new_password_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password_field.setPlaceholderText("New password")
        self.new_password_field.setMaxLength(128)
        self._style_field(self.new_password_field)
        root.addWidget(self.new_password_field, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.confirm_field = QLineEdit()
        self.confirm_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_field.setPlaceholderText("Confirm new password")
        self.confirm_field.setMaxLength(128)
        self._style_field(self.confirm_field)
        root.addWidget(self.confirm_field, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.msg_label = QLabel("")
        self.msg_label.setStyleSheet("color:#ff7070;font-size:13px;")
        self.msg_label.setVisible(False)
        self.msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.msg_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        reset_btn = QPushButton("Reset password")
        reset_btn.setFixedSize(220, 44)
        self._style_button(reset_btn)
        reset_btn.clicked.connect(self._do_reset)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(120, 44)
        cancel_btn.setStyleSheet(
            "QPushButton{background:transparent;color:rgba(200,210,230,200);"
            "border:1px solid rgba(255,255,255,8);border-radius:12px;}"
        )
        cancel_btn.clicked.connect(self.reject)

        btn_row.addStretch(1)
        btn_row.addWidget(reset_btn)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        root.addSpacerItem(QSpacerItem(20, 12, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

    def _style_field(self, w: QLineEdit):
        w.setFixedHeight(self._input_h)
        w.setFixedWidth(self._input_w)
        w.setTextMargins(14, 0, 14, 0)
        w.setStyleSheet(f"""
            QLineEdit {{
                border:2px solid rgba(110,116,255,120);
                border-radius:{self._input_h//2}px;
                padding-left:14px;
                color:white;
                background-color:rgba(40,45,58,240);
                font-size:14px;
            }}
        """)

    def _style_button(self, btn: QPushButton):
        btn.setStyleSheet("""
            QPushButton {
                border:0;
                border-radius:12px;
                color:white;
                font-weight:600;
                background-color:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 rgba(110,116,255,255), stop:1 rgba(90,240,255,255));
            }
        """)

    def _do_reset(self):
        email = self.email_field.text().strip()
        otp = self.otp_field.text().strip()
        new_pwd = self.new_password_field.text()
        confirm = self.confirm_field.text()

        ok, msg, _ = validate_email(email)
        if not ok:
            self.msg_label.setText(msg)
            self.msg_label.setStyleSheet("color:#ff7070;")
            self.msg_label.setVisible(True)
            return

        if not self._otp_code:
            self.msg_label.setText("Please send OTP first.")
            self.msg_label.setStyleSheet("color:#ff7070;")
            self.msg_label.setVisible(True)
            return

        if email.lower() != self._otp_email.lower():
            self.msg_label.setText("OTP was sent to a different email. Please send OTP again.")
            self.msg_label.setStyleSheet("color:#ff7070;")
            self.msg_label.setVisible(True)
            return

        if monotonic() > self._otp_expires_at:
            self.msg_label.setText("OTP expired. Please request a new OTP.")
            self.msg_label.setStyleSheet("color:#ff7070;")
            self.msg_label.setVisible(True)
            return

        if otp != self._otp_code:
            self._otp_attempts_left -= 1
            if self._otp_attempts_left <= 0:
                self._otp_code = None
                self.msg_label.setText("OTP attempts exceeded. Please request a new OTP.")
            else:
                self.msg_label.setText(f"Invalid OTP. Attempts left: {self._otp_attempts_left}")
            self.msg_label.setStyleSheet("color:#ff7070;")
            self.msg_label.setVisible(True)
            return

        ok, msg = validate_password(new_pwd)
        if not ok:
            self.msg_label.setText(msg)
            self.msg_label.setStyleSheet("color:#ff7070;")
            self.msg_label.setVisible(True)
            return

        if new_pwd != confirm:
            self.msg_label.setText("Passwords do not match.")
            self.msg_label.setStyleSheet("color:#ff7070;")
            self.msg_label.setVisible(True)
            return

        ok, message = reset_password(email, new_pwd)
        if not ok:
            self.msg_label.setText(message or "Password reset failed.")
            self.msg_label.setStyleSheet("color:#ff7070;")
            self.msg_label.setVisible(True)
            return
        self._otp_code = None
        self._otp_expires_at = 0.0
        self._otp_attempts_left = 0
        self.msg_label.setText(message)
        self.msg_label.setStyleSheet("color:#80ff9a;")
        self.msg_label.setVisible(True)
        QTimer.singleShot(800, self.accept)

    def _send_otp(self):
        email = self.email_field.text().strip()
        ok, msg, email_n = validate_email(email)
        if not ok:
            self.msg_label.setText(msg)
            self.msg_label.setStyleSheet("color:#ff7070;")
            self.msg_label.setVisible(True)
            return

        otp_code = f"{random.randint(100000, 999999)}"
        sent, message = send_password_reset_otp(email_n, otp_code)
        if not sent:
            self.msg_label.setText(message or "Could not send OTP.")
            self.msg_label.setStyleSheet("color:#ff7070;")
            self.msg_label.setVisible(True)
            return

        self._otp_code = otp_code
        self._otp_email = email_n
        self._otp_expires_at = monotonic() + 600
        self._otp_attempts_left = 5
        self.msg_label.setText("OTP sent. Check your email. It expires in 10 minutes.")
        self.msg_label.setStyleSheet("color:#80ff9a;")
        self.msg_label.setVisible(True)

    def paintEvent(self, e):
        p = QPainter(self)
        set_aa(p)
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, self.corner_radius, self.corner_radius)
        p.setBrush(QColor(24, 28, 38))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)
        p.end()
class AuraLoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.corner_radius = 20
        self._drag_pos = None
        self.panel = None
        self._failed_login_count = 0
        self._lockout_until_ts = 0.0
        self.setup_window()
        self.build_ui()
        self.attempt_login = self.handle_login

    def setup_window(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.resize(560, 520)
        self.center_on_screen()
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(20, 30, 70, 140))
        self.setGraphicsEffect(shadow)

    def center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.center().x() - self.width() // 2,
                  screen.center().y() - self.height() // 2)

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(16)
        logo_row = QHBoxLayout()
        logo_row.addStretch(1)
        self.logo = AuraLogoWidget(self)
        logo_row.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignCenter)
        logo_row.addStretch(1)
        root.addLayout(logo_row)

        title = QLabel("AURA")
        title.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        title.setStyleSheet("color: white; letter-spacing: 1px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        subtitle = QLabel("Sign in to continue")
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setStyleSheet("color: rgba(200,210,230,200);")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subtitle)

        root.addSpacerItem(QSpacerItem(20, 8, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        self.email_field = QLineEdit()
        self.email_field.setPlaceholderText("you@example.com")
        self.email_field.setMaxLength(254)
        self._style_input(self.email_field)
        root.addWidget(self.email_field, alignment=Qt.AlignmentFlag.AlignHCenter)
        pwd_box = QHBoxLayout()
        pwd_box.setContentsMargins(0, 0, 0, 0)
        pwd_box.setSpacing(6)

        self.password_field = QLineEdit()
        self.password_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_field.setPlaceholderText("Password")
        self.password_field.setMaxLength(128)
        self._style_input(self.password_field, reserve_right=46)

        self.eye_btn = QPushButton()
        self.eye_btn.setCheckable(True)
        self.eye_btn.setFixedSize(38, INPUT_HEIGHT)
        self.eye_btn.setIcon(svg_to_icon(EYE_OUTLINE_SVG))
        self.eye_btn.setStyleSheet("border:0;background:transparent;")
        self.eye_btn.clicked.connect(self.toggle_eye)

        pwd_box.addWidget(self.password_field, 1)
        pwd_box.addWidget(self.eye_btn, 0)
        pwd_widget = QWidget()
        pwd_widget.setLayout(pwd_box)
        pwd_widget.setFixedWidth(INPUT_WIDTH)
        root.addWidget(pwd_widget, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color:#ff7070;font-size:13px;")
        self.error_label.setVisible(False)
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.error_label)
        self.login_btn = QPushButton("SIGN IN")
        self.login_btn.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
        self._style_button(self.login_btn)
        self.login_btn.clicked.connect(self.handle_login)
        root.addWidget(self.login_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        links = QHBoxLayout()
        self.register_btn = QPushButton("Create account")
        self.register_btn.setStyleSheet("background:transparent;color:rgba(200,210,230,200);border:0;text-decoration:underline;")
        self.register_btn.clicked.connect(self.open_registration)
       
        self.forgot_btn = QPushButton("Forgot?")
        self.forgot_btn.setStyleSheet("background:transparent;color:rgba(200,210,230,200);border:0;text-decoration:underline;")
        self.forgot_btn.clicked.connect(self.show_forgot_message)
       
        links.addStretch(1)
        links.addWidget(self.register_btn)
        links.addWidget(self.forgot_btn)
        links.addStretch(1)
        root.addLayout(links)

        root.addItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

    def _style_input(self, w: QLineEdit, reserve_right: int = 0):
        w.setFixedHeight(INPUT_HEIGHT)
        w.setFixedWidth(INPUT_WIDTH)
        right_margin = reserve_right if reserve_right else 14
        w.setTextMargins(14, 0, right_margin, 0)
        w.setStyleSheet(f"""
            QLineEdit {{
                border:2px solid rgba(110,116,255,120);
                border-radius:{INPUT_HEIGHT//2}px;
                padding-left:14px;
                color:white;
                background-color:rgba(40,45,58,240);
                font-size:15px;
            }}
        """)

    def _style_button(self, btn: QPushButton):
        btn.setStyleSheet("""
            QPushButton {
                border:0;
                border-radius:24px;
                color:white;
                font-weight:700;
                background-color:qlineargradient(
                    x1:0,y1:0,x2:1,y2:1,
                    stop:0 rgba(110,116,255,255),
                    stop:1 rgba(90,240,255,255)
                );
            }
        """)

    def toggle_eye(self):
        if self.eye_btn.isChecked():
            self.password_field.setEchoMode(QLineEdit.EchoMode.Normal)
            self.eye_btn.setIcon(svg_to_icon(EYE_SLASH_OUTLINE_SVG))
        else:
            self.password_field.setEchoMode(QLineEdit.EchoMode.Password)
            self.eye_btn.setIcon(svg_to_icon(EYE_OUTLINE_SVG))

    def open_registration(self):
        dlg = RegistrationDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.error_label.setStyleSheet("color:#80ff9a;font-size:13px;")
            self.error_label.setText("Registered — please sign in.")
            self.error_label.setVisible(True)

    def show_forgot_message(self):
        """Open forgot-password dialog and show result message."""
        dlg = ForgotPasswordDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.error_label.setStyleSheet("color:#80ff9a;font-size:13px;")
            self.error_label.setText("Password reset complete. Please sign in with your new password.")
            self.error_label.setVisible(True)
        else:
            self.error_label.setStyleSheet("color:rgba(200,210,230,200);font-size:13px;")
            self.error_label.setText("Password reset cancelled.")
            self.error_label.setVisible(True)

    def validate_inputs(self) -> Tuple[bool, str]:
        email = self.email_field.text().strip()
        pwd = self.password_field.text()
        ok, msg, _ = validate_email(email)
        if not ok:
            return False, msg
        if not pwd:
            return False, "Password cannot be empty."
        return True, ""

    def handle_login(self):
        now_ts = monotonic()
        if now_ts < self._lockout_until_ts:
            remaining = int(self._lockout_until_ts - now_ts) + 1
            return self.show_error(f"Too many failed attempts. Try again in {remaining}s.")

        valid, msg = self.validate_inputs()
        if not valid:
            return self.show_error(msg)

        email = self.email_field.text().strip()
        password = self.password_field.text().strip()

        try:
            ok, msg, user_id, user_name = login_user(email, password)
        except Exception as e:
            return self.show_error(f"Login error: {e}")

        if not ok:
            self._failed_login_count += 1
            if self._failed_login_count >= 5:
                self._lockout_until_ts = monotonic() + 30
                self._failed_login_count = 0
                return self.show_error("Too many failed attempts. Login is locked for 30s.")
            return self.show_error(msg or "Invalid credentials")
        self._failed_login_count = 0
        self._lockout_until_ts = 0.0

        user_role = get_user_role(email)
        user_memory.save_user(email, password, user_id, user_name)
       
        self.error_label.setStyleSheet("color:#80ff9a;font-size:13px;")
        self.error_label.setText("Login successful! Opening AURA…")
        self.error_label.setVisible(True)
        QTimer.singleShot(300, lambda: self.open_panel(user_id, user_name, email, user_role))

    def open_panel(self, user_id, user_name, user_email="", user_role="user"):
        """Open main panel and close login window"""
        if self.panel is not None:
            return  # Prevent duplicate
        
        self.panel = MainWindow(user_id, user_name, user_email=user_email, user_role=user_role)
        self.panel.show()
        self.close()  # Close login window

    def show_error(self, msg):
        self.error_label.setStyleSheet("color:#ff7070;font-size:13px;")
        self.error_label.setText(msg)
        self.error_label.setVisible(True)

    def resizeEvent(self, e):
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, self.corner_radius, self.corner_radius)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def paintEvent(self, e):
        p = QPainter(self)
        set_aa(p)
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, self.corner_radius, self.corner_radius)
        p.setBrush(QColor(24, 28, 38))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)
        p.end()
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("AURA Login")
    saved_user = user_memory.get_saved_user()
    
    if saved_user:
        email = saved_user.get("email", "")
        pwd_hash = (saved_user.get("password_hash") or "").strip()
        ok = False
        user_id = None
        user_name = None

        if pwd_hash:
            ok, _, user_id, user_name = login_user_with_hash(email, pwd_hash)
        else:
            legacy_pwd = saved_user.get("password", "")
            ok, _, user_id, user_name = login_user(email, legacy_pwd)
            if ok and legacy_pwd:
                user_memory.save_user(email, legacy_pwd, user_id, user_name)

        if ok:
            print(f"SUCCESS: Auto-login: Welcome back, {user_name}!")
            panel = MainWindow(
                user_id,
                user_name,
                user_email=email,
                user_role=get_user_role(email),
            )
            panel.show()
        else:
            user_memory.clear_user()
            print("INFO: Saved session invalid. Please login.")
            win = AuraLoginWindow()
            win.show()
    else:
        print("INFO: No saved user. Please login.")
        win = AuraLoginWindow()
        win.show()
    
    sys.exit(app.exec())
import argparse
import os
from dotenv import load_dotenv
load_dotenv()  # ensures .env values are available via os.getenv()

import sys
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication
from aura_login import AuraLoginWindow, user_memory
from aura_panel import MainWindow
from auth import login_user, login_user_with_hash, get_user_role
from aura.tray_app import run_tray
from aura import wake_word

class WakeBridge(QObject):
    triggered = pyqtSignal(str)

def detect_wake_word(text: str) -> bool:
    """Required API: detect wake phrase in text."""
    return wake_word.detect_wake_word(text, "hey aura")

def on_wake_trigger(controller: "Controller") -> None:
    """Required API: when wake word fires, open panel and start listening."""
    controller.wake_bridge.triggered.emit("hey aura")

def start_wake_listener(controller: "Controller"):
    """Required API: start low-CPU background wake listener."""
    keyword_path = os.getenv("AURA_WAKE_KEYWORD_PATH", "").strip() or None
    return wake_word.start_wake_word_listener(
        callback=lambda _phrase: on_wake_trigger(controller),
        wake_phrase="hey aura",
        keyword_path=keyword_path,
    )

class Controller:
    def __init__(self):
        self.wake_controller = None
        self.printed_vscode_msg = False  # Track if we've already printed the VS Code warning
        self.wake_bridge = WakeBridge()
        self.wake_bridge.triggered.connect(self.handle_wake_trigger)
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
                password = saved_user.get("password", "")
                ok, _, user_id, user_name = login_user(email, password)
                if ok and password:
                    user_memory.save_user(email, password, user_id, user_name)
            if ok:
                print(f"Auto-login: Welcome back, {user_name}!")
                self.window = MainWindow(
                    user_id,
                    user_name,
                    user_email=email,
                    user_role=get_user_role(email),
                )
                self.window.show()
                self._start_wake_listener_if_ready()
                return
            user_memory.clear_user()
            print("Saved session expired/invalid. Please login again.")
        print("No saved user. Please login.")
        self.window = AuraLoginWindow()
        self.window.show()

    def _start_wake_listener_if_ready(self):
        """Enable background wake-word listening when main panel is available."""
        if self.wake_controller is not None:
            return
        if not isinstance(self.window, MainWindow):
            return
        if os.getenv("AURA_DISABLE_WAKE", "0").strip() == "1":
            if not self.printed_vscode_msg:
                print("Wake listener disabled via AURA_DISABLE_WAKE=1.")
                self.printed_vscode_msg = True
            return

        try:
            self.wake_controller = start_wake_listener(self)
            print("Wake listener started. Say: Hey Aura")
        except Exception as e:
            print(f"Wake listener failed to start: {e}")

    def try_attach_main_window(self):
        """Detect MainWindow after login flow and attach wake listener once."""
        app = QApplication.instance()
        if app is None:
            return
        for w in app.topLevelWidgets():
            if isinstance(w, MainWindow):
                self.window = w
                self._start_wake_listener_if_ready()
                return

    def handle_wake_trigger(self, phrase: str = "hey aura"):
        """Open panel and start listening for command on wake trigger."""
        if not isinstance(self.window, MainWindow):
            return

        try:
            self.window.showNormal()
        except Exception:
            self.window.show()
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

        panel = getattr(self.window, "panel", None)
        if panel is not None:
            if hasattr(panel, "listen_command"):
                panel.listen_command()
            elif hasattr(panel, "_toggle_voice"):
                panel._toggle_voice(True)

    def stop_wake_listener(self):
        wc = self.wake_controller
        if wc is not None:
            try:
                wc.stop()
            except Exception:
                pass
        self.wake_controller = None

    def run(self):
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aura desktop launcher")
    parser.add_argument("--tray", action="store_true", help="Run with system tray controls")
    parser.add_argument("--minimized", action="store_true", help="Start minimized/hidden")
    args, _unknown = parser.parse_known_args()

    app = QApplication(sys.argv)
    controller = Controller()
    wake_attach_timer = QTimer()
    wake_attach_timer.setInterval(1000)
    wake_attach_timer.timeout.connect(controller.try_attach_main_window)
    wake_attach_timer.start()

    if args.minimized:
        controller.window.hide()

    if args.tray:
        run_tray(
            on_show=lambda: QTimer.singleShot(0, controller.window.show),
            on_hide=lambda: QTimer.singleShot(0, controller.window.hide),
            on_exit=lambda: QTimer.singleShot(0, app.quit),
        )

    app.aboutToQuit.connect(controller.stop_wake_listener)

    sys.exit(app.exec())
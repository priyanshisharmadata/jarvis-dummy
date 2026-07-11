"""
Jarvis - AI Voice Assistant for Windows
========================================
Entry point that initializes the Eel web UI and starts the assistant.

Run directly:
    python main.py

Or with hotword detection:
    python run.py
"""

import os
import sys
import time
import socket
import threading

import eel

# -- Ensure the project root is on sys.path so all imports resolve --
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# -- Reconfigure stdout for Unicode (fixes cp1252 crashes on Windows) --
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from backend.command import speak
from backend.feature import play_assistant_sound


def _find_free_port(start: int = 8000, max_attempts: int = 20) -> int:
    """Return the first available TCP port starting from *start*.

    Avoids the "port already in use" crash that happened in the original code
    when port 8000 was occupied.
    """
    for offset in range(max_attempts):
        port = start + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                return port
            except OSError:
                continue
    # If every port was taken, fall back to letting the OS pick one
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _open_browser(url: str, delay: float = 2.0) -> None:
    """Open the given URL in a Microsoft Edge app window after a short delay.

    Falls back to the system default browser when Edge is not installed.
    """
    time.sleep(delay)

    # Try Edge in app-mode first (cleaner UI for assistant)
    import shutil
    edge_path = shutil.which("msedge") or shutil.which("msedge.exe")
    if edge_path:
        try:
            os.system(f'start msedge.exe --app="{url}"')
            return
        except Exception:
            pass

    # Fall back to the system default browser
    import webbrowser
    webbrowser.open(url)


def start() -> None:
    """Initialise the Eel front-end and launch the assistant server."""
    frontend_dir = os.path.join(ROOT_DIR, "frontend")
    eel.init(frontend_dir)

    # ------------------------------------------------------------------
    # Exposed Python functions the front-end can call
    # ------------------------------------------------------------------

    @eel.expose
    def init() -> None:
        """Called by the front-end once it has finished loading.

        Steps through the loading sequence with proper delays so each
        animation has time to play before the next one appears.
        """
        print("DEBUG: init() called from frontend")
        eel.hideLoader()          # Loader → FaceAuth
        time.sleep(3.5)           # Let face-auth Lottie play
        eel.hideFaceAuth()        # FaceAuth → Success checkmark
        time.sleep(2.5)           # Let success animation play
        eel.hideFaceAuthSuccess() # Success → Hello greeting
        time.sleep(2.0)           # Let greeting animation play
        eel.hideStart()           # Show main UI (Jarvis hood)
        print("DEBUG: All hide functions called")
        # Greet the user now that the UI is ready
        speak("Welcome to Your Assistant")
        play_assistant_sound()

    @eel.expose
    def start_listening() -> None:
        """Greet the user and play the assistant startup sound."""
        speak("Welcome to Your Assistant")
        play_assistant_sound()

    # ------------------------------------------------------------------
    # Launch
    # ------------------------------------------------------------------
    port = _find_free_port()
    url = f"http://127.0.0.1:{port}/index.html"

    threading.Thread(target=_open_browser, args=(url,), daemon=True).start()

    print(f"Server starting on {url}")
    eel.start("index.html", mode=None, host="localhost", port=port, block=True)


if __name__ == "__main__":
    start()

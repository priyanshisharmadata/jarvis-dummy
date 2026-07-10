"""
Feature implementations for Jarvis.
====================================

App launching, YouTube playback, WhatsApp messaging/calling, hot-word
detection, contact lookup, and the AI chatbot fallback.

All file paths are relative to the project root so the code is portable
across machines — no hard-coded ``C:\\Users\\...`` paths.
"""

import os
import re
import struct
import subprocess
import sys
import time
import webbrowser
from urllib.parse import quote as url_quote

import eel
import pyautogui
import pywhatkit as kit

# -- Conditional imports ------------------------------------------------
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

try:
    import pvporcupine
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False

# -- PyAudio (real or wrapper) -------------------------------------------
try:
    import pyaudio
except ImportError:
    # Insert our sounddevice-based wrapper so 'import pyaudio' works
    from backend import pyaudio_wrapper  # noqa: F401
    import pyaudio

# -- Local imports -------------------------------------------------------
from backend.command import speak
from backend.config import ASSISTANT_NAME
from backend.helper import extract_yt_term, remove_words

# -- Database connection (relative path) ---------------------------------
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_ROOT, "jarvis.db")

import sqlite3


def _get_conn():
    """Return a fresh connection to the Jarvis database."""
    return sqlite3.connect(DB_PATH)


# ========================================================================
#  Sound
# ========================================================================

@eel.expose
def play_assistant_sound() -> None:
    """Play the start-up chime (``frontend/assets/audio/start_sound.mp3``).

    Uses Pygame if available; falls back to ``playsound``."""
    sound_file = os.path.join(
        _ROOT, "frontend", "assets", "audio", "start_sound.mp3"
    )

    if PYGAME_AVAILABLE:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(sound_file)
            pygame.mixer.music.play()
            return
        except Exception as exc:
            print(f"Pygame sound failed: {exc}")

    try:
        import playsound
        playsound.playsound(sound_file)
    except Exception as exc:
        print(f"Sound playback not available: {exc}")


# ========================================================================
#  Open / launch apps
# ========================================================================

def _find_app_in_system(app_name: str) -> str | None:
    """Search common Windows directories for an app whose name contains
    *app_name*.  Returns ``None`` if nothing is found."""
    import glob as gb

    username = os.environ.get("USERNAME", os.environ.get("USER", "*"))

    search_patterns = [
        # Start Menu
        f"C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\**\\*{app_name}*.lnk",
        f"C:\\Users\\{username}\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\**\\*{app_name}*.lnk",
        # Program Files
        f"C:\\Program Files\\**\\*{app_name}*.exe",
        f"C:\\Program Files (x86)\\**\\*{app_name}*.exe",
        # Local / Roaming AppData
        f"C:\\Users\\{username}\\AppData\\Local\\**\\*{app_name}*.exe",
        f"C:\\Users\\{username}\\AppData\\Roaming\\**\\*{app_name}*.exe",
    ]

    for pattern in search_patterns:
        try:
            matches = gb.glob(pattern, recursive=True)
            if matches:
                return matches[0]
        except Exception:
            pass

    return None


def openCommand(query: str) -> None:
    """Attempt to open an application or website matching *query*.

    Resolution order
    ----------------
    1. Exact match in **sys_command** table (local app paths).
    2. Exact match in **web_command** table (URLs).
    3. Windows ``start`` command (PATH-registered apps).
    4. Filesystem scan via ``_find_app_in_system``.
    5. Fuzzy ``LIKE`` match in **sys_command**.
    6. Give up with an apology.
    """
    # Strip trigger words (both English and Hindi)
    trigger_words = [
        "open", "kholo", "खोलो", "khol", "खोल", "chalu karo",
        "start", "launch", "run", "shuru karo", "चालू करो", "ओपन",
        ASSISTANT_NAME,
    ]
    for word in trigger_words:
        query = query.replace(word, "")

    app_name = query.strip()
    if not app_name:
        return

    conn = _get_conn()
    cursor = conn.cursor()

    try:
        # -- Step 1: DB exact match --------------------------------------
        cursor.execute(
            "SELECT path FROM sys_command WHERE LOWER(name) = LOWER(?)",
            (app_name,),
        )
        rows = cursor.fetchall()
        if rows:
            path = rows[0][0]
            print(f"[DB] Opening: {path}")
            speak(f"Opening {app_name}")
            _launch_path(path)
            return

        # -- Step 2: Website match ---------------------------------------
        cursor.execute(
            "SELECT url FROM web_command WHERE LOWER(name) = LOWER(?)",
            (app_name,),
        )
        rows = cursor.fetchall()
        if rows:
            url = rows[0][0]
            print(f"[WEB] Opening: {url}")
            speak(f"Opening {app_name}")
            webbrowser.open(url)
            return

        # -- Step 3: Windows 'start' command -----------------------------
        print(f"[SYS] Trying: start {app_name}")
        try:
            os.system(f'start {app_name}')
            speak(f"Opening {app_name}")
            return
        except Exception:
            pass

        # -- Step 4: Filesystem scan -------------------------------------
        print(f"[SEARCH] Looking for: {app_name}")
        found = _find_app_in_system(app_name)
        if found:
            print(f"[FOUND] {found}")
            speak(f"Opening {app_name}")
            _launch_path(found)
            # Cache for next time
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO sys_command (name, path) VALUES (?, ?)",
                    (app_name, found),
                )
                conn.commit()
            except Exception:
                pass
            return

        # -- Step 5: DB fuzzy match --------------------------------------
        cursor.execute(
            "SELECT name, path FROM sys_command WHERE LOWER(name) LIKE ?",
            (f"%{app_name}%",),
        )
        rows = cursor.fetchall()
        if rows:
            match_name, path = rows[0]
            print(f"[FUZZY] Found: {match_name} -> {path}")
            speak(f"Opening {match_name}")
            _launch_path(path)
            return

        # -- Step 6: Give up ---------------------------------------------
        speak(f"Sorry, couldn't find {app_name}. Try adding it to the database.")

    except Exception as exc:
        print(f"Error in openCommand: {exc}")
        traceback = sys.exc_info()[2]
        if traceback:
            import traceback as tb
            tb.print_exc()
        speak("Something went wrong")
    finally:
        conn.close()


def _launch_path(path: str) -> None:
    """Open the given file / shortcut, handling UWP apps gracefully."""
    try:
        if "shell:appsFolder" in path or "shell:AppsFolder" in path:
            os.system(f"start {path}")
        else:
            os.startfile(path)
    except Exception:
        os.system(f'start "" "{path}"')


# ========================================================================
#  YouTube
# ========================================================================

def PlayYoutube(query: str) -> None:
    """Search YouTube for the term extracted from *query* and play the top
    result."""
    search_term = extract_yt_term(query)
    speak(f"Playing {search_term} on YouTube")
    kit.playonyt(search_term)


# ========================================================================
#  Hot-word detection  (Win + J)
# ========================================================================

def hotword() -> None:
    """Continuously listen for the wake words "jarvis" or "alexa".

    When detected, presses **Win+J** to activate the assistant UI.  Requires
    ``pvporcupine`` and a working PyAudio installation."""
    if not PORCUPINE_AVAILABLE:
        print("Hotword detection not available (pvporcupine not installed)")
        return

    porcupine = None
    paud = None
    audio_stream = None

    try:
        porcupine = pvporcupine.create(keywords=["jarvis", "alexa"])
        paud = pyaudio.PyAudio()

        audio_stream = paud.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length,
        )

        while True:
            keyword_data = audio_stream.read(porcupine.frame_length)
            keyword_data = struct.unpack_from(
                "h" * porcupine.frame_length, keyword_data
            )
            keyword_index = porcupine.process(keyword_data)

            if keyword_index >= 0:
                print("hotword detected")
                pyautogui.keyDown("win")
                pyautogui.press("j")
                time.sleep(2)
                pyautogui.keyUp("win")

    except Exception as exc:
        print(f"Hotword error: {exc}")
    finally:
        if porcupine is not None:
            try:
                porcupine.delete()
            except Exception:
                pass
        if audio_stream is not None:
            try:
                audio_stream.close()
            except Exception:
                pass
        if paud is not None:
            try:
                paud.terminate()
            except Exception:
                pass


# ========================================================================
#  Contacts & WhatsApp
# ========================================================================

def findContact(query: str):
    """Search the contacts table for *query*.

    Returns
    -------
    tuple[str, str] | tuple[int, int]
        ``(phone_number, name)`` on success, ``(0, 0)`` on failure.
    """
    words_to_remove = [
        ASSISTANT_NAME, "make", "a", "to", "phone", "call",
        "send", "message", "whatsapp", "video",
    ]
    query = remove_words(query, words_to_remove).strip().lower()

    conn = _get_conn()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT Phone, name FROM contacts WHERE LOWER(name) LIKE ? OR LOWER(name) LIKE ?",
            (f"%{query}%", f"{query}%"),
        )
        results = cursor.fetchall()

        # FIX: original code indexed ``results[0][0]`` without checking
        # whether any rows were returned, causing an IndexError on miss.
        if not results:
            speak(f"{query} not found in contacts")
            return 0, 0

        mobile_number_str = str(results[0][0])

        if not mobile_number_str.startswith("+91"):
            mobile_number_str = "+91" + mobile_number_str

        contact_name = results[0][1] if len(results[0]) > 1 else query
        print(f"[CONTACT] {contact_name} -> {mobile_number_str}")
        return mobile_number_str, contact_name

    except Exception as exc:
        print(f"findContact error: {exc}")
        speak(f"{query} not found in contacts")
        return 0, 0
    finally:
        conn.close()


def whatsApp(Phone: str, message: str | None, flag: str, name: str) -> None:
    """Open WhatsApp Web and initiate a call, video call, or message.

    Parameters
    ----------
    Phone : str
        Phone number with country code (e.g. ``+91XXXXXXXXXX``).
    message : str or None
        Message body (only used when *flag* is ``"message"``).
    flag : str
        One of ``"message"``, ``"call"``, or ``"video call"``.
    name : str
        Contact display name (used for spoken confirmation).
    """
    if flag == "message":
        target_tab = 12
        jarvis_message = f"Message sent successfully to {name}"
        encoded = quote(message if message else "")
    elif flag == "call":
        target_tab = 7
        encoded = ""
        jarvis_message = f"Calling {name}"
    else:  # video call
        target_tab = 6
        encoded = ""
        jarvis_message = f"Starting video call with {name}"

    whatsapp_url = f"whatsapp://send?phone={Phone}&text={encoded}"
    full_command = f'start "" "{whatsapp_url}"'

    subprocess.run(full_command, shell=True)
    time.sleep(5)
    subprocess.run(full_command, shell=True)

    pyautogui.hotkey("ctrl", "f")

    for _ in range(1, target_tab):
        pyautogui.hotkey("tab")

    pyautogui.hotkey("enter")
    speak(jarvis_message)


# ========================================================================
#  AI Chatbot  (HuggingFace via hugchat)
# ========================================================================

def chatBot(query: str) -> str:
    """Fallback: send *query* to the HuggingFace chatbot.

    Requires a valid ``cookie.json`` file in the project's ``backend/``
    directory (exported from a logged-in HuggingChat session).

    Returns
    -------
    str
        The chatbot's response.
    """
    user_input = query.lower()

    try:
        from hugchat import hugchat

        # FIX: The original code used a hard-coded Windows path
        #      ``"backend\\cookie.json"``, which crashed on other machines
        #      or when the working directory was not the project root.
        cookie_path = os.path.join(_ROOT, "backend", "cookie.json")

        chatbot = hugchat.ChatBot(cookie_path=cookie_path)
        conv_id = chatbot.new_conversation()
        chatbot.change_conversation(conv_id)
        response = chatbot.chat(user_input)
        print(response)
        speak(response)
        return response

    except FileNotFoundError:
        speak(
            "Chatbot needs a HuggingFace cookie. "
            "Export your HuggingChat session to backend/cookie.json."
        )
        return "Chatbot unavailable — cookie.json missing"
    except Exception as exc:
        print(f"ChatBot error: {exc}")
        speak(
            "Chatbot feature needs HuggingFace login. "
            "Please add cookie.json file."
        )
        return "Chatbot unavailable — cookie.json missing"

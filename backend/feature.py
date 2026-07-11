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
from backend.command import speak, _say
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

    Uses Pygame if available; falls back to ``playsound``, then a
    self-closing Windows Media Player invocation."""
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
        except Exception:
            pass  # pygame failed silently, try next

    # playsound is broken on Python 3.13+ — skip without noise
    try:
        import playsound
        playsound.playsound(sound_file)
        return
    except Exception:
        pass

    # Last resort — use Windows Media Player with /play /close so it
    # exits automatically after playback instead of lingering minimized.
    try:
        os.system(
            f'start /min wmplayer "{sound_file}" /play /close'
        )
    except Exception:
        pass  # Sound is optional; never block the app for it


# ========================================================================
#  Open / launch apps
# ========================================================================

# Built-in mapping of common names → Windows launch commands.
# Covers UWP apps, system settings, and apps whose executable names don't
# match what users naturally say.  Add new entries here and they "just work".
_BUILTIN_APPS: dict[str, str] = {
    # --- UWP / Modern Windows apps ---
    "camera": "shell:appsFolder\\Microsoft.WindowsCamera_8wekyb3d8bbwe!App",
    "calculator": "shell:appsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App",
    "calc": "shell:appsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App",
    "clock": "shell:appsFolder\\Microsoft.WindowsAlarms_8wekyb3d8bbwe!App",
    "alarms": "shell:appsFolder\\Microsoft.WindowsAlarms_8wekyb3d8bbwe!App",
    "weather": "shell:appsFolder\\Microsoft.BingWeather_8wekyb3d8bbwe!App",
    "mausam": "shell:appsFolder\\Microsoft.BingWeather_8wekyb3d8bbwe!App",
    "maps": "shell:appsFolder\\Microsoft.WindowsMaps_8wekyb3d8bbwe!App",
    "photos": "shell:appsFolder\\Microsoft.Windows.Photos_8wekyb3d8bbwe!App",
    "mail": "shell:appsFolder\\microsoft.windowscommunicationsapps_8wekyb3d8bbwe!microsoft.windowslive.mail",
    "calendar": "shell:appsFolder\\microsoft.windowscommunicationsapps_8wekyb3d8bbwe!microsoft.windowslive.calendar",
    "store": "shell:appsFolder\\Microsoft.WindowsStore_8wekyb3d8bbwe!App",
    "microsoft store": "shell:appsFolder\\Microsoft.WindowsStore_8wekyb3d8bbwe!App",
    "paint": "shell:appsFolder\\Microsoft.Paint_8wekyb3d8bbwe!App",
    "notepad": "notepad.exe",
    "wordpad": "write.exe",
    # --- System settings pages ---
    "settings": "ms-settings:",
    "setting": "ms-settings:",
    "bluetooth": "ms-settings:bluetooth",
    "wifi": "ms-settings:network-wifi",
    "wi-fi": "ms-settings:network-wifi",
    "network": "ms-settings:network",
    "display": "ms-settings:display",
    "sound": "ms-settings:sound",
    "volume": "ms-settings:sound",
    "privacy": "ms-settings:privacy",
    "update": "ms-settings:windowsupdate",
    "windows update": "ms-settings:windowsupdate",
    "battery": "ms-settings:batterysaver",
    "storage": "ms-settings:storagesense",
    "accounts": "ms-settings:yourinfo",
    # --- Shell folders ---
    "downloads": "shell:Downloads",
    "documents": "shell:Personal",
    "desktop": "shell:Desktop",
    "pictures": "shell:My Pictures",
    "music": "shell:My Music",
    "videos": "shell:My Video",
    "recycle bin": "shell:RecycleBinFolder",
    "control panel": "control",
    "task manager": "taskmgr",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "file explorer": "explorer",
    "explorer": "explorer",
    "this pc": "explorer shell:MyComputerFolder",
    "my computer": "explorer shell:MyComputerFolder",
    # --- Common browser aliases ---
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "brave": "brave.exe",
    # --- Common apps ---
    "excel": "excel.exe",
    "microsoft excel": "excel.exe",
    "word": "winword.exe",
    "microsoft word": "winword.exe",
    "powerpoint": "powerpnt.exe",
    "microsoft powerpoint": "powerpnt.exe",
    "outlook": "outlook.exe",
    "onenote": "onenote.exe",
    "vs code": "code",
    "visual studio code": "code",
    "spotify": "spotify.exe",
    "vlc": "vlc.exe",
    "discord": "discord.exe",
    "zoom": "zoom.exe",
    "telegram": "telegram.exe",
    "slack": "slack.exe",
    "notion": "notion.exe",
    "whatsapp": "whatsapp.exe",
    "photoshop": "photoshop.exe",
    "illustrator": "illustrator.exe",
    "figma": "figma.exe",
    "epic games": "epicgameslauncher.exe",
    "steam": "steam.exe",
    # --- Hindi → English mappings ---
    "कैमरा": "shell:appsFolder\\Microsoft.WindowsCamera_8wekyb3d8bbwe!App",
    "कैलकुलेटर": "shell:appsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App",
    "कैलेंडर": "shell:appsFolder\\microsoft.windowscommunicationsapps_8wekyb3d8bbwe!microsoft.windowslive.calendar",
    "मौसम": "shell:appsFolder\\Microsoft.BingWeather_8wekyb3d8bbwe!App",
    "सेटिंग्स": "ms-settings:",
    "स्टोर": "shell:appsFolder\\Microsoft.WindowsStore_8wekyb3d8bbwe!App",
    "डाउनलोड": "shell:Downloads",
    "कंट्रोल पैनल": "control",
    "टास्क मैनेजर": "taskmgr",
    "फ़ाइल एक्सप्लोरर": "explorer",
    # --- Websites (open in default browser) ---
    "youtube": "https://www.youtube.com",
    "यूट्यूब": "https://www.youtube.com",
    "google": "https://www.google.com",
    "गूगल": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "facebook": "https://www.facebook.com",
    "फेसबुक": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "इंस्टाग्राम": "https://www.instagram.com",
    "whatsapp web": "https://web.whatsapp.com",
    "twitter": "https://www.twitter.com",
    "linkedin": "https://www.linkedin.com",
    "netflix": "https://www.netflix.com",
    "amazon": "https://www.amazon.in",
    "flipkart": "https://www.flipkart.com",
    "chatgpt": "https://chat.openai.com",
    "chat gpt": "https://chat.openai.com",
    "claude": "https://claude.ai",
    "gemini": "https://gemini.google.com",
    "deepseek": "https://chat.deepseek.com",
    "copilot": "https://copilot.microsoft.com",
    "wikipedia": "https://www.wikipedia.org",
    "stack overflow": "https://stackoverflow.com",
    "leetcode": "https://leetcode.com",
    "maps": "https://maps.google.com",
    "मेप": "https://maps.google.com",
    "translate": "https://translate.google.com",
    "news": "https://news.google.com",
    "google news": "https://news.google.com",
    "hotstar": "https://www.hotstar.com",
    "prime video": "https://www.primevideo.com",
    "spotify": "https://open.spotify.com",
    "reddit": "https://www.reddit.com",
    "pinterest": "https://www.pinterest.com",
    "snapchat": "https://www.snapchat.com",
    "quora": "https://www.quora.com",
    "discord": "https://discord.com/app",
    "twitch": "https://www.twitch.tv",
    "notion": "https://www.notion.so",
    "canva": "https://www.canva.com",
    "figma": "https://www.figma.com",
    "zomato": "https://www.zomato.com",
    "swiggy": "https://www.swiggy.com",
    "paytm": "https://paytm.com",
    "phonepe": "https://www.phonepe.com",
    "irctc": "https://www.irctc.co.in",
    "makemytrip": "https://www.makemytrip.com",
    "bookmyshow": "https://in.bookmyshow.com",
    "cricbuzz": "https://www.cricbuzz.com",
    "ndtv": "https://www.ndtv.com",
    "bbc": "https://www.bbc.com",
    "medium": "https://medium.com",
    "udemy": "https://www.udemy.com",
    "coursera": "https://www.coursera.org",
    "naukri": "https://www.naukri.com",
    "internshala": "https://internshala.com",
    "imdb": "https://www.imdb.com",
    "speedtest": "https://www.speedtest.net",
    "weather": "https://weather.com",
    "drive": "https://drive.google.com",
    "photos": "https://photos.google.com",
    "meet": "https://meet.google.com",
}

# Web fallbacks for desktop apps that might not be installed locally.
# When an exe from _BUILTIN_APPS can't be found, we try the web version.
_APP_WEB_FALLBACK: dict[str, str] = {
    "whatsapp": "https://web.whatsapp.com",
    "spotify": "https://open.spotify.com",
    "discord": "https://discord.com/app",
    "telegram": "https://web.telegram.org",
    "notion": "https://www.notion.so",
    "figma": "https://www.figma.com",
    "slack": "https://slack.com/signin",
    "zoom": "https://zoom.us",
    "onenote": "https://www.onenote.com/notebooks",
    "outlook": "https://outlook.live.com",
    "excel": "https://www.office.com/launch/excel",
    "word": "https://www.office.com/launch/word",
    "powerpoint": "https://www.office.com/launch/powerpoint",
    "photoshop": "https://creativecloud.adobe.com",
    "illustrator": "https://creativecloud.adobe.com",
    "epic games": "https://store.epicgames.com",
    "steam": "https://store.steampowered.com",
}


def _find_app_in_system(app_name: str) -> str | None:
    """Search common Windows directories for an app whose name contains
    *app_name*.  Returns ``None`` if nothing is found."""
    import glob as gb

    # Use USERPROFILE instead of hardcoding ``C:\\Users\\{username}``.
    # User profiles can live on drives other than C: (e.g. D:\\Users\\…).
    userprofile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    # ProgramData is always on the system drive
    systemdrive = os.environ.get("SystemDrive", "C:")
    programdata = os.path.join(systemdrive, "ProgramData")

    # Build patterns from multiple possible names
    names_to_search = {app_name.lower()}
    # Also search for the name without spaces
    names_to_search.add(app_name.lower().replace(" ", ""))
    # Title-case variant
    names_to_search.add(app_name.title())

    search_patterns = [
        # Start Menu (most user-facing shortcuts)
        os.path.join(programdata, "Microsoft", "Windows", "Start Menu", "Programs", "**", f"*{n}*.lnk")
        for n in names_to_search
    ] + [
        os.path.join(userprofile, "AppData", "Roaming", "Microsoft", "Windows", "Start Menu", "Programs", "**", f"*{n}*.lnk")
        for n in names_to_search
    ] + [
        # Program Files executables
        os.path.join(systemdrive, "Program Files", "**", f"*{n}*.exe")
        for n in names_to_search
    ] + [
        os.path.join(systemdrive, "Program Files (x86)", "**", f"*{n}*.exe")
        for n in names_to_search
    ] + [
        # AppData executables
        os.path.join(userprofile, "AppData", "Local", "**", f"*{n}*.exe")
        for n in names_to_search
    ] + [
        os.path.join(userprofile, "AppData", "Roaming", "**", f"*{n}*.exe")
        for n in names_to_search
    ]

    best_match = None

    for pattern in search_patterns:
        try:
            matches = gb.glob(pattern, recursive=True)
            if matches:
                # Prefer shorter paths (more likely to be the right app)
                # and prefer Start Menu shortcuts over raw .exe
                shortcut_matches = [m for m in matches if m.endswith(".lnk")]
                if shortcut_matches:
                    return shortcut_matches[0]
                if best_match is None:
                    best_match = matches[0]
        except Exception:
            pass

    return best_match


def openCommand(query: str) -> None:
    """Attempt to open an application or website matching *query*.

    Resolution order
    ----------------
    1. Built-in mapping (covers UWP apps, settings, common aliases, websites).
    2. Exact match in **sys_command** table (local app paths).
    3. Exact match in **web_command** table (URLs).
    4. Windows ``start`` command (PATH-registered apps).
    5. Filesystem scan via ``_find_app_in_system``.
    6. Fuzzy ``LIKE`` match in **sys_command** table.
    7. Fuzzy ``LIKE`` match in **web_command** table.
    8. Try as a website (ASCII names only).
    9. Give up with an apology.
    """
    # Strip trigger words (both English and Hindi)
    trigger_words = [
        "open", "kholo", "खोलो", "khol", "खोल", "chalu karo",
        "start", "launch", "run", "shuru karo", "चालू करो", "ओपन",
        "open the", "kholo to", "kholna", "khol do", "खोल दो",
        "khol ke do", "khol ke dikhao",
        ASSISTANT_NAME,
    ]
    # Strip longer phrases first so shorter substrings don't leave orphans
    for word in sorted(trigger_words, key=len, reverse=True):
        escaped = re.escape(word)
        # \b with re.UNICODE handles Devanagari word boundaries in Python 3
        query = re.sub(
            rf"\b{escaped}\b", "", query,
            flags=re.IGNORECASE | re.UNICODE,
        )
    # Collapse whitespace left behind by removed words
    query = re.sub(r"\s+", " ", query).strip()

    app_name = query.strip().strip('"').strip("'")
    if not app_name:
        return

    conn = _get_conn()
    cursor = conn.cursor()

    def _try_open(path_or_url: str, label: str = "") -> bool:
        """Try to open *path_or_url*.  Returns ``True`` on success."""
        if path_or_url.startswith("http"):
            webbrowser.open(path_or_url)
            return True
        # For bare exe names (no path separators), verify they exist first
        if not os.path.exists(path_or_url) and "/" not in path_or_url and "\\" not in path_or_url:
            import shutil
            if not shutil.which(path_or_url):
                return False
        return _launch_path(path_or_url)

    try:
        # -- Step 0: Built-in mapping ------------------------------------
        lookup = app_name.lower()
        if lookup in _BUILTIN_APPS:
            path = _BUILTIN_APPS[lookup]
            print(f"[BUILTIN] Trying: {path}")
            if _try_open(path):
                _say(f"Opening {app_name}", f"{app_name} khol raha hoon")
                return
            # Builtin failed (e.g., whatsapp.exe not installed) — check
            # for a web fallback before scanning the filesystem.
            print(f"[BUILTIN] Failed, checking web fallback...")
            if lookup in _APP_WEB_FALLBACK:
                url = _APP_WEB_FALLBACK[lookup]
                print(f"[WEB-FALLBACK] Opening: {url}")
                _say(f"Opening {app_name} online", f"{app_name} online khol raha hoon")
                webbrowser.open(url)
                return
            # No web fallback — fall through to DB / filesystem search

        # -- Step 1: DB exact match (apps) --------------------------------
        cursor.execute(
            "SELECT path FROM sys_command WHERE LOWER(name) = LOWER(?)",
            (app_name,),
        )
        rows = cursor.fetchall()
        if rows:
            path = rows[0][0]
            print(f"[DB] Opening: {path}")
            if _try_open(path):
                _say(f"Opening {app_name}", f"{app_name} khol raha hoon")
                return

        # -- Step 2: DB exact match (websites) ----------------------------
        cursor.execute(
            "SELECT url FROM web_command WHERE LOWER(name) = LOWER(?)",
            (app_name,),
        )
        rows = cursor.fetchall()
        if rows:
            url = rows[0][0]
            print(f"[WEB] Opening: {url}")
            _say(f"Opening {app_name}", f"{app_name} khol raha hoon")
            webbrowser.open(url)
            return

        # -- Step 3: Windows 'start' command -----------------------------
        print(f"[SYS] Trying: start \"{app_name}\"")
        try:
            result = os.system(f'start "" "{app_name}"')
            if result == 0:
                _say(f"Opening {app_name}", f"{app_name} khol raha hoon")
                return
        except Exception:
            pass

        # -- Step 4: Filesystem scan -------------------------------------
        print(f"[SEARCH] Looking for: {app_name}")
        found = _find_app_in_system(app_name)
        if found:
            print(f"[FOUND] {found}")
            _say(f"Opening {app_name}", f"{app_name} khol raha hoon")
            _launch_path(found)
            # Cache for next time
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO sys_command (name, path) VALUES (?, ?)",
                    (app_name.lower(), found),
                )
                conn.commit()
            except Exception:
                pass
            return

        # -- Step 5: DB fuzzy match on sys_command -----------------------
        cursor.execute(
            "SELECT name, path FROM sys_command WHERE LOWER(name) LIKE ?",
            (f"%{app_name}%",),
        )
        rows = cursor.fetchall()
        if rows:
            match_name, path = rows[0]
            print(f"[FUZZY-SYS] Found: {match_name} -> {path}")
            if _try_open(path):
                _say(f"Opening {match_name}", f"{match_name} khol raha hoon")
                return

        # -- Step 6: DB fuzzy match on web_command -----------------------
        cursor.execute(
            "SELECT name, url FROM web_command WHERE LOWER(name) LIKE ?",
            (f"%{app_name}%",),
        )
        rows = cursor.fetchall()
        if rows:
            match_name, url = rows[0]
            print(f"[FUZZY-WEB] Found: {match_name} -> {url}")
            _say(f"Opening {match_name}", f"{match_name} khol raha hoon")
            webbrowser.open(url)
            return

        # -- Step 7: Try as website (ASCII-only names) -------------------
        # Don't guess websites for Devanagari / non-ASCII app names
        is_ascii = all(ord(c) < 128 for c in app_name)
        if is_ascii and "." not in app_name and " " not in app_name:
            url_guess = f"https://www.{app_name}.com"
            print(f"[GUESS] Trying: {url_guess}")
            _say(f"Trying {app_name} website", f"{app_name} website try kar raha hoon")
            webbrowser.open(url_guess)
            return

        # -- Step 8: Search web for relatable info ----------------------
        # If nothing matched locally, search Google AND YouTube for the name.
        # Covers YouTubers, new websites, or anything the user might want.
        google_search = f"https://www.google.com/search?q={url_quote(app_name)}"
        yt_search = f"https://www.youtube.com/results?search_query={url_quote(app_name)}"

        _say(
            f"Searching {app_name} on Google and YouTube",
            f"Google aur YouTube par {app_name} dhundh raha hoon",
        )
        webbrowser.open(google_search)
        time.sleep(0.3)
        webbrowser.open(yt_search)
        return

    except Exception as exc:
        print(f"Error in openCommand: {exc}")
        import traceback as tb
        tb.print_exc()
        _say(
            "Something went wrong while trying to open that",
            "Kuch galat ho gaya, maaf karna",
        )
    finally:
        conn.close()


def _launch_path(path: str) -> bool:
    """Open the given file / shortcut, handling UWP apps gracefully.

    Returns ``True`` if the launch succeeded, ``False`` otherwise.
    """
    try:
        if "shell:" in path.lower():
            # UWP app / shell: protocol
            result = os.system(f'start "" {path}')
            return result == 0
        else:
            # Check if the path exists first (exe, lnk, or URL)
            if path.startswith("http"):
                import webbrowser
                webbrowser.open(path)
                return True

            if os.path.exists(path):
                os.startfile(path)
                return True

            # Path doesn't exist — try as a bare command via start
            result = os.system(f'start "" "{path}"')
            return result == 0
    except FileNotFoundError:
        return False
    except Exception as exc:
        print(f"_launch_path error: {exc}")
        try:
            import webbrowser
            if path.startswith("http"):
                webbrowser.open(path)
                return True
            os.system(f'start "" "{path}"')
            return True
        except Exception:
            return False


# ========================================================================
#  YouTuber / Channel search
# ========================================================================

def openYoutuber(query: str) -> None:
    """Extract a YouTuber/channel name from *query* and open their channel
    on YouTube.

    First tries ``youtube.com/@handle`` (the modern URL format), then falls
    back to a search query so the channel still appears at the top of results.
    """
    # Strip command trigger words to isolate the channel name
    trigger_words = [
        "open", "kholo", "खोलो", "khol", "खोल",
        "channel", "चैनल", "youtuber", "यूट्यूबर",
        "youtube channel", "youtube par", "youtube pe",
        "ka channel", "ki channel", "ka channel kholo",
        "ki channel kholo", "channel kholo", "channel open",
        "search", "dhundho", "ढूंढो", "khojo", "खोजो",
        "on youtube", ASSISTANT_NAME,
    ]
    name = query
    # Strip longer phrases first
    for word in sorted(trigger_words, key=len, reverse=True):
        name = re.sub(rf"\b{re.escape(word)}\b", "", name, flags=re.IGNORECASE | re.UNICODE)
    name = re.sub(r"\s+", " ", name).strip()

    if not name:
        # Nothing left after stripping — open YouTube homepage
        _say("Opening YouTube", "YouTube khol raha hoon")
        webbrowser.open("https://www.youtube.com")
        return

    encoded = url_quote(name)
    channel_url = f"https://www.youtube.com/@{name.lower().replace(' ', '')}"
    search_url = f"https://www.youtube.com/results?search_query={encoded}"

    _say(
        f"Opening {name} on YouTube",
        f"YouTube par {name} khol raha hoon",
    )

    # Try the @handle URL first (quick, direct to channel if it exists)
    try:
        webbrowser.open(channel_url)
    except Exception:
        webbrowser.open(search_url)


# ========================================================================
#  YouTube
# ========================================================================

def PlayYoutube(query: str) -> None:
    """Search YouTube for the term extracted from *query* and play the top
    result."""
    search_term = extract_yt_term(query)
    _say(
        f"Playing {search_term} on YouTube",
        f"YouTube par {search_term} baja raha hoon",
    )
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
                # Use hotkey() instead of manual keyDown/press/sleep/keyUp.
                # The old code held Win for 2 seconds, which flashed the
                # Start menu and interfered with other shortcuts.
                pyautogui.hotkey("win", "j")

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

    # Guard: empty query after word removal would match ALL contacts
    if not query:
        speak("Please say the contact name.")
        return 0, 0

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
    """Open WhatsApp and initiate a call, video call, or message.

    Uses WhatsApp Web's native URI schemes for opening chats.  For calls and
    video calls on WhatsApp Web the user must click the call button manually
    (WhatsApp Web does not provide a URI scheme for initiating calls).

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
    # Clean phone number: remove spaces, dashes, and ensure + prefix
    phone_clean = Phone.strip().replace(" ", "").replace("-", "")
    if not phone_clean.startswith("+"):
        phone_clean = "+" + phone_clean

    if flag == "message":
        encoded = url_quote(message if message else "")
        whatsapp_url = (
            f"https://web.whatsapp.com/send?phone={phone_clean}&text={encoded}"
        )
        _say(
            f"Opening WhatsApp for {name}. Press Enter to send.",
            f"{name} ke liye WhatsApp khol raha hoon. Enter press karo bhejne ke liye.",
        )
    elif flag == "call":
        whatsapp_url = f"https://web.whatsapp.com/send?phone={phone_clean}"
        _say(
            f"Opening chat with {name}. Click the Call button to start audio call.",
            f"{name} ki chat khol raha hoon. Call button dabao.",
        )
    else:  # video call
        whatsapp_url = f"https://web.whatsapp.com/send?phone={phone_clean}"
        _say(
            f"Opening chat with {name}. Click Video Call button to start.",
            f"{name} ki chat khol raha hoon. Video Call button dabao.",
        )

    webbrowser.open(whatsapp_url)

    # NOTE: WhatsApp Web does not expose call / video-call URI schemes.
    # The user must manually click the header buttons.  Old code tried
    # ``pyautogui.hotkey("alt", "shift", "]")`` which is NOT a real
    # WhatsApp shortcut and did nothing.


# ========================================================================
#  Universal web search fallback
# ========================================================================

def searchWeb(query: str) -> None:
    """Search Google and YouTube for *query*.

    Used as the last-resort fallback when no app, website, or command
    handler matches the user's request.  Opens Google search in the default
    browser so the user always gets relevant information.
    """
    encoded = url_quote(query)
    google_url = f"https://www.google.com/search?q={encoded}"

    _say(
        f"Searching the web for {query}",
        f"Internet par {query} dhundh raha hoon",
    )
    webbrowser.open(google_url)


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
    except ImportError:
        speak(
            "Chatbot feature is not available. "
            "Please install hugchat: pip install hugchat"
        )
        return "Chatbot unavailable — hugchat not installed"

    try:
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

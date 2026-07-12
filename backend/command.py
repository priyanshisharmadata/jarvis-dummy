"""
Voice-command engine for Jarvis.
=================================

Handles speech-to-text (via ``speech_recognition``), text-to-speech (via
``pyttsx3``), and multi-language command routing (Hindi, English, Hinglish).

Exposed to the front-end via Eel
---------------------------------
``takeAllCommands(message=None)``
    The single entry point — either listens to the microphone (when *message*
    is ``None``) or processes a typed command.  Dispatches to the appropriate
    feature handler.
"""

import sys
import time
import traceback
from datetime import datetime
from typing import Optional

import eel
import pyttsx3
import speech_recognition as sr

from backend import config

# ---------------------------------------------------------------------------
#  Speech-recognition retry configuration
# ---------------------------------------------------------------------------
# Number of times to retry the Google Speech API on transient errors
# (network glitches, 500s) before giving up.
_MAX_API_RETRIES = 1
# Seconds to wait between retries (doubles each retry: 1, 2, 4, …).
_API_RETRY_BASE_DELAY = 0.8

# Reconfigure stdout to handle Unicode (Devanagari) characters on Windows
# terminals that default to cp1252.  Without this, ``print()`` calls with
# Hindi text crash with ``UnicodeEncodeError``.
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ---------------------------------------------------------------------------
#  Text-to-speech
# ---------------------------------------------------------------------------

# Module-level engine cache — creating a new pyttsx3 engine on every call is
# slow and causes stuttering between consecutive ``speak()`` invocations.
_tts_engine: Optional[pyttsx3.Engine] = None
_tts_lock = None  # lazily-created threading.Lock in speak()

# Module-level language flag — set by ``takeAllCommands`` before
# dispatching to feature functions so they can respond in Hindi/English.
_last_query_hindi = False

# Cached energy threshold — avoids re-calibrating on retry.
_cached_energy_threshold: float | None = None

# Tracks whether we've already suppressed media players in this session.
_suppress_done = False


def _suppress_interfering_apps() -> None:
    """Fast, non-blocking media-player suppression.

    Phase 1 (sync): ``taskkill /f`` — blocks for ~0.3s.
    Phase 2 (bg thread): PowerShell minimize — runs in background so it
    never delays the mic setup.
    """
    import subprocess as _sp
    import threading as _th
    _interfering = [
        "MXPlayer.exe",
        "PotPlayerMini64.exe",
        "PotPlayerMini.exe",
        "GOM.EXE",
        "GOM64.EXE",
        "VLC.exe",
        "wmplayer.exe",
    ]
    # Phase 1: force-kill (fast, synchronous — must finish before mic opens)
    try:
        _sp.run(
            ["taskkill", "/f", "/im"] + _interfering,
            capture_output=True,
            timeout=1.0,
        )
    except Exception:
        pass

    # Phase 2: minimize survivors in background (PowerShell startup is slow)
    def _minimize_bg() -> None:
        try:
            ps_script = (
                "Get-Process -Name "
                + ",".join(p.replace(".exe", "") for p in _interfering)
                + " -ErrorAction SilentlyContinue | ForEach-Object { "
                "$_.MainWindowHandle } | ForEach-Object { "
                "Add-Type -Name Win32 -Namespace API -MemberDefinition '"
                "[DllImport(\"user32.dll\")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);"
                "'; [API.Win32]::ShowWindow($_, 6) }"
            )
            _sp.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                timeout=5.0,
            )
        except Exception:
            pass

    _th.Thread(target=_minimize_bg, daemon=True).start()


def _say(en: str, hi: str) -> None:
    """Speak in the same language the user's last query was in."""
    if _last_query_hindi:
        speak(hi, "hi")
    else:
        speak(en, "en")


def speak(text: str, lang: str = "en") -> None:
    """Speak *text* aloud using a SAPI5 voice.

    Parameters
    ----------
    text : str
        The message to speak (converted to ``str`` automatically).
    lang : str
        ``"hi"`` tries to select a Hindi voice; ``"en"`` (default) uses the
        first available voice.
    """
    global _tts_engine, _tts_lock

    text = str(text)
    try:
        # Lazy-init the lock (avoid import-time side-effects)
        if _tts_lock is None:
            import threading
            _tts_lock = threading.Lock()

        with _tts_lock:
            if _tts_engine is None:
                _tts_engine = pyttsx3.init("sapi5")

            voices = _tts_engine.getProperty("voices")

            if lang == "hi":
                # Prefer a Hindi voice when available
                hindi = [v for v in voices if "hindi" in v.name.lower()]
                if hindi:
                    _tts_engine.setProperty("voice", hindi[0].id)
                elif voices:
                    _tts_engine.setProperty("voice", voices[0].id)
            elif voices:
                _tts_engine.setProperty("voice", voices[0].id)

            _tts_engine.setProperty("rate", 170)
            eel.DisplayMessage(text)
            _tts_engine.say(text)
            _tts_engine.runAndWait()
    except Exception as exc:
        print(f"Speak error: {exc}")
        # Reset the engine so next call tries to re-init
        try:
            if _tts_engine is not None:
                _tts_engine.stop()
        except Exception:
            pass
        _tts_engine = None
        # Still try to show the message even if TTS fails
        try:
            eel.DisplayMessage(text)
        except Exception:
            pass


# ---------------------------------------------------------------------------
#  Speech-to-text  (multi-engine, multi-language)
# ---------------------------------------------------------------------------
#
#  Engine cascade (tried in order until one succeeds):
#    1. Google Speech Recognition  — shared key, works without any API key
#    2. Google show_all alternates — picks best from multiple hypotheses
#    3. PocketSphinx              — offline, always available when installed
#    4. Windows SAPI              — offline, built into Windows 10/11
# ---------------------------------------------------------------------------

import tempfile as _tempfile
import os as _os

# Language models to try for Google Speech Recognition (in priority order).
# Reduced to 3 — en-IN handles Indian English + Hinglish well enough
# that en-US is redundant; AUTO catches anything else.
_LANG_ATTEMPTS = [
    ("en-IN", "EN-IN"),
    ("hi-IN", "HI"),
    (None,    "AUTO"),   # let Google detect language automatically
]

# Words Google sometimes returns as "filler" when it can't understand speech.
# These are never valid Jarvis commands, so we reject them as gibberish.
_GIBBERISH = {
    "the", "a", "an", "oh", "uh", "um", "ah", "hmm", "mm",
    "i", "you", "we", "it", "he", "she", "they",
    "and", "but", "or", "so", "if", "in", "on", "at", "to", "of",
    "is", "am", "are", "was", "were", "be", "been",
    "yes", "no", "ok", "okay", "yeah", "hey", "hi", "hello",
    "thanks", "thank you", "please",
    "what", "when", "where", "who", "why", "how",
    "this", "that", "these", "those", "there", "here",
    "just", "like", "well", "right", "now", "then",
}


def _is_gibberish(text: str) -> bool:
    """Return True if *text* looks like a recognition error."""
    t = text.strip().lower()
    if len(t) <= 1:
        return True
    if t in _GIBBERISH:
        return True
    if len(t) <= 2 and t.isalpha():
        return True
    return False


def _extract_best(response) -> str | None:
    """Pick the longest non-gibberish transcript from a Google response."""
    if not response:
        return None
    candidates: list[str] = []

    if isinstance(response, dict):
        for alt in response.get("alternative", []):
            t = (alt.get("transcript", "") if isinstance(alt, dict) else str(alt)).strip()
            if t:
                candidates.append(t)
    elif isinstance(response, list):
        for item in response:
            t = (item.get("transcript", "") if isinstance(item, dict) else str(item)).strip()
            if t:
                candidates.append(t)
    elif isinstance(response, str):
        candidates.append(response.strip())

    candidates.sort(key=lambda t: len(t), reverse=True)
    for c in candidates:
        if not _is_gibberish(c):
            return c
    return candidates[0] if candidates else None


def _transcribe_google(
    recognizer: sr.Recognizer,
    audio,
    lang_code: str | None,
    google_key: str | None,
    tag: str,
) -> tuple[str | None, bool]:
    """Call Google Speech Recognition with retries + alternate hypotheses."""
    for attempt in range(_MAX_API_RETRIES + 1):
        try:
            kwargs: dict = {"show_all": True}
            if lang_code is not None:
                kwargs["language"] = lang_code
            if google_key:
                kwargs["key"] = google_key

            response = recognizer.recognize_google(audio, **kwargs)
            best = _extract_best(response)

            if best and not _is_gibberish(best):
                print(f"[{tag}] User said: {best}")
                return best, False
            return None, False

        except sr.UnknownValueError:
            return None, False

        except sr.RequestError as exc:
            err = str(exc)
            print(f"[{tag}] Google API error (attempt {attempt + 1}): {err}")
            if "404" in err.lower():
                return None, True
            if attempt < _MAX_API_RETRIES:
                delay = _API_RETRY_BASE_DELAY * (2 ** attempt)
                print(f"[{tag}] Retrying in {delay:.1f}s...")
                time.sleep(delay)
            else:
                return None, True

    return None, True


def _recognize_sphinx(recognizer, audio) -> str | None:
    """Offline PocketSphinx — no API key needed."""
    try:
        r = recognizer.recognize_sphinx(audio)
        if r and r.strip() and not _is_gibberish(r.strip()):
            return r.strip()
    except Exception:
        pass
    return None


def _recognize_sapi(audio_data) -> str | None:
    """Windows built-in offline speech recognition — no API key needed.

    Uses the Windows Desktop Speech Recognition engine (SAPI) that ships
    with Windows 10/11.  Completely offline, no internet required.
    """
    try:
        import pythoncom
        import win32com.client as _win32
        import io as _io

        pythoncom.CoInitialize()
        try:
            # Write audio to an in-memory WAV stream
            wav_buf = _io.BytesIO(audio_data.get_wav_data())
            wav_buf.seek(0)

            # Create SAPI file stream from the WAV data
            stream = _win32.Dispatch("SAPI.SpFileStream")
            stream.Open(wav_buf, _win32.constants.SPFileMode_ReadOnly)

            engine = _win32.Dispatch("SAPI.SpInprocRecognizer")
            engine.AudioInputStream = stream

            result = engine.Recognize()
            if result:
                text = result.PhraseInfo.GetText()
                if text and text.strip() and not _is_gibberish(text.strip()):
                    return text.strip()
        finally:
            pythoncom.CoUninitialize()
    except ImportError:
        pass
    except Exception:
        pass
    return None


def takecommand(lang: str = "auto") -> str | None:
    """Listen to the microphone and return the recognised utterance.

    Multi-engine cascade (no API key required):
      1. Google Speech Recognition (shared key, with retries)
      2. Google alternate hypotheses (picks best from multiple results)
      3. PocketSphinx (offline)
      4. Windows SAPI    (offline, built into Windows)

    Returns
    -------
    str or None
        Lower-cased text, or ``None`` if all engines failed.
    """
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 1.2   # longer for Hindi/Hinglish pauses
    recognizer.phrase_threshold = 0.2  # detect even short/quiet phrases
    recognizer.non_speaking_duration = 0.3  # minimal silence padding

    # Suppress media players once per session — skip on retries
    global _suppress_done
    if not _suppress_done:
        _suppress_interfering_apps()
        _suppress_done = True

    recognizer.dynamic_energy_threshold = True
    recognizer.dynamic_energy_ratio = 1.15   # more sensitive (was 1.3)

    # Use cached threshold if available (skips calibration on retry)
    global _cached_energy_threshold
    if _cached_energy_threshold is not None:
        recognizer.energy_threshold = _cached_energy_threshold
    else:
        recognizer.energy_threshold = 200  # lower initial threshold (was 300)

    # -- Step 1: capture audio from the microphone --------------------------
    try:
        with sr.Microphone() as source:
            print("I'm listening... (सुन रहा हूं...)")
            eel.DisplayMessage("I'm listening... / सुन रहा हूं...")

            try:
                # Skip calibration if we already have a cached threshold
                if _cached_energy_threshold is not None:
                    print(f"Using cached energy threshold: {_cached_energy_threshold}")
                else:
                    recognizer.adjust_for_ambient_noise(source, duration=1.2)
                    if recognizer.energy_threshold < 120:
                        recognizer.energy_threshold = 120
                    _cached_energy_threshold = recognizer.energy_threshold
                    print(f"Energy threshold (calibrated): {recognizer.energy_threshold}")
            except Exception as exc:
                print(f"Ambient calibration failed: {exc}")
                recognizer.energy_threshold = 200
                _cached_energy_threshold = 200

            audio = recognizer.listen(source, timeout=7, phrase_time_limit=8)

    except sr.WaitTimeoutError:
        print("No speech detected within 7 seconds")
        eel.DisplayMessage("Didn't catch that — try again?")
        return None
    except Exception as exc:
        print(f"Microphone error: {exc}")
        traceback.print_exc()
        try:
            speak("Microphone problem. Please check your mic and try again.")
        except Exception:
            pass
        return None

    # -- Reject audio that's obviously just noise ---------------------------
    try:
        import numpy as _np
        raw = audio.get_raw_data()
        samples = _np.frombuffer(raw, dtype=_np.int16)
        rms = _np.sqrt(_np.mean(samples.astype(_np.float64) ** 2))
        print(f"Audio RMS: {rms:.1f}")
        if rms < 20:
            print("Audio too quiet — rejecting as noise")
            eel.DisplayMessage("Too quiet — please speak louder.")
            return None
    except Exception:
        pass

    # -- Step 2: transcribe — Google (all language models) ------------------
    print("Recognizing...")
    eel.DisplayMessage("Recognizing...")

    query: str | None = None
    api_unreachable = False

    google_key = (
        config.GOOGLE_SPEECH_API_KEY.strip()
        if config.GOOGLE_SPEECH_API_KEY and config.GOOGLE_SPEECH_API_KEY.strip()
        else None
    )

    if not google_key:
        print("No custom API key — using shared Google key (retries built-in)")

    for lang_code, tag in _LANG_ATTEMPTS:
        result, is_api_error = _transcribe_google(
            recognizer, audio, lang_code, google_key, tag
        )
        if is_api_error:
            api_unreachable = True
            break
        if result:
            query = result
            break

    # -- Step 3: offline fallback #1 — PocketSphinx -------------------------
    if query is None and not api_unreachable:
        print("Trying offline Sphinx...")
        sphinx_result = _recognize_sphinx(recognizer, audio)
        if sphinx_result:
            print(f"[SPHINX] User said: {sphinx_result}")
            query = sphinx_result

    # -- Step 4: offline fallback #2 — Windows SAPI -------------------------
    if query is None and not api_unreachable:
        print("Trying Windows offline SAPI...")
        sapi_result = _recognize_sapi(audio)
        if sapi_result:
            print(f"[SAPI] User said: {sapi_result}")
            query = sapi_result

    # -- Step 5: report back -------------------------------------------------
    if query is None:
        if api_unreachable:
            _say(
                "Speech recognition is unavailable. Check internet or type your command.",
                "Speech recognition abhi kaam nahi kar raha. Internet check karo ya type karo.",
            )
        else:
            _say(
                "Sorry, didn't understand. Try again or type your command.",
                "Sorry, main samjha nahi. Dobara bolo ya type karo.",
            )
        # Save debug audio so the user can check what the mic captured
        try:
            _tmp = _tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False, prefix="jarvis_debug_"
            )
            _tmp.write(audio.get_wav_data())
            _tmp.close()
            print(f"Debug audio saved: {_tmp.name}")
        except Exception:
            pass
        return None

    eel.DisplayMessage(query)

    try:
        has_hindi = any(ord(c) > 127 for c in query)
        speak(query, "hi" if has_hindi else "en")
    except Exception:
        pass

    return query.lower()


# ---------------------------------------------------------------------------
#  Keyword matching helper
# ---------------------------------------------------------------------------

def _match_keyword(query: str, keyword: str) -> bool:
    """Match *keyword* in *query* using word boundaries for single words.

    Multi-word keywords (like ``"on youtube"``) still use substring matching
    because they are specific enough not to cause false positives.  Single
    words like ``"play"``, ``"search"``, ``"open"``, ``"time"`` use
    ``\\bword\\b`` to avoid matching inside longer words (e.g. "research"
    matching "search", or "display" matching "play").
    """
    if " " in keyword:
        # Multi-word — specific enough for substring matching
        return keyword in query
    # Single word — use word boundaries to avoid false positives
    import re as _re
    return bool(_re.search(rf"\b{_re.escape(keyword)}\b", query))


# ---------------------------------------------------------------------------
#  Command processor  (internal — does NOT manage UI visibility)
# ---------------------------------------------------------------------------

# Keywords that exit continuous listening mode.
_CONTINUOUS_EXIT = {
    "stop", "exit", "quit", "bye", "goodbye", "nothing", "never mind",
    "turn off", "shut down", "shutdown", "power off",
    "band kar", "band karo", "bas itna hi", "chup ho ja", "ruk ja",
    "nikal", "jao", "hato", "bas", "enough", "so ja", "soja",
    "fir milte hai", "fir milte hain", "bye bye", "tata",
}


def _process_query(query: str, message: str | None) -> None:
    """Process a single recognised / typed command and dispatch to features.

    Does **not** call ``eel.ShowHood()`` — the caller decides when to show
    the idle UI (typed mode or continuous-mode exit).
    """
    # ---- Detect language BEFORE transliteration overwrites query ----------
    global _last_query_hindi
    _last_query_hindi = any(ord(c) > 127 for c in query)

    try:
        # ---- Step 0: transliterate Hindi words to English equivalents ----
        q = query.lower()

        hindi_to_eng = {
            # -- Multi-word command phrases (match before single words) --
            "गाना बजाओ": "play song", "गाना बजा": "play song",
            "गाने बजाओ": "play song", "गाना चला": "play song",
            "चालू करो": "open", "शुरू करो": "open",
            "खोल दो": "open", "खोल के": "open", "खोलना": "open",
            "चला दो": "play", "बजा दो": "play", "बजा के": "play",
            "बंद करो": "close", "बंद कर": "close",
            "ढूंढो": "search", "खोजो": "search", "सर्च करो": "search",
            "गूगल करो": "google search", "गूगल पर ढूंढो": "google search",
            "यूट्यूब पर ढूंढो": "youtube search", "यूट्यूब खोजो": "youtube search",
            "इंटरनेट पर ढूंढो": "web search", "ऑनलाइन ढूंढो": "web search",
            "भेजो": "send", "भेज दो": "send",
            # -- Command verbs --
            "ओपन": "open", "खोलो": "open", "खोल": "open",
            "स्टार्ट": "start", "लॉन्च": "launch", "निकालो": "open",
            "प्ले": "play", "बजा": "play", "बजाओ": "play",
            "चला": "play", "चलाओ": "play",
            "गाना": "play song", "गाने": "play song",
            # -- Apps / targets --
            "कैमरा": "camera", "कैम": "camera", "फोटो": "camera",
            "कैलकुलेटर": "calculator", "कैलक्यूलेटर": "calculator",
            "कैलेंडर": "calendar", "कलेंडर": "calendar",
            "यूट्यूब": "youtube", "युटुब": "youtube", "यूटूब": "youtube",
            "व्हाट्सएप": "whatsapp", "वॉट्स्ऐप": "whatsapp", "व्हाट्सएप्प": "whatsapp",
            "मैसेज": "message", "मेसेज": "message", "सन्देश": "message",
            "कॉल": "call", "काल": "call", "फ़ोन": "call",
            "टाइम": "time", "समय": "time", "टाईम": "time",
            "डेट": "date", "तारीख": "date",
            "नोटपैड": "notepad", "क्रोम": "chrome", "एज": "edge",
            "सेटिंग": "settings", "सेटिंग्स": "settings",
            "एक्सेल": "excel", "वर्ड": "word", "पावरपॉइंट": "powerpoint",
            "म्यूजिक": "music", "वीडियो": "video", "विडियो": "video",
            "स्टोर": "store", "मौसम": "weather", "मेप": "maps",
            "गूगल": "google", "फेसबुक": "facebook", "इंस्टाग्राम": "instagram",
            "स्पॉटिफाई": "spotify", "डिस्कॉर्ड": "discord",
        }

        for hi_word, eng_word in hindi_to_eng.items():
            if hi_word in q:
                q = q.replace(hi_word, eng_word)

        # Remove Hindi filler words using whole-word matching
        _filler_words = {
            # Particles / postpositions
            "दो", "देना", "दिखाओ", "के", "को", "पर", "पे",
            "में", "से", "ना", "जरा", "ज़रा", "थोड़ा", "रे",
            # Question words
            "क्या", "क्यों", "कैसे", "कब", "कहाँ", "कौन", "किसे",
            "किसका", "कितना", "कितने",
            # Pronouns
            "तुम", "तुम्हारा", "तुम्हारे", "तुम्हें", "तुझे",
            "आप", "आपका", "आपके", "आपको",
            "मैं", "मुझे", "मेरा", "मेरी", "मेरे", "हम", "हमें", "हमारा",
            "यह", "ये", "वह", "वो", "इस", "उस", "इसे", "उसे",
            "इसका", "उसका", "इन", "उन",
            # Auxiliary / modal verbs
            "है", "हैं", "हो", "हूं", "था", "थी", "थे",
            "सकता", "सकती", "सकते", "सकता हूं", "सकते हो",
            "कर", "करो", "करना", "करते", "करती", "करूं", "करें",
            "किया", "कीजिए", "कर दो", "कर देना",
            "होना", "होता", "होती", "होते", "हुआ", "हुई",
            "जाओ", "जाना", "जाए", "जाएं", "जाऊं",
            "दे", "दो", "दूं", "देंगे",
            "लो", "लेना", "ले",
            "चाहता", "चाहती", "चाहते", "चाहिए",
            "रहा", "रही", "रहे", "रहा हूं", "रहे हैं",
            # Postpositions
            "लिए", "वाला", "वाली", "वाले", "जैसा", "जैसे",
            "बिना", "बाद", "पहले", "अंदर", "बाहर",
            "ऊपर", "नीचे", "सामने", "पीछे", "आसपास",
            # Fillers / discourse markers
            "तो", "भी", "ही", "बस", "अभी", "अब", "फिर",
            "और", "या", "लेकिन", "मगर", "कि",
            "ज़रा", "जरा", "थोड़ा", "एक", "कोई", "कुछ",
        }
        q = " ".join(w for w in q.split() if w not in _filler_words)

        # Collapse multiple spaces
        import re as _re
        q = _re.sub(r"\s+", " ", q).strip()

        print(f"[CMD] Processing: {q}")

        # From this point onward, use transliterated ``q`` as canonical text
        query = q

        # ==================================================================
        #  SEARCH / GOOGLE / WEB  commands
        # ==================================================================
        search_keywords = [
            "search", "google search", "web search", "youtube search",
            "search karo", "google karo", "google par", "youtube par",
            "search for", "dhundho", "ढूंढो", "khojo", "खोजो",
            "internet par", "online search",
        ]
        if any(_match_keyword(query, kw) for kw in search_keywords):
            from backend.feature import searchWeb
            searchWeb(query)
            return

        # ==================================================================
        #  YOUTUBER / CHANNEL  search
        # ==================================================================
        channel_keywords = [
            "channel", "चैनल", "youtuber", "यूट्यूबर",
            "youtube channel", "ka channel", "ki channel",
        ]
        if any(_match_keyword(query, kw) for kw in channel_keywords):
            from backend.feature import openYoutuber
            openYoutuber(query)
            return

        # ==================================================================
        #  OPEN / KHOLO  commands
        # ==================================================================
        open_keywords = [
            "open", "kholo", "खोलो", "khol", "खोल",
            "chalu karo", "start",
        ]
        if any(_match_keyword(query, kw) for kw in open_keywords):
            from backend.feature import openCommand
            openCommand(query)
            return

        # ==================================================================
        #  PLAY / YOUTUBE  commands
        # ==================================================================
        play_keywords = [
            "on youtube", "play", "baja", "बजा", "chala", "चला",
            "gaana", "गाना", "youtube pe", "youtube par",
            "song", "music", "गाने",
        ]
        if any(_match_keyword(query, kw) for kw in play_keywords):
            from backend.feature import PlayYoutube
            PlayYoutube(query)
            return

        # ==================================================================
        #  WHATSAPP / CALL / MESSAGE  commands
        # ==================================================================
        msg_keywords = [
            "send message", "message bhejo", "मैसेज", "message karo",
            "whatsapp", "call", "कॉल", "video call", "video कॉल",
        ]
        if any(_match_keyword(query, kw) for kw in msg_keywords):
            from backend.feature import findContact, whatsApp, openCommand

            is_just_whatsapp = (
                "whatsapp" in query
                and not any(w in query for w in ("call", "message", "video", "कॉल", "मैसेज", "bhejo", "karo"))
            )
            if is_just_whatsapp:
                openCommand("open whatsapp")
                return

            flag = ""
            phone, name = findContact(query)

            if phone != 0 and phone is not None:
                if any(w in query for w in ("send message", "message", "मैसेज")):
                    flag = "message"
                    if message is None:
                        speak("Kya message bhejna hai? / What message to send?")
                        time.sleep(0.5)
                        msg_text = takecommand()
                        if not msg_text:
                            speak("Message cancelled — no speech detected.")
                            return
                    else:
                        from backend.helper import remove_words
                        contact_words = name.lower().split() if name and name != query else []
                        cmd_words = ["send", "message", "to", "bhejo", "karo",
                                     "whatsapp", "के", "को", "भेजो", "करो", "सन्देश"]
                        remaining = remove_words(query, cmd_words + contact_words + [config.ASSISTANT_NAME])
                        if remaining.strip():
                            msg_text = remaining.strip()
                            speak(f"Sending message to {name}: {msg_text}")
                        else:
                            speak(f"Opening WhatsApp for {name}. Please type your message.")
                            msg_text = ""
                    whatsApp(phone, msg_text, flag, name)
                    return
                elif "video" in query:
                    flag = "video call"
                else:
                    flag = "call"
                whatsApp(phone, query, flag, name)

            return

        # ==================================================================
        #  CAMERA  specific
        # ==================================================================
        camera_keywords = ["camera", "कैमरा", "photo", "फोटो", "selfie"]
        if any(kw in query for kw in camera_keywords):
            from backend.feature import openCommand
            openCommand("open camera")
            return

        # ==================================================================
        #  TIME  command
        # ==================================================================
        time_keywords = ["time", "समय", "kitne baje"]
        if any(kw in query for kw in time_keywords):
            now = datetime.now().strftime("%I:%M %p")
            _say(f"Time is {now}", f"समय हुआ है {now}")
            return

        # ==================================================================
        #  DATE  command
        # ==================================================================
        date_keywords = ["date", "तारीख", "aaj ki date"]
        if any(kw in query for kw in date_keywords):
            today = datetime.now().strftime("%d %B %Y")
            _say(f"Today's date is {today}", f"आज की तारीख है {today}")
            return

        # ==================================================================
        #  FALLBACK  -- Web search (Google)
        # ==================================================================
        from backend.feature import searchWeb
        searchWeb(query)

    except Exception as exc:
        print(f"Error in command dispatch: {exc}")
        traceback.print_exc()
        try:
            speak("Sorry, kuch galat ho gaya.")
        except Exception:
            pass


# ---------------------------------------------------------------------------
#  Command dispatcher  (exposed to Eel)
# ---------------------------------------------------------------------------

@eel.expose
def takeAllCommands(message: str | None = None) -> None:
    """The main command loop — voice or typed.

    Voice mode (``message is None``)
    --------------------------------
    Enters **continuous listening** — after each command completes the mic
    re-opens automatically so you can give multiple commands without
    pressing the mic button again.

    Say **"stop"**, **"bye"**, **"turn off"**, **"bas"**, **"so ja"**, or
    **"band kar"** to exit continuous mode.

    Typed mode (``message`` is a string)
    ------------------------------------
    Processes the single typed command then shows the idle hood.
    """
    if message is None:
        # ================================================================
        #  CONTINUOUS VOICE MODE
        # ================================================================
        # Jarvis keeps listening until you say "bye", "stop", "turn off",
        # "band kar", etc.  Silence does NOT exit — only explicit keywords.
        print("Continuous listening started — say 'bye' or 'stop' to exit")

        _silent_loops = 0  # track consecutive silent cycles

        while True:
            query = takecommand()
            if not query:
                # First attempt failed — one quick retry (no TTS, just visual)
                eel.senderText("(Listening...)")
                query = takecommand()

            if not query:
                # Both attempts failed — stay in the loop silently
                _silent_loops += 1
                if _silent_loops == 1:
                    eel.DisplayMessage("I'm still here... / मैं सुन रहा हूं...")
                elif _silent_loops % 5 == 0:
                    eel.DisplayMessage("Listening... / सुन रहा हूं...")
                continue

            _silent_loops = 0  # reset silence counter

            # -- Exit keyword check: STOP listening ----------------------
            if _is_exit_command(query):
                _say(
                    "Okay, going to sleep. Press the mic or say Jarvis when you need me.",
                    "Okay, so raha hoon. Jab zaroorat ho mic dabao ya Jarvis bolo.",
                )
                eel.ShowHood()
                return

            print(f"Voice: {query}")
            eel.senderText(query)

            # Process the command
            _process_query(query, message)

            # Ready for next command
            eel.DisplayMessage("Listening... / सुन रहा हूं...")
    else:
        # ================================================================
        #  TYPED MODE  (single command)
        # ================================================================
        query = message
        print(f"Message: {query}")
        eel.senderText(query)

        if not query:
            speak("No command was given.")
            eel.ShowHood()
            return

        if _is_exit_command(query):
            speak("Okay, going to sleep.")
            eel.ShowHood()
            return

        _process_query(query, message)
        eel.ShowHood()


def _is_exit_command(query: str) -> bool:
    """Return True if *query* is a request to stop continuous listening."""
    q = query.lower().strip()
    if q in _CONTINUOUS_EXIT:
        return True
    for kw in _CONTINUOUS_EXIT:
        if " " in kw and kw in q:
            return True
    return False

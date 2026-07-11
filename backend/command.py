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


def _suppress_interfering_apps() -> None:
    """Silently close media players that intercept microphone events.

    MX Player and a few other media apps register as audio-device handlers
    on Windows.  When any app opens or closes a microphone stream (which
    Jarvis does on every voice command), these media players pop open a
    window, stealing focus.  We close them pre-emptively here.
    """
    import subprocess as _sp
    _interfering = [
        "MXPlayer.exe",
        "MXPlayer.exe",
        "PotPlayerMini64.exe",
        "PotPlayerMini.exe",
        "GOM.EXE",
        "GOM64.EXE",
    ]
    for proc in _interfering:
        try:
            _sp.run(
                ["taskkill", "/f", "/im", proc],
                capture_output=True,
                timeout=3,
            )
        except Exception:
            pass  # Not running — that's fine


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
#  Speech-to-text  (multi-language)
# ---------------------------------------------------------------------------

# Language models to try for Google Speech Recognition (in priority order).
#
# ``en-IN`` is tried FIRST because it handles Indian-accented English as well as
# Hinglish (Hindi+English code-switching) — the most common input for this app.
# ``en-US`` is the fallback for Western-accented English.
# ``hi-IN`` is the LAST resort for pure-Hindi input — it was formerly first but
# would often return garbled Devanagari for English/Hinglish speech instead of
# raising ``UnknownValueError``, so the English fallbacks were never reached.
_LANG_ATTEMPTS = [
    ("en-IN", "EN-IN"),
    ("en-US", "EN-US"),
    ("hi-IN", "HI"),
]


def takecommand(lang: str = "auto") -> str | None:
    """Listen to the microphone and return the recognised utterance.

    Attempts Google Speech Recognition across Hindi, Indian English, and US
    English models.  If Google's API is unreachable it falls back to offline
    PocketSphinx (when installed).

    Parameters
    ----------
    lang : str
        Ignored (kept for backward compatibility).  All three models are
        always tried in priority order.

    Returns
    -------
    str or None
        Lower-cased text, or ``None`` if recognition failed entirely.
    """
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 1

    # -- Suppress media players that interfere with the microphone ----------
    # MX Player (and some other media apps) register as audio-device handlers
    # and pop open whenever the microphone stream starts/stops.  Silently
    # close them before listening so they don't steal focus from Jarvis.
    _suppress_interfering_apps()

    # Set a sensible fallback energy threshold in case ``adjust_for_ambient_noise``
    # fails silently.  The dynamic calibration below will normally overwrite this,
    # but having a lower-than-default floor (300) avoids missing quiet speech on
    # mics where auto-calibration doesn't work well.
    recognizer.energy_threshold = 200

    # -- Step 1: capture audio from the microphone --------------------------
    try:
        with sr.Microphone() as source:
            print("I'm listening... (सुन रहा हूं...)")
            eel.DisplayMessage("I'm listening... / सुन रहा हूं...")

            # Calibrate for background noise.  A full second gives much
            # better results than the common 0.5 s snippet.
            recognizer.adjust_for_ambient_noise(source, duration=1.0)

            # ``timeout``  = max seconds to wait for the user to START speaking.
            # ``phrase_time_limit`` = max seconds of audio to capture once speech
            #   begins (raised from 5 → 10 for longer Hindi / Hinglish commands).
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)

    except sr.WaitTimeoutError:
        print("No speech detected within 10 seconds")
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

    # -- Step 2: transcribe the captured audio ------------------------------
    print("Recognizing...")
    eel.DisplayMessage("Recognizing...")

    query: str | None = None
    api_unreachable = False

    # Resolve the Google API key (if the user configured one)
    google_key = (
        config.GOOGLE_SPEECH_API_KEY.strip()
        if config.GOOGLE_SPEECH_API_KEY and config.GOOGLE_SPEECH_API_KEY.strip()
        else None
    )

    for lang_code, tag in _LANG_ATTEMPTS:
        try:
            kwargs: dict = {"language": lang_code}
            if google_key:
                kwargs["key"] = google_key

            result = recognizer.recognize_google(audio, **kwargs)

            # Guard against empty / whitespace-only results
            if result and result.strip():
                query = result.strip()
                print(f"[{tag}] User said: {query}")
                break  # success — don't try other languages
            # Empty string — treat as failure, try next language
            query = None

        except sr.UnknownValueError:
            # Speech audio was captured but Google couldn't make sense of it
            # in this language.  Perfectly normal — just try the next model.
            continue

        except sr.RequestError as exc:
            # Google's API returned an error (rate-limit, bad key, no internet…).
            # Don't waste time trying the remaining languages — they all use the
            # same API endpoint and will fail the same way.
            api_unreachable = True
            print(f"[{tag}] Google Speech API error: {exc}")
            break

    # -- Step 3: offline fallback (Sphinx) ----------------------------------
    if query is None and not api_unreachable:
        # Google didn't understand the audio in any language — try Sphinx
        # as a last resort (only if the user has pocketsphinx installed).
        try:
            query = recognizer.recognize_sphinx(audio)
            if query and query.strip():
                query = query.strip()
                print(f"[SPHINX] User said: {query}")
        except sr.UnknownValueError:
            pass
        except sr.RequestError:
            pass
        except Exception:
            # pocketsphinx probably not installed — that's fine
            pass

    # -- Step 4: report back to the user ------------------------------------
    if query is None:
        if api_unreachable:
            speak(
                "Speech recognition service is unavailable. "
                "Please check your internet connection, or add a Google API "
                "key in backend/config.py to avoid rate limits."
            )
        else:
            speak("Sorry, main samjha nahi. Dobara bolo.", "hi")
        return None

    eel.DisplayMessage(query)

    # Echo the recognised text back to the user
    try:
        has_hindi_chars = any(ord(c) > 127 for c in query)
        speak(query, "hi" if has_hindi_chars else "en")
    except Exception:
        pass

    return query.lower()


# ---------------------------------------------------------------------------
#  Command dispatcher  (exposed to Eel)
# ---------------------------------------------------------------------------

@eel.expose
def takeAllCommands(message: str | None = None) -> None:
    """The main command loop — voice or typed.

    Parameters
    ----------
    message : str or None
        If ``None``, the microphone is activated.  Otherwise *message* is
        treated as a typed command and routed the same way.
    """
    if message is None:
        query = takecommand()
        if not query:
            # First attempt failed — ask user to try once more
            speak("Main sun nahi paaya. Ek baar aur bolo.", "hi")
            eel.senderText("(Listening again...)")
            query = takecommand()
        if not query:
            # Both attempts failed — show hood and exit gracefully
            speak(
                "I couldn't hear anything. Please try again or type your command.",
            )
            eel.ShowHood()
            return
        print(f"Voice: {query}")
        eel.senderText(query)
    else:
        query = message
        print(f"Message: {query}")
        eel.senderText(query)

    # Guard against ``query`` being ``None`` or empty *after* the if/else
    if not query:
        speak("No command was given.")
        eel.ShowHood()
        return

    # ---- Detect language BEFORE transliteration overwrites query ----------
    global _last_query_hindi
    _last_query_hindi = any(ord(c) > 127 for c in query)

    try:
        # ---- Step 0: transliterate Hindi words to English equivalents ----
        q = query.lower()

        # IMPORTANT: longer phrases MUST come before shorter substrings.
        # Dict iteration order is insertion order (Python 3.7+), so put
        # multi-word phrases first.
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

        # Detect if the original query was in Hindi (has Devanagari chars).
        # ``_last_query_hindi`` was already set above and is used by the
        # module-level ``_say()`` helper to pick Hindi vs English responses.

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

        # Collapse multiple spaces from stripped words and trim
        import re as _re
        q = _re.sub(r"\s+", " ", q).strip()

        print(f"[CMD] Processing: {q}")

        # From this point onward, use the transliterated ``q`` as the
        # canonical command text.  The original ``query`` (which may still
        # contain Devanagari) was already displayed to the user via
        # ``senderText`` above — all downstream functions expect English.
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
        if any(kw in query for kw in search_keywords):
            from backend.feature import searchWeb
            searchWeb(query)
            eel.ShowHood()
            return

        # ==================================================================
        #  YOUTUBER / CHANNEL  search
        # ==================================================================
        channel_keywords = [
            "channel", "चैनल", "youtuber", "यूट्यूबर",
            "youtube channel", "ka channel", "ki channel",
        ]
        if any(kw in query for kw in channel_keywords):
            from backend.feature import openYoutuber
            openYoutuber(query)
            eel.ShowHood()
            return

        # ==================================================================
        #  OPEN / KHOLO  commands
        # ==================================================================
        open_keywords = [
            "open", "kholo", "खोलो", "khol", "खोल",
            "chalu karo", "start",
        ]
        if any(kw in query for kw in open_keywords):
            from backend.feature import openCommand
            openCommand(query)
            eel.ShowHood()
            return

        # ==================================================================
        #  PLAY / YOUTUBE  commands
        # ==================================================================
        play_keywords = [
            "on youtube", "play", "baja", "बजा", "chala", "चला",
            "gaana", "गाना", "youtube pe", "youtube par",
            "song", "music", "गाने",
        ]
        if any(kw in query for kw in play_keywords):
            from backend.feature import PlayYoutube
            PlayYoutube(query)
            eel.ShowHood()
            return

        # ==================================================================
        #  WHATSAPP / CALL / MESSAGE  commands
        # ==================================================================
        msg_keywords = [
            "send message", "message bhejo", "मैसेज", "message karo",
            "whatsapp", "call", "कॉल", "video call", "video कॉल",
        ]
        if any(kw in query for kw in msg_keywords):
            from backend.feature import findContact, whatsApp, openCommand

            # If the user JUST said "whatsapp" (no call/message/video),
            # open WhatsApp instead of searching contacts
            is_just_whatsapp = (
                "whatsapp" in query
                and not any(w in query for w in ("call", "message", "video", "कॉल", "मैसेज", "bhejo", "karo"))
            )
            if is_just_whatsapp:
                openCommand("open whatsapp")
                eel.ShowHood()
                return

            flag = ""
            phone, name = findContact(query)

            if phone != 0 and phone is not None:
                if any(w in query for w in ("send message", "message", "मैसेज")):
                    flag = "message"
                    if message is None:
                        # Voice mode — ask user to speak the message body
                        speak("Kya message bhejna hai? / What message to send?")
                        msg_text = takecommand()
                        if not msg_text:
                            speak("Message cancelled — no speech detected.")
                            eel.ShowHood()
                            return
                    else:
                        # Typing mode — extract message from the typed query
                        # Remove command words and contact name to get the message
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
                    eel.ShowHood()
                    return
                elif "video" in query:
                    flag = "video call"
                else:
                    flag = "call"
                whatsApp(phone, query, flag, name)

            eel.ShowHood()
            return

        # ==================================================================
        #  CAMERA  specific
        # ==================================================================
        camera_keywords = ["camera", "कैमरा", "photo", "फोटो", "selfie"]
        if any(kw in query for kw in camera_keywords):
            from backend.feature import openCommand
            openCommand("open camera")
            eel.ShowHood()
            return

        # ==================================================================
        #  TIME  command
        # ==================================================================
        time_keywords = ["time", "समय", "kitne baje"]
        if any(kw in query for kw in time_keywords):
            now = datetime.now().strftime("%I:%M %p")
            _say(f"Time is {now}", f"समय हुआ है {now}")
            eel.ShowHood()
            return

        # ==================================================================
        #  DATE  command
        # ==================================================================
        date_keywords = ["date", "तारीख", "aaj ki date"]
        if any(kw in query for kw in date_keywords):
            today = datetime.now().strftime("%d %B %Y")
            _say(f"Today's date is {today}", f"आज की तारीख है {today}")
            eel.ShowHood()
            return

        # ==================================================================
        #  FALLBACK  -- Web search (Google)
        # ==================================================================
        # If nothing matched and it's not a known command, search Google
        # so the user always gets relevant info instead of a dead end.
        from backend.feature import searchWeb
        searchWeb(query)

    except Exception as exc:
        print(f"Error in command dispatch: {exc}")
        traceback.print_exc()
        try:
            speak("Sorry, kuch galat ho gaya.")
        except Exception:
            pass

    eel.ShowHood()

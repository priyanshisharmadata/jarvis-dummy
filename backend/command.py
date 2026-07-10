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

import time
import traceback
from datetime import datetime

import eel
import pyttsx3
import speech_recognition as sr


# ---------------------------------------------------------------------------
#  Text-to-speech
# ---------------------------------------------------------------------------

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
    text = str(text)
    try:
        engine = pyttsx3.init("sapi5")
        voices = engine.getProperty("voices")

        if lang == "hi":
            # Prefer a Hindi voice when available
            hindi = [v for v in voices if "hindi" in v.name.lower()]
            if hindi:
                engine.setProperty("voice", hindi[0].id)
            elif voices:
                engine.setProperty("voice", voices[0].id)
        elif voices:
            engine.setProperty("voice", voices[0].id)

        engine.setProperty("rate", 170)
        eel.DisplayMessage(text)
        engine.say(text)
        engine.runAndWait()
    except Exception as exc:
        print(f"Speak error: {exc}")
        # Still try to show the message even if TTS fails
        try:
            eel.DisplayMessage(text)
        except Exception:
            pass


# ---------------------------------------------------------------------------
#  Speech-to-text  (multi-language)
# ---------------------------------------------------------------------------

def takecommand(lang: str = "auto") -> str | None:
    """Listen to the microphone and return the recognised utterance.

    Tries Google Speech Recognition with three language models in order:

    1. ``hi-IN``  (Hindi + English mixed / Hinglish)
    2. ``en-IN``  (Indian English)
    3. ``en-US``  (US English fallback)

    Returns
    -------
    str or None
        Lower-cased text, or ``None`` if recognition failed entirely.
    """
    recognizer = sr.Recognizer()

    try:
        with sr.Microphone() as source:
            print("I'm listening... (सुन रहा हूं...)")
            eel.DisplayMessage("I'm listening... / सुन रहा हूं...")
            recognizer.pause_threshold = 1
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=5)

        print("Recognizing...")
        eel.DisplayMessage("Recognizing...")

        query: str | None = None

        # Attempt 1 – Hindi/Hinglish
        try:
            query = recognizer.recognize_google(audio, language="hi-IN")
            print(f"[HI] User said: {query}")
        except Exception:
            pass

        # Attempt 2 – Indian English
        if query is None:
            try:
                query = recognizer.recognize_google(audio, language="en-IN")
                print(f"[EN-IN] User said: {query}")
            except Exception:
                pass

        # Attempt 3 – US English
        if query is None:
            try:
                query = recognizer.recognize_google(audio, language="en-US")
                print(f"[EN-US] User said: {query}")
            except Exception:
                pass

        if query is None:
            speak("Sorry, main samjha nahi. Dobara bolo.", "hi")
            return None

        eel.DisplayMessage(query)

        # Echo back in the appropriate language
        try:
            has_hindi_chars = any(ord(c) > 127 for c in query)
            speak(query, "hi" if has_hindi_chars else "en")
        except Exception:
            pass

        # FIX: The original code called ``query.lower()`` even when query
        #      could be ``None``.  Now we guard with the check above.
        return query.lower()

    except Exception as exc:
        print(f"Error in takecommand: {exc}")
        try:
            speak("Sorry, main samjha nahi. Dobara bolo.", "hi")
        except Exception:
            pass
        return None


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

    try:
        # ---- Step 0: transliterate Hindi words to English equivalents ----
        q = query.lower()

        hindi_to_eng = {
            "ओपन": "open", "खोलो": "open", "खोल": "open", "चालू करो": "open",
            "शुरू करो": "open", "स्टार्ट": "open", "लॉन्च": "open",
            "प्ले": "play", "बजा": "play", "बजाओ": "play", "चला": "play",
            "चलाओ": "play", "गाना": "play song", "गाने": "play song",
            "कैमरा": "camera", "कैम": "camera", "फोटो": "camera",
            "कैलकुलेटर": "calculator", "कैलक्यूलेटर": "calculator",
            "कैलेंडर": "calendar", "कलेंडर": "calendar",
            "यूट्यूब": "youtube", "यूट्यूब": "youtube",
            "व्हाट्सएप": "whatsapp", "वॉट्स्ऐप": "whatsapp",
            "मैसेज": "message", "मेसेज": "message", "सन्देश": "message",
            "कॉल": "call", "काल": "call", "फ़ोन": "call",
            "टाइम": "time", "समय": "time", "टाईम": "time",
            "डेट": "date", "तारीख": "date",
            "नोटपैड": "notepad", "क्रोम": "chrome", "एज": "edge",
            "सेटिंग": "settings", "सेटिंग्स": "settings",
            "एक्सेल": "excel", "वर्ड": "word", "पावरपॉइंट": "powerpoint",
            "म्यूजिक": "music", "वीडियो": "video", "विडियो": "video",
            "स्टोर": "store", "मौसम": "weather", "मेप": "maps",
        }

        for hi_word, eng_word in hindi_to_eng.items():
            if hi_word in q:
                q = q.replace(hi_word, eng_word)

        print(f"[CMD] Processing: {q}")

        # ==================================================================
        #  OPEN / KHOLO  commands
        # ==================================================================
        open_keywords = [
            "open", "kholo", "खोलो", "khol", "खोल",
            "chalu karo", "start",
        ]
        if any(kw in q for kw in open_keywords):
            from backend.feature import openCommand
            openCommand(query)  # pass original (case preserved)
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
        if any(kw in q for kw in play_keywords):
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
        if any(kw in q for kw in msg_keywords):
            from backend.feature import findContact, whatsApp

            flag = ""
            phone, name = findContact(query)

            if phone != 0 and phone is not None:
                if any(w in q for w in ("send message", "message", "मैसेज")):
                    flag = "message"
                    speak("Kya message bhejna hai? / What message to send?")
                    query = takecommand()
                elif "video" in q:
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
        if any(kw in q for kw in camera_keywords):
            from backend.feature import openCommand
            openCommand("open camera")
            eel.ShowHood()
            return

        # ==================================================================
        #  TIME  command
        # ==================================================================
        time_keywords = ["time", "समय", "kitne baje"]
        if any(kw in q for kw in time_keywords):
            now = datetime.now().strftime("%I:%M %p")
            speak(f"Time is {now}")
            eel.ShowHood()
            return

        # ==================================================================
        #  DATE  command
        # ==================================================================
        date_keywords = ["date", "तारीख", "aaj ki date"]
        if any(kw in q for kw in date_keywords):
            today = datetime.now().strftime("%d %B %Y")
            speak(f"Today's date is {today}")
            eel.ShowHood()
            return

        # ==================================================================
        #  FALLBACK  -- AI Chatbot (HuggingFace)
        # ==================================================================
        from backend.feature import chatBot
        chatBot(query)

    except Exception as exc:
        print(f"Error in command dispatch: {exc}")
        traceback.print_exc()
        try:
            speak("Sorry, kuch galat ho gaya.")
        except Exception:
            pass

    eel.ShowHood()

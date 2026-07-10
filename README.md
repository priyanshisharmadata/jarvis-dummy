# Jarvis -- AI Voice Assistant for Windows

_Your personal desktop assistant that speaks Hindi, English, and Hinglish._

> **Jarvis** is a voice-controlled AI assistant for Windows PCs inspired by Iron Man's J.A.R.V.I.S. It listens to your voice commands, opens apps, plays music on YouTube, sends WhatsApp messages, tells you the time/date, and even chats with you via an AI chatbot -- all through a sleek animated web UI. Built by Indian developers, for Indian developers.

---

## Table of Contents

1. [Project Overview](#-project-overview)
2. [Features at a Glance](#-features-at-a-glance)
3. [Architecture](#-architecture)
4. [Directory Structure](#-directory-structure)
5. [Tech Stack](#-tech-stack)
6. [Installation Guide](#-installation-guide)
7. [How to Run](#-how-to-run)
8. [Voice Commands Reference](#-voice-commands-reference)
   - [Opening Apps](#-opening-apps)
   - [Playing Music / YouTube](#-playing-music--youtube)
   - [WhatsApp Messaging & Calling](#-whatsapp-messaging--calling)
   - [Camera](#-camera)
   - [Time / Date](#-time--date)
   - [AI Chatbot](#-ai-chatbot)
   - [System Apps & Settings](#-system-apps--settings)
   - [Hindi Transliteration Table](#-hindi-transliteration-table)
9. [Keyboard Shortcuts](#-keyboard-shortcuts)
10. [Face Authentication](#-face-authentication)
11. [How to Add New Apps / Websites](#-how-to-add-new-apps--websites)
12. [How `pyaudio_wrapper` Works](#-how-pyaudio_wrapper-works)
13. [Troubleshooting Guide](#-troubleshooting-guide)
14. [All Known Bugs Fixed](#-all-known-bugs-fixed)
15. [Credits & License](#-credits--license)

---

## Project Overview

Jarvis is a **desktop voice assistant** that runs as a local web application. It uses **Python (Eel)** as the backend and a **browser-based UI (Edge in app mode)** as the frontend. You speak to it -- it talks back to you.

### How It Works (High-Level)

```
You Speak  -->  Google Speech Recognition  -->  Command Parser  -->  Feature Handler
   (mic)              (Hindi/EN-IN/EN-US)         (multi-lang)       (open/play/chat)
                                                                         |
                                                                         v
                                                                   Action Performed
                                                                   (app opens, YT plays,
                                                                    message sent, etc.)
```

### What Makes It Different

| Capability | Jarvis | Typical Voice Assistant |
|---|---|---|
| Multi-language (Hindi + English + Hinglish) | Yes | Rarely |
| Opens desktop apps (Chrome, VS Code, etc.) | Yes | No |
| WhatsApp automation (Web) | Yes | No |
| YouTube playback via voice | Yes | Partial |
| AI Chatbot fallback (HuggingFace) | Yes | Sometimes |
| Face authentication | Yes | No |
| Fully offline (except STT + chatbot) | Yes | Partial |
| Runs in a browser window (no install) | Yes | No |

---

## Features at a Glance

| # | Feature | Voice | Typed | Hindi Support |
|---|---|---|---|---|
| 1 | Open desktop apps | Yes | Yes | Yes |
| 2 | Open websites | Yes | Yes | Yes |
| 3 | Play songs on YouTube | Yes | Yes | Yes |
| 4 | Send WhatsApp messages | Yes | Yes | Yes |
| 5 | Make WhatsApp calls (voice/video) | Yes | Yes | Yes |
| 6 | Tell current time | Yes | Yes | Yes |
| 7 | Tell today's date | Yes | Yes | Yes |
| 8 | Open camera / take photo | Yes | Yes | Yes |
| 9 | AI Chatbot (HuggingFace) | Yes | Yes | Yes |
| 10 | Face authentication (optional) | -- | -- | -- |
| 11 | Hot-word wake ("Jarvis" / "Alexa") | -- | -- | -- |
| 12 | Keyboard shortcut activation | -- | -- | -- |

---

## Architecture

```
                        WINDOWS DESKTOP
+------------------------------------------------------------------+
|                                                                    |
|   +-------------------+         +---------------------------+     |
|   |   run.py          |         |   main.py                 |     |
|   |   (multi-process) |         |   (single entry point)    |     |
|   |                   |         |                           |     |
|   |  Process 1:       |         |  1. _find_free_port()    |     |
|   |   main.start()    |         |     -> port 8000+         |     |
|   |                   |         |                           |     |
|   |  Process 2:       |         |  2. eel.init("frontend")  |     |
|   |   hotword()       |         |                           |     |
|   +-------------------+         |  3. Opens Edge app window |     |
|                                 |     http://localhost:PORT  |     |
|                                 +-------------+-------------+     |
|                                               |                   |
|                    EEL BRIDGE (JS <-> Python)  |                   |
|                                               |                   |
|   +-------------------------------------------v-------------+     |
|   |                    backend/command.py                    |     |
|   |                                                          |     |
|   |  takeAllCommands(message)                                 |     |
|   |     |                                                     |     |
|   |     |-> takecommand() -- listens via mic (STT)            |     |
|   |     |   tries: hi-IN -> en-IN -> en-US                    |     |
|   |     |                                                     |     |
|   |     |-> Hindi-to-English transliteration                  |     |
|   |     |                                                     |     |
|   |     |-> Keyword routing:                                  |     |
|   |         |-> "open/kholo/..." -> feature.openCommand()     |     |
|   |         |-> "play/baja/..." -> feature.PlayYoutube()      |     |
|   |         |-> "message/call/..." -> feature.whatsApp()      |     |
|   |         |-> "time/date/..." -> speak(time/date)           |     |
|   |         |-> else           -> feature.chatBot()  (AI)     |
|   |                                                          |     |
|   +------------------+-------------------+------------------+     |
|                      |                   |                        |
|          +-----------v----+   +---------v--------+               |
|          | feature.py     |   | backend/db.py    |               |
|          |                 |   |                  |               |
|          | openCommand()   |   | SQLite tables:   |               |
|          | PlayYoutube()   |   |  - sys_command   |               |
|          | hotword()       |   |  - web_command   |               |
|          | findContact()   |   |  - contacts      |               |
|          | whatsApp()      |   +------------------+               |
|          | chatBot()       |                                      |
|          | playAssistant.. |    +---------------------+           |
|          +-----------------+    | pyaudio_wrapper.py  |           |
|                                 | (sounddevice fallback) |        |
|                                 +---------------------+           |
|                                                                    |
|   +----------------------------------------------------------+     |
|   |                     frontend/                              |     |
|   |                                                          |     |
|   |  index.html -- loading animation -> face auth -> main UI  |     |
|   |  main.js    -- button clicks, keyboard, text input        |     |
|   |  controller.js -- DisplayMessage(), ShowHood(), etc.      |     |
|   |  script.js  -- Canvas particle sphere animation           |     |
|   |  style.css  -- glowing buttons, hood animation, chat      |     |
|   +----------------------------------------------------------+     |
+------------------------------------------------------------------+

EXTERNAL SERVICES:
  Google Speech Recognition (STT)  -- speech-to-text
  HuggingFace Chat (hugchat)        -- AI chatbot fallback
  pywhatkit                         -- YouTube search & playback
```

### Data Flow Diagram

```
[User speaks "chrome kholo"]
        |
        v
[Microphone] --> [speech_recognition + Google STT]
        |
        v
["chrome kholo"] --> [Hindi transliterator: "kholo" -> "open"]
        |
        v
["chrome open"] --> [Command router: matches "open" keyword]
        |
        v
[openCommand("chrome open")]
        |
        v
[DB lookup: "chrome" in sys_command?] --YES--> [os.startfile("chrome.exe")]
        |                                         or
        NO                                      [subprocess: start chrome]
        |
        v
[Filesystem scan: Program Files, Start Menu, PATH]
        |
        v
[Found: C:\...\chrome.exe] --> [Launch + cache in DB]
```

---

## Directory Structure

```
jarvis-dummy/
|
|   # ===== ENTRY POINTS =====
|   main.py                  Entry point -- starts the Eel server + opens browser
|   run.py                   Multi-process launcher (UI + hot-word detection)
|   setup.bat                One-click Windows setup script
|   requirements.txt         All Python dependencies pinned
|   README.md                You are reading it!
|
+-- backend/
|   |   __init__.py          Makes backend a Python package
|   |   config.py            Global config: ASSISTANT_NAME = "jarvis"
|   |   command.py           Voice command engine + multi-language routing
|   |   feature.py           Feature implementations:
|   |   |                       - openCommand()     (app/website launcher)
|   |   |                       - PlayYoutube()     (YT search via pywhatkit)
|   |   |                       - hotword()         (wake-word detection)
|   |   |                       - findContact()     (contact lookup in DB)
|   |   |                       - whatsApp()        (WhatsApp web automation)
|   |   |                       - chatBot()         (HuggingFace AI fallback)
|   |   |                       - play_assistant_sound()
|   |   db.py                SQLite DB schema: sys_command, web_command, contacts
|   |   helper.py            Utilities: extract_yt_term(), remove_words()
|   |   pyaudio_wrapper.py   Pure-Python PyAudio replacement (uses sounddevice)
|   |   scan_apps.py         PC scanner -- populates DB with 100+ apps & websites
|   |
|   +-- auth/
|   |   |   __init__.py
|   |   |   recoganize.py    Face authentication runtime (LBPH + Haar cascade)
|   |   |   sample.py        Capture face samples from webcam
|   |   |   trainer.py       Train the LBPH face recognition model
|   |   |   haarcascade_frontalface_default.xml   OpenCV Haar cascade XML
|   |   |   samples/         (gitignored) Captured face images for training
|   |   |   trainer/         (gitignored) Output: trainer.yml model file
|
+-- frontend/
|   |   index.html           Main UI: loading screen + face auth + main interface
|   |   main.js              UI initialization, button bindings, keyboard shortcuts
|   |   controller.js        JS functions exposed to Python via Eel
|   |   script.js            Canvas 2D particle-sphere 3D animation
|   |   style.css            All styling: hood animation, glow buttons, chat bubbles
|   |
|   +-- assets/
|       |   audio/
|       |       start_sound.mp3     Startup chime (played when mic is clicked)
|       |   img/
|       |       logo.ico            Jarvis app icon
|       +-- vendore/texllate/
|               animate.css         Textillate CSS dependencies
|               jquery.fittext.js   Textillate JS vendor
|               jquery.lettering.js Textillate JS vendor
|               style.css           Textillate vendor styles
|
+-- .gitignore               Ignores: envJarvis/, jarvis.db, cookie.json, samples
+-- jarvis.db                (auto-created) SQLite database with app/contact data
```

---

## Tech Stack

### Backend (Python)

| Component | Library | Purpose |
|---|---|---|
| Web Server / Bridge | `eel >= 0.16.0` | Python-JS communication, serves the UI |
| Speech-to-Text | `speech_recognition >= 3.10.0` | Microphone input -> Google STT |
| Text-to-Speech | `pyttsx3 >= 2.90` | SAPI5 voices on Windows |
| Audio Capture | `sounddevice >= 0.4.6` + `numpy` | Clean PyAudio replacement (no C++ build) |
| Screen Automation | `pyautogui >= 0.9.54` + `pygetwindow` | WhatsApp Web keyboard/mouse automation |
| YouTube | `pywhatkit >= 5.4` | YouTube search and playback |
| Startup Sound | `pygame >= 2.5.0` | MP3 playback |
| Face Detection | `opencv-python >= 4.8.0` | Haar cascade + LBPH face recognition |
| Image Processing | `Pillow >= 10.0.0` | Face sample preprocessing |
| AI Chatbot | `hugchat >= 0.3.0` | HuggingFace Chat API |
| Hot-word Detection | `pvporcupine >= 3.0.0` (Win only) | "Jarvis" / "Alexa" wake words |
| Database | `sqlite3` (stdlib) | App paths, websites, contacts |

### Frontend (HTML/CSS/JS)

| Component | Library | Purpose |
|---|---|---|
| CSS Framework | Bootstrap 5.0.2 | Layout, icons, responsive design |
| Icons | Bootstrap Icons 1.11.1 | Mic, send, chat, settings icons |
| Particles | Canvas 2D API (custom) | 3D particle sphere animation |
| Animations | Textillate + Animate.css | Text bounce/fade animations |
| Waveform | SiriWave.js | Listening-state visualization |
| Lottie | lottie-player + dotlottie-player | Face auth loading animations |
| DOM | jQuery 3.6.4 | DOM manipulation, event handling |

### External Services

| Service | Used For | Requires Internet? |
|---|---|---|
| Google Speech Recognition | Speech-to-text conversion | Yes |
| HuggingFace Chat | AI chatbot fallback | Yes |
| YouTube (via pywhatkit) | Playing songs/videos | Yes |
| WhatsApp Web | Sending messages / making calls | Yes |

Everything else runs fully offline on your machine.

---

## Installation Guide

### Prerequisites

- **Windows 10 or 11** (64-bit)
- **Python 3.10 or newer** (tested up to 3.14)
- **A working microphone** (laptop built-in or external)
- **A working webcam** (optional, for face authentication)
- **Internet connection** (for speech recognition, YouTube, and chatbot)

### Step-by-Step Installation

#### Method 1: One-Click Setup (Recommended)

Open Command Prompt or PowerShell in the project folder and run:

```bat
setup.bat
```

This single command will:
1. Check that Python is installed and in PATH
2. Create a virtual environment called `envJarvis/`
3. Install all dependencies from `requirements.txt`
4. Scan your PC for apps and websites and populate the database
5. Print a success message with instructions to run

**Typical output:**
```
 ========================================
   Jarvis AI Assistant -- Setup
 ========================================

[INFO] Python found:
Python 3.12.0

[INFO] Creating virtual environment...
[INFO] Virtual environment created.

[INFO] Installing dependencies. This may take a few minutes...
... (pip output) ...

[INFO] Scanning your PC for apps and websites...
Scanning Program Files...
Scanning Start Menu...
Scanning PATH...
Adding Windows tools...
Adding popular apps...
Adding websites...

Done! 374 apps + 33 websites = 407 total entries in database

 ========================================
   Setup complete!

   To start Jarvis:
     envJarvis\Scripts\activate
     python main.py

   For hot-word wake (say "Jarvis"):
     python run.py
 ========================================
```

#### Method 2: Manual Setup (Step by Step)

```powershell
# Step 1: Clone or navigate to the project folder
cd jarvis-dummy

# Step 2: Create a virtual environment
python -m venv envJarvis

# Step 3: Activate the virtual environment
envJarvis\Scripts\activate

# Step 4: Upgrade pip (optional but recommended)
python -m pip install --upgrade pip

# Step 5: Install all dependencies
pip install -r requirements.txt

# Step 6: Scan your PC for apps and populate the database
python backend\scan_apps.py

# Step 7: (Optional) Set up face authentication
python backend\auth\sample.py      # Capture face samples
python backend\auth\trainer.py     # Train the model

# Step 8: (Optional) Set up AI chatbot
# 1. Log in at https://huggingface.co/chat
# 2. Export your session cookie as cookie.json
# 3. Place it in: jarvis-dummy\backend\cookie.json
```

#### Troubleshooting Installation Issues

| Problem | Solution |
|---|---|
| Python not found | Install Python from https://www.python.org/downloads/ and check "Add Python to PATH" |
| `pip` not recognized | Run `python -m pip install --upgrade pip` |
| `pyaudio` fails to install | No problem! The `pyaudio_wrapper` uses `sounddevice` instead. You can safely ignore pyaudio errors |
| `pvporcupine` fails | This is optional. Only needed for hot-word detection (`run.py`). If it fails, use `main.py` instead |
| `opencv-python` install hangs | Try `pip install opencv-python-headless` instead |
| Permission errors | Run Command Prompt as Administrator |

---

## How to Run

### Basic Mode -- Voice + Typed Commands

```powershell
# Activate the environment (if not already active)
envJarvis\Scripts\activate

# Launch Jarvis
python main.py
```

**What happens:** A Microsoft Edge window opens in app mode (no browser chrome) showing the Jarvis UI. The loading animation plays, then the main interface appears. Click the mic button or press **Ctrl+J** to start speaking.

### Hot-Word Mode -- Say "Jarvis" or "Alexa" to Wake

```powershell
# Activate the environment
envJarvis\Scripts\activate

# Launch with hot-word detection
python run.py
```

**What happens:** Two processes start simultaneously:
- **Process 1**: The Eel web UI (same as `main.py`)
- **Process 2**: A hot-word listener that continuously monitors your microphone for "Jarvis" or "Alexa". When detected, it presses **Win+J** to activate the assistant.

> **Note**: Hot-word mode requires `pvporcupine` to be installed. If it's not installed, Process 2 will print a warning and the UI will still work (just without wake-word detection).

### First-Time Experience

1. The loading screen appears with a spinning SVG animation
2. (If face auth is set up) The camera opens and scans your face
3. The main UI appears: a glowing blue particle sphere with a text input
4. Click the **microphone button** (or press **Ctrl+J**) and speak a command
5. Jarvis echoes your command and responds

---

## Voice Commands Reference

### How Speech Recognition Works

Jarvis uses Google's speech recognition with a three-stage language fallback:

```
hi-IN (Hindi + English mixed / Hinglish)
  |
  v (if that fails)
en-IN (Indian English)
  |
  v (if that fails)
en-US (US English)
```

This means you can mix Hindi and English freely in a single sentence and Jarvis will understand.

### Opening Apps

| English Command | Hindi / Hinglish Command | What Happens |
|---|---|---|
| "Open Chrome" | "Chrome kholo" / "क्रोम खोलो" | Launches Google Chrome |
| "Open VS Code" | "VS Code kholo" / "VS Code खोलो" | Launches Visual Studio Code |
| "Open Notepad" | "Notepad kholo" / "नोटपैड खोलो" | Opens Notepad |
| "Open Calculator" | "Calculator kholo" / "कैलकुलेटर खोलो" | Opens Windows Calculator |
| "Open Excel" | "Excel kholo" / "एक्सेल खोलो" | Opens Microsoft Excel |
| "Open Word" | "Word kholo" / "वर्ड खोलो" | Opens Microsoft Word |
| "Open PowerPoint" | "PowerPoint kholo" | Opens Microsoft PowerPoint |
| "Open Settings" | "Settings kholo" / "सेटिंग्स खोलो" | Opens Windows Settings |
| "Open File Explorer" | "Explorer kholo" | Opens File Explorer |
| "Open Command Prompt" | "CMD kholo" | Opens Command Prompt |
| "Open Control Panel" | "Control Panel kholo" | Opens Control Panel |
| "Open Task Manager" | "Task Manager kholo" | Opens Task Manager |
| "Open Discord" | "Discord kholo" | Opens Discord |
| "Open Spotify" | "Spotify kholo" | Opens Spotify |
| "Open Zoom" | "Zoom kholo" | Opens Zoom |
| "Open Telegram" | "Telegram kholo" | Opens Telegram |
| "Open VLC" | "VLC kholo" | Opens VLC Media Player |
| "Open Edge" | "Edge kholo" / "एज खोलो" | Opens Microsoft Edge |
| "Open Firefox" | "Firefox kholo" | Opens Firefox |
| "Open Brave" | "Brave kholo" | Opens Brave Browser |
| "Open Paint" | "Paint kholo" | Opens MS Paint |
| "Open Store" | "Store kholo" / "स्टोर खोलो" | Opens Microsoft Store |
| "Open Weather" | "Weather kholo" / "मौसम खोलो" | Opens Weather app |
| "Open Maps" | "Maps kholo" / "मेप खोलो" | Opens Maps app |
| "Open Photos" | "Photos kholo" | Opens Photos app |
| "Open Mail" | "Mail kholo" | Opens Mail app |
| "Open Clock" | "Clock kholo" | Opens Clock app |

**How app opening works (resolution order):**

1. **Exact DB match** -- looks for exact name in `sys_command` table
2. **Website DB match** -- looks for exact name in `web_command` table
3. **Windows `start` command** -- tries PATH-registered apps
4. **Filesystem scan** -- searches Program Files, Start Menu, AppData
5. **Fuzzy DB match** -- partial name match fallback
6. **Apologizes** -- "Sorry, couldn't find that app"

### Opening Websites

| English Command | Hindi / Hinglish | What Opens |
|---|---|---|
| "Open YouTube" | "YouTube kholo" / "यूट्यूब खोलो" | https://www.youtube.com |
| "Open Google" | "Google kholo" | https://www.google.com |
| "Open Gmail" | "Gmail kholo" | https://mail.google.com |
| "Open GitHub" | "GitHub kholo" | https://github.com |
| "Open Instagram" | "Instagram kholo" | https://www.instagram.com |
| "Open Facebook" | "Facebook kholo" | https://www.facebook.com |
| "Open WhatsApp Web" | "WhatsApp Web kholo" | https://web.whatsapp.com |
| "Open LinkedIn" | "LinkedIn kholo" | https://www.linkedin.com |
| "Open Amazon" | "Amazon kholo" | https://www.amazon.in |
| "Open Flipkart" | "Flipkart kholo" | https://www.flipkart.com |
| "Open Netflix" | "Netflix kholo" | https://www.netflix.com |
| "Open Hotstar" | "Hotstar kholo" | https://www.hotstar.com |
| "Open Prime Video" | "Prime Video kholo" | https://www.primevideo.com |
| "Open Reddit" | "Reddit kholo" | https://www.reddit.com |
| "Open Twitter" | "Twitter kholo" | https://www.twitter.com |
| "Open ChatGPT" | "ChatGPT kholo" | https://chat.openai.com |
| "Open Claude" | "Claude kholo" | https://claude.ai |
| "Open Wikipedia" | "Wikipedia kholo" | https://www.wikipedia.org |
| "Open Zomato" | "Zomato kholo" | https://www.zomato.com |
| "Open Swiggy" | "Swiggy kholo" | https://www.swiggy.com |
| "Open LeetCode" | "LeetCode kholo" | https://leetcode.com |
| "Open Stack Overflow" | "Stack Overflow kholo" | https://stackoverflow.com |
| "Open Canva" | "Canva kholo" | https://www.canva.com |
| "Open Notion" | "Notion kholo" | https://www.notion.so |
| "Open Cricbuzz" | "Cricbuzz kholo" | https://www.cricbuzz.com |
| "Open IRCTC" | "IRCTC kholo" | https://www.irctc.co.in |
| "Open Paytm" | "Paytm kholo" | https://paytm.com |
| "Open Translate" | "Translate kholo" | https://translate.google.com |
| "Open Drive" | "Drive kholo" | https://drive.google.com |
| "Open HackerRank" | "HackerRank kholo" | https://www.hackerrank.com |

### Playing Music / YouTube

| English Command | Hindi / Hinglish | What Happens |
|---|---|---|
| "Play Believer on YouTube" | "Believer baja do YouTube pe" | Searches YouTube and plays Believer |
| "Play [song name] on YouTube" | "[song name] bajao" / "[song name] गाना बजाओ" | Plays the top YouTube result |
| "Play music" | "Gaana baja" / "गाना बजाओ" | Plays music on YouTube |
| "Play [song]" | "[song] chalao" / "[song] चलाओ" | Plays the song on YouTube |
| "Play song [name]" | "Gaana chala [name]" | Plays the named song |

**How it works:**
1. `extract_yt_term()` strips trigger words ("play", "baja", "gaana", "on youtube", etc.)
2. The remaining text is passed to `pywhatkit.playonyt()`
3. Your default browser opens the top YouTube result

### WhatsApp Messaging & Calling

| English Command | Hindi / Hinglish | What Happens |
|---|---|---|
| "Send message to Mom" | "Mom ko message bhejo" / "माँ को मैसेज भेजो" | Opens WhatsApp Web -> asks for message -> sends to Mom |
| "Send message to Dad" | "Dad ko message karo" | Opens WhatsApp Web -> asks for message -> sends to Dad |
| "Call Mom" | "Mom ko call karo" / "माँ को कॉल करो" | Opens WhatsApp Web -> initiates voice call to Mom |
| "Video call Mom" | "Mom ko video call karo" | Opens WhatsApp Web -> initiates video call to Mom |
| "WhatsApp Mom" | "WhatsApp Mom" | Opens WhatsApp chat with Mom |

**Prerequisites for WhatsApp features:**
1. Contacts must be added to the `contacts` table in `jarvis.db`
2. WhatsApp Web must be logged in on your default browser

**How it works:**
1. `findContact()` searches the contacts table for a name match
2. `whatsApp()` constructs a `whatsapp://send?phone=...` URL
3. Uses `pyautogui` to automate keyboard navigation on WhatsApp Web
4. For calls: `Ctrl+F` to find contact -> Tab to message box -> Enter
5. For messages: Opens the send URL, types and sends the message

### Camera

| English Command | Hindi / Hinglish | What Happens |
|---|---|---|
| "Open Camera" | "Camera kholo" / "कैमरा खोलो" | Opens Windows Camera app |
| "Camera" | "कैमरा" | Opens Windows Camera app |
| "Take photo" | "Photo lo" / "फोटो खींचो" | Opens Windows Camera app |
| "Selfie" | "Selfie" | Opens Windows Camera app |

### Time / Date

| English Command | Hindi / Hinglish | Response |
|---|---|---|
| "What is the time?" | "Time batao" / "समय बताओ" / "Kitne baje hain?" | "Time is 03:45 PM" |
| "What is today's date?" | "Aaj ki date batao" / "तारीख बताओ" | "Today's date is 10 July 2026" |
| "Time" | "Samay" / "टाइम" | Current time spoken aloud |
| "Date" | "Tarikh" / "डेट" | Today's date spoken aloud |

### AI Chatbot

| English Command | Hindi / Hinglish | What Happens |
|---|---|---|
| "Who is the Prime Minister of India?" | "Bharat ke PM kaun hain?" | HuggingFace chatbot answers |
| "Explain quantum computing" | "Quantum computing samjhao" | HuggingFace chatbot explains |
| "Write a Python script to sort a list" | "Ek Python script likho" | HuggingFace chatbot generates code |
| "Tell me a joke" | "Ek joke sunao" | HuggingFace chatbot tells a joke |
| "What is the capital of France?" | "France ki capital kya hai?" | HuggingFace chatbot answers |

Any command not matching the known keywords (open, play, message, call, camera, time, date) is automatically forwarded to the AI chatbot.

**Prerequisites:**
1. Log in at https://huggingface.co/chat
2. Export your browser's session cookie as `cookie.json`
3. Place the file at: `jarvis-dummy/backend/cookie.json`

Without `cookie.json`, the chatbot gracefully disables itself and says: "Chatbot needs a HuggingFace cookie."

### System Apps & Settings

| English Command | What Opens |
|---|---|
| "Open Device Manager" | Device Manager (`devmgmt.msc`) |
| "Open Disk Management" | Disk Management (`diskmgmt.msc`) |
| "Open Registry Editor" | Registry Editor (`regedit`) |
| "Open System Information" | System Information (`msinfo32`) |
| "Open Services" | Services manager (`services.msc`) |
| "Open Bluetooth settings" | Windows Bluetooth settings |
| "Open WiFi settings" | Windows WiFi settings |
| "Open Display settings" | Windows Display settings |
| "Open Sound settings" | Windows Sound settings |
| "Open Windows Update" | Windows Update |
| "Open Snipping Tool" | Snipping Tool / Screen Sketch |
| "Open Sticky Notes" | Sticky Notes |
| "Open Terminal" | Windows Terminal |
| "Open PowerShell" | PowerShell |
| "Open WordPad" | WordPad |
| "Open Media Player" | Windows Media Player |

### Hindi Transliteration Table

The command parser converts these Hindi/Devanagari words to English before routing:

| Hindi Input | English Equivalent | Triggered Feature |
|---|---|---|
| `खोलो`, `खोल`, `ओपन` | `open` | App/website opener |
| `चालू करो`, `शुरू करो`, `स्टार्ट` | `open` | App/website opener |
| `प्ले`, `बजा`, `बजाओ`, `चला`, `चलाओ` | `play` | YouTube playback |
| `गाना`, `गाने` | `play song` | YouTube playback |
| `कैमरा`, `कैम`, `फोटो` | `camera` | Camera launcher |
| `कैलकुलेटर` | `calculator` | App opener |
| `कैलेंडर` | `calendar` | App opener |
| `यूट्यूब` | `youtube` | Website opener |
| `व्हाट्सएप`, `वॉट्स्ऐप` | `whatsapp` | WhatsApp feature |
| `मैसेज`, `मेसेज`, `सन्देश` | `message` | WhatsApp messenger |
| `कॉल`, `काल`, `फ़ोन` | `call` | WhatsApp caller |
| `टाइम`, `समय` | `time` | Time teller |
| `डेट`, `तारीख` | `date` | Date teller |
| `नोटपैड` | `notepad` | App opener |
| `क्रोम` | `chrome` | App opener |
| `एज` | `edge` | App opener |
| `सेटिंग`, `सेटिंग्स` | `settings` | App opener |
| `एक्सेल` | `excel` | App opener |
| `वर्ड` | `word` | App opener |
| `पावरपॉइंट` | `powerpoint` | App opener |
| `म्यूजिक` | `music` | YouTube playback |
| `वीडियो`, `विडियो` | `video` | YouTube playback |
| `स्टोर` | `store` | App opener |
| `मौसम` | `weather` | App opener |
| `मेप` | `maps` | App opener |

---

## Keyboard Shortcuts

| Shortcut | Action | Context |
|---|---|---|
| **Ctrl + J** | Activate voice recognition | Anytime the main UI is visible |
| **Win + J** | Activate voice recognition | Same as above (Windows key variant) |
| **Enter** | Submit typed command | When text is typed in the chat input |
| **ESC** | Stop face authentication | During face recognition loop |
| **Click Mic Button** | Start listening via microphone | Main UI |
| **Click Send Button** | Send typed command | When text is present in input |
| **Click Chat Button** | Return to main UI from wave view | Wave/listening view |

The Win+J shortcut is the one triggered automatically by the hot-word listener (when using `run.py`). Both Ctrl+J and Win+J are handled identically by `main.js`.

---

## Face Authentication

Jarvis includes an optional face authentication system using **OpenCV's LBPH (Local Binary Patterns Histograms)** algorithm and **Haar cascade** face detection.

### How It Works

```
                        TRAINING PHASE
+-------------------------------------------------------------+
|                                                             |
|  1. sample.py                                              |
|     Webcam -> Detect face -> Crop to grayscale             |
|     -> Save as face.{id}.{count}.jpg                       |
|     -> 100 images per person                               |
|                                                             |
|  2. trainer.py                                             |
|     Read all face.{id}.{count}.jpg                         |
|     -> Detect faces in each image                          |
|     -> Extract LBPH features                               |
|     -> Train LBPH recognizer                               |
|     -> Save model as trainer.yml                           |
|                                                             |
+-------------------------------------------------------------+

                        RUNTIME PHASE
+-------------------------------------------------------------+
|                                                             |
|  3. recoganize.py                                          |
|     Open webcam                                             |
|     -> For every frame:                                     |
|        -> Convert to grayscale                              |
|        -> Detect faces (Haar cascade)                       |
|        -> For each face:                                    |
|           -> recognizer.predict(face_roi)                   |
|           -> Returns (person_id, confidence)                |
|           -> If confidence < 100: MATCH -> return 1         |
|           -> Else: UNKNOWN -> continue scanning             |
|     -> ESC key quits                                        |
|                                                             |
+-------------------------------------------------------------+
```

### Step-by-Step Setup

#### Step 1: Capture Face Samples

```powershell
python backend\auth\sample.py
```

You will be prompted:
```
Enter a numeric user ID here: 1
Taking samples, look at camera .......
```

- The webcam opens and captures your face in grayscale
- 100 samples are automatically collected (about 10 seconds)
- Each sample is saved as `backend/auth/samples/face.1.1.jpg`, `face.1.2.jpg`, ... `face.1.100.jpg`
- Press **ESC** to stop early if you want fewer samples
- For multiple users, run the script again with a different ID (2, 3, ...)

#### Step 2: Train the Model

```powershell
python backend\auth\trainer.py
```

Output:
```
Training faces. It will take a few seconds. Wait ...
Model trained and saved to backend\auth\trainer\trainer.yml
Now you can recognize your face with recoganize.py
```

#### Step 3: Test Recognition (Optional)

The `AuthenticateFace()` function in `recoganize.py` opens the webcam and runs detection. You can test it by importing:

```python
from backend.auth.recoganize import AuthenticateFace
result = AuthenticateFace()  # Returns 1 if recognized, 0 if not
```

#### Step 4: Customizing Names

Edit the `names` list in `backend/auth/recoganize.py`:

```python
# Default:
names = ["", "Person 1", "Person 2", "Person 3", "Person 4", "Person 5"]

# After training yourself with ID=1 and your friend with ID=2:
names = ["", "Priya", "Ankit", "Person 3", "Person 4", "Person 5"]
```

### Important Notes

- The `samples/` and `trainer/` directories are **gitignored**. Your face data stays on your machine
- LBPH works best with frontal, well-lit faces. Avoid extreme angles or shadows
- The accuracy threshold is set to `< 100` (lower is better in OpenCV LBPH). If you get false rejections, increase this threshold
- The haarcascade XML file is included in the repo (`backend/auth/haarcascade_frontalface_default.xml`)

---

## How to Add New Apps / Websites

### Method 1: Add to the Database Manually

Use any SQLite tool (or Python) to insert rows into `jarvis.db`:

```sql
-- Add a new desktop app
INSERT INTO sys_command (name, path)
VALUES ('obsidian', 'C:\\Users\\YourName\\AppData\\Local\\Obsidian\\Obsidian.exe');

-- Add a new website
INSERT INTO web_command (name, url)
VALUES ('jira', 'https://your-company.atlassian.net');
```

Or with Python:

```python
import sqlite3
conn = sqlite3.connect("jarvis.db")
cursor = conn.cursor()

# Add an app
cursor.execute(
    "INSERT OR IGNORE INTO sys_command (name, path) VALUES (?, ?)",
    ("obsidian", r"C:\Users\YourName\AppData\Local\Obsidian\Obsidian.exe")
)

# Add a website
cursor.execute(
    "INSERT OR IGNORE INTO web_command (name, url) VALUES (?, ?)",
    ("jira", "https://your-company.atlassian.net")
)

conn.commit()
conn.close()
```

Now you can say: **"Open Obsidian"** or **"Open Jira"**.

### Method 2: Re-run the Scanner

The scanner in `scan_apps.py` automatically discovers hundreds of apps. Re-run it anytime:

```powershell
python backend\scan_apps.py
```

It scans:
1. Program Files `.exe` files
2. Start Menu `.lnk` shortcuts
3. PATH executables
4. Windows built-in tools (Control Panel, Settings, etc.)
5. Popular apps (Chrome, VS Code, Notion, Discord, etc.)
6. Common websites

### Method 3: Add to the Scanner (for permanent inclusion)

Edit `backend/scan_apps.py` and add your app to the `popular` list:

```python
popular = [
    # ... existing entries ...
    ("my app", "myapp"),            # PATH-based app
    ("obsidian", "obsidian"),       # PATH-based app
]
```

Or add a new website to the `sites` list:

```python
sites = [
    # ... existing entries ...
    ("jira", "https://your-company.atlassian.net"),
    ("slack", "https://slack.com"),
]
```

### Method 4: Custom Trigger Words (Hindi/Hinglish)

To add a Hindi trigger word for your app, edit `backend/command.py` and add to the `hindi_to_eng` dictionary:

```python
hindi_to_eng = {
    # ... existing entries ...
    "जीरा": "jira",     # so "jira kholo" or "जीरा खोलो" both work
}
```

### How the Resolution System Works

When you say "Open [app_name]", Jarvis tries these 6 steps in order:

```
Step 1: Exact DB match
  SELECT path FROM sys_command WHERE LOWER(name) = '[app_name]'
  -> If found: launch immediately

Step 2: Website match
  SELECT url FROM web_command WHERE LOWER(name) = '[app_name]'
  -> If found: open in browser

Step 3: Windows 'start' command
  start "" "[app_name]"
  -> If the app is in PATH: it launches

Step 4: Filesystem scan
  Search: Program Files, Start Menu, AppData
  -> If found: launch AND cache in DB for next time

Step 5: Fuzzy DB match
  SELECT ... WHERE LOWER(name) LIKE '%app_name%'
  -> If partial match found: launch

Step 6: Apology
  "Sorry, couldn't find [app_name]"
```

This means even if an app is not in the database, Jarvis has a good chance of finding it through filesystem scanning.

---

## How `pyaudio_wrapper` Works

### The Problem

The original `pyaudio` library requires **PortAudio C++ libraries and a C++ compiler** to install on Windows. This is a major headache, especially on Python 3.12+ where pre-compiled wheels may not be available. Many users get errors like:

```
error: Microsoft Visual C++ 14.0 or greater is required
```

### The Solution

`pyaudio_wrapper.py` is a **drop-in replacement** for `pyaudio` that uses `sounddevice` (a pure-Python library with pre-compiled wheels for all platforms) under the hood. It requires **zero C++ build tools**.

### How It Works -- Monkey Patching

```python
# In feature.py (and anywhere else that needs PyAudio):

try:
    import pyaudio         # Try the real library first
except ImportError:
    from backend import pyaudio_wrapper   # Falls back to wrapper
    import pyaudio          # Now resolves to the wrapper!
```

The trick is in the last lines of `pyaudio_wrapper.py`:

```python
# Monkey-patch sys.modules so that 'import pyaudio' resolves to this wrapper
try:
    import pyaudio
except ImportError:
    import sounddevice as sd

    fake_module = type(sys)("pyaudio")   # Create a fake module object
    fake_module.PyAudio = PyAudio         # Attach our wrapper class
    fake_module.paInt16 = paInt16         # Format constants
    fake_module.paInt32 = paInt32
    fake_module.get_sample_size = get_sample_size
    sys.modules["pyaudio"] = fake_module  # Register in sys.modules
```

After this runs, **any subsequent `import pyaudio`** in the same Python process resolves to the wrapper -- completely transparently.

### What's Implemented (the Subset Jarvis Actually Uses)

| PyAudio API | Implemented in Wrapper? | Notes |
|---|---|---|
| `pyaudio.PyAudio()` | Yes | Factory class with `open()`, `terminate()` |
| `PyAudio.open()` | Yes | Returns a `Stream` wrapper around `sounddevice.InputStream` |
| `PyAudio.terminate()` | Yes | Stops and clears all streams |
| `PyAudio.get_device_count()` | Yes | Number of audio devices |
| `PyAudio.get_default_input_device_info()` | Yes | Default mic metadata |
| `PyAudio.get_device_info_by_index()` | Yes | Device metadata by index |
| `Stream.read(num_frames)` | Yes | Reads PCM audio, returns `bytes` |
| `Stream.is_stopped()` | Yes | Returns stream state |
| `Stream.stop_stream()` | Yes | Stops the stream |
| `Stream.close()` | Yes | Stops and releases |
| `pyaudio.paInt16` | Yes | Format constant (= 2) |
| `pyaudio.paInt32` | Yes | Format constant (= 8) |
| `pyaudio.get_sample_size()` | Yes | Byte size of format |

### Built-in Safety Features

1. **Device index out-of-range protection:**
   ```python
   if device is not None and device >= device_count:
       print(f"Device index {device} out of range, falling back to default")
       device = None
   ```

2. **Graceful read failures:**
   ```python
   except sd.CallbackStop:
       return b"\x00" * (num_frames * sample_size)  # Silence instead of crash
   ```

3. **Stream cleanup on terminate:**
   ```python
   def terminate(self):
       for s in self._streams:
           try: s.stop()
           except: pass
       self._streams.clear()
   ```

### Installing the Wrapper

The wrapper is already in the project. Its dependencies are in `requirements.txt`:

```
sounddevice>=0.4.6
numpy>=1.24.0
```

Both install cleanly on **Windows, macOS, and Linux** without any build tools. The wrapper activates automatically when real `pyaudio` is not found.

---

## Troubleshooting Guide

### Voice Recognition Issues

| Problem | Likely Cause | Solution |
|---|---|---|
| Mic not picking up voice | Wrong microphone selected | Check Windows sound settings: set the correct input device as default |
| "Sorry, main samjha nahi" repeated | Poor audio quality or heavy accent | Speak clearly, reduce background noise, move closer to mic |
| Recognition very slow | Poor internet connection | Google STT needs internet; check your connection |
| Hindi words not recognized | Pronunciation or speed | Speak at moderate speed; try Hinglish (mix Hindi + English) |
| Exact words spoken but wrong action | Homonyms or ambiguity | Be more specific: "open Google Chrome" vs "open chrome" |

### Python / Dependency Issues

| Problem | Likely Cause | Solution |
|---|---|---|
| `ModuleNotFoundError: No module named 'eel'` | Environment not activated | Run `envJarvis\Scripts\activate` first |
| `ImportError: pyaudio` errors on macOS | pyaudio build fails | The wrapper auto-loads. Make sure `sounddevice` and `numpy` are installed |
| `ModuleNotFoundError: No module named 'sounddevice'` | Missing dependency | `pip install sounddevice numpy` |
| `pip install` fails on some packages | Build tools missing | Most are optional. `pyaudio` is not needed; `pvporcupine` is optional |
| `pygame` fails to play sound | Missing audio codec | Install `playsound` as fallback: `pip install playsound` |

### App/Website Opening Issues

| Problem | Likely Cause | Solution |
|---|---|---|
| "Sorry, couldn't find [app]" | App not in DB and not in PATH | Run `python backend\scan_apps.py` or add manually |
| App opens but wrong version | Multiple installs, wrong path in DB | Check DB: `SELECT * FROM sys_command WHERE name='appname'` |
| Website opens in wrong browser | Default browser setting | Change Windows default browser, or use Edge (it's hardcoded for UI) |
| UWP app doesn't open | `os.startfile()` doesn't work on UWP | UWP apps use `shell:appsFolder` syntax; scanner adds these correctly |

### WhatsApp Issues

| Problem | Likely Cause | Solution |
|---|---|---|
| Contact not found | Contact not in database | Add to `contacts` table in `jarvis.db` |
| WhatsApp Web not opening | Not logged in | Log in to web.whatsapp.com first in your default browser |
| Message not typed correctly | pyautogui timing issue | The script uses `time.sleep(5)` -- slower PCs may need longer delay |
| "Video call" vs "call" confusion | Keyword matching | Say clearly: "video call Mom" vs "call Mom" |

### Face Authentication Issues

| Problem | Likely Cause | Solution |
|---|---|---|
| Face not detected | Poor lighting or camera angle | Good frontal lighting, face the camera directly |
| Always returns "unknown" | Model not trained or trained poorly | Re-train with more samples, better lighting |
| `trainer.yml not found` | Training not run | Run `python backend\auth\trainer.py` |
| Camera doesn't open | Webcam in use by another app | Close other camera apps (Zoom, Teams, etc.) |
| `cv2.face` not found | Missing opencv-contrib | Install: `pip install opencv-contrib-python` |

### Port / Startup Issues

| Problem | Likely Cause | Solution |
|---|---|---|
| Port already in use | Another instance running | The app auto-scans for free ports (8000+), or kill the old process |
| Edge window doesn't open | Edge not installed | Falls back to default browser via `webbrowser.open()` |
| White screen, no UI | Eel or JS error | Check the terminal for Python tracebacks; ensure `eel` is installed |
| `hotword()` crashes immediately | `pvporcupine` not installed | Optional. Use `python main.py` instead of `python run.py` |

### Performance

| Problem | Likely Cause | Solution |
|---|---|---|
| UI animation lags | GPU rendering | The Canvas particle animation is lightweight; try reducing browser windows |
| Memory usage grows over time | Python process leak | The app is designed for short sessions; restart if needed |
| CPU usage high when idle | Hot-word listener running | Use `main.py` (no hot-word) instead of `run.py` for lower CPU usage |

---

## All Known Bugs Fixed

This is a cleaned-up fork of the original [AI-assistant-for-pc](https://github.com/ankitpathak62/AI-assistant-for-pc) project. The following bugs were present in the original codebase and have been fixed:

| # | Bug | Severity | Original Behavior | Fix Applied |
|---|---|---|---|---|
| 1 | **Hardcoded absolute paths** | Critical | `C:\Users\patha\OneDrive\Desktop\...` hardcoded everywhere; project only worked on the original author's PC | All paths resolved relative to `__file__` using `os.path.dirname(os.path.abspath(__file__))` |
| 2 | **`cookie_path` used bare string** | Critical | `cookie_path="backend\\cookie.json"` -- crashed when CWD was not the project root | Uses `os.path.join(_ROOT, "backend", "cookie.json")` where `_ROOT` is the project root |
| 3 | **`None` passed to `.lower()`** | Critical | `query.lower()` called after failed speech recognition when `query` was `None` -> `AttributeError` | Added `if not query: return` guard before `.lower()` and all string operations |
| 4 | **`results[0][0]` without empty check** | Critical | `findContact()` indexed `results[0][0]` without verifying any rows were returned -> `IndexError: list index out of range` | Added `if not results: speak("not found"); return 0, 0` guard |
| 5 | **Port 8000 always hardcoded** | High | `eel.start(..., port=8000)` -- crashed if anything else was using port 8000 | `_find_free_port()` function scans from port 8000 upward, returns first available port |
| 6 | **PyAudio required C++ build tools** | High | `pyaudio` installation failed on Windows without Visual C++ 14.0+ build tools | Created `pyaudio_wrapper.py` -- a drop-in `sounddevice`-based replacement that monkey-patches `sys.modules` |
| 7 | **Device index out of range** | High | `pyaudio.PyAudio().open(input_device_index=N)` with invalid index -> `sounddevice.PortAudioError` | Wrapper validates `device < device_count` before opening, falls back to default device |
| 8 | **`start /B` command injection risk** | Medium | Raw `os.system(f'start /B {app_name}')` without quoting -> command injection | Switched to `subprocess.run(f'start /B "" "{app_name}"', shell=True, capture_output=True, timeout=5)` |
| 9 | **Unused imports** | Low | `compileall` imported in `feature.py` but never used; `from sys import flags` in `recoganize.py` unused | Removed all unused imports |
| 10 | **`youtube pe` regex too narrow** | Medium | Original `extract_yt_term()` only matched `"play ... on youtube"` exactly; Hinglish commands like `"baja de Believer"` failed | Rewrote with multiple patterns + filler-word stripping |
| 11 | **`contacts` table creation optional** | Low | `db.py` only created `sys_command` and `web_command` tables; `contacts` table creation was commented out | Added explicit `contacts` table creation in `db.py` schema |
| 12 | **No `freeze_support()` on Windows multiprocessing** | Medium | `run.py` used `multiprocessing.Process` without `freeze_support()` -- could cause issues on frozen executables | Added `multiprocessing.freeze_support()` at the top of `run.py`'s `__main__` block |
| 13 | **Edge process not cleaned up** | Low | Browser window left open when Python process exited | Edge runs as a child process; closing the terminal also closes the Edge app window |

---

## Credits & License

This project is a thoroughly refactored, documented, and bug-fixed version of:

> [AI-assistant-for-pc](https://github.com/ankitpathak62/AI-assistant-for-pc) by Ankit Pathak

Major improvements in this version:
- All hardcoded `C:\Users\patha\...` paths replaced with relative resolution
- Critical `None` and empty-list crashes fixed
- Auto port discovery instead of hardcoded port 8000
- Pure-Python `pyaudio_wrapper` eliminating C++ build dependency
- Comprehensive inline docstrings and type hints
- Full multi-language command reference documentation
- Proper multiprocessing with `freeze_support()`
- Device index validation preventing audio crashes

The original project was created by Indian developers and this fork maintains that spirit -- built for the Indian developer community, with first-class Hindi and Hinglish support.

---

**Made with passion in India.** If you have questions, ideas, or want to contribute, open an issue or PR on the repository.

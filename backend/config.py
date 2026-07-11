"""
Central configuration for the Jarvis assistant.

Change the assistant name here and it will be used everywhere — voice prompts,
command parsing, hot-word detection, etc.
"""

ASSISTANT_NAME = "jarvis"

# ---------------------------------------------------------------------------
# Google Speech Recognition API key (optional)
# ---------------------------------------------------------------------------
# The ``speech_recognition`` library ships with a hard-coded demo key that is
# heavily rate-limited and may fail with ``RequestError`` when many users hit
# it simultaneously.  Set your own key here to avoid that problem.
#
# 1. Go to https://console.cloud.google.com/apis/credentials
# 2. Create an API key (restrict to "Speech-to-Text" if you like)
# 3. Paste it below
#
# Leave empty to use the library default (may be unreliable).
GOOGLE_SPEECH_API_KEY: str = ""

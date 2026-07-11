"""
Central configuration for the Jarvis assistant.

Change the assistant name here and it will be used everywhere — voice prompts,
command parsing, hot-word detection, etc.
"""

ASSISTANT_NAME = "jarvis"

# ---------------------------------------------------------------------------
# Google Speech Recognition API key (STRONGLY RECOMMENDED)
# ---------------------------------------------------------------------------
# The ``speech_recognition`` library ships with a hard-coded demo key that is
# shared by every user of the library worldwide.  It is heavily rate-limited
# and will fail with ``RequestError`` after only a few voice commands,
# especially during peak hours.
#
# **Without a key, speech recognition WILL be unreliable.**  If Jarvis can
# understand typed commands but not your voice, this is the #1 reason.
#
# Getting a key takes ~2 minutes and is FREE (Google gives 60 min/month):
#
# 1. Go to https://console.cloud.google.com/apis/credentials
# 2. Click "+ CREATE CREDENTIALS" → "API key"
# 3. (Optional) Restrict the key to "Cloud Speech-to-Text API"
# 4. Copy the key and paste it below between the quotes
#
# Example:  GOOGLE_SPEECH_API_KEY = "AIzaSyD...your-key-here..."
#
# Leave empty to use the library default (will be unreliable).
GOOGLE_SPEECH_API_KEY: str = ""

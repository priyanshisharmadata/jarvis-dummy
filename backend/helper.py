"""
Utility helpers used across the Jarvis backend.
"""

import re


def extract_yt_term(command: str) -> str:
    """Pull the search term from a *"play X on youtube"* command.

    Practically all of the original bugs boiled down to the regex being too
    narrow — it would only match ``"play … on youtube"`` exactly.  Hindi /
    Hinglish phrases like ``"gaana baja de"``, ``"bajao X youtube pe"`` came
    through with the trigger words already stripped by the time this function
    was called, but the regex still expected the word "play" and the phrase
    "on youtube".  This version is much more liberal.

    Returns
    -------
    str
        The extracted search term, or the original *command* string (stripped)
        if no YouTube-specific pattern matched.
    """
    command = command.strip()

    # Pattern 1 – canonical English:  "play <song> on youtube"
    m = re.search(r"play\s+(.*?)\s+on\s+youtube", command, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Pattern 2 – "play <song>" without explicit "on youtube" but we know
    #            we are already inside PlayYoutube because of keyword match.
    m = re.search(r"play\s+(.*)", command, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Pattern 3 – Hindi / Hinglish patterns the command parser already
    #            transliterated into English keywords.  We strip known
    #            COMMAND words (not content words like "song", "music").
    #
    #            Strategy: first remove multi-word command phrases, then
    #            remove single-word command verbs.  Content nouns (song,
    #            music, gaana) are NOT stripped because they could be
    #            part of the actual search term.

    # Phase 1 — multi-word command phrases (longest first)
    command_phrases = [
        "youtube pe", "youtube par", "on youtube",
        "search karo", "play karo", "play kar",
        "baja de", "baja do", "bajao na",
        "chala de", "chala do", "chalao na",
        "karo search", "search kar",
    ]
    term = command
    for cp in command_phrases:
        term = re.sub(re.escape(cp), "", term, flags=re.IGNORECASE)

    # Phase 2 — single-word command verbs (only words that are clearly
    #           commands, not content)
    command_words = [
        "play", "baja", "bajao", "bajana",
        "chala", "chalao", "chalana",
        "karo", "karna", "kar",
        "sunao", "sunana", "dikhao",
        "gaane", "gane",             # "gaane/gane" = songs (plural, filler)
                                     # "gaana/gana" stays — it could be "Gaana.com" or a song name
        "na",                        # Hindi filler: "baja de na", "chala do na"
        "to",                        # "play to", "baja to"
        "बजाओ", "चलाओ", "करो", "सुनाओ", "दिखाओ",
        "गाने",
    ]
    for cw in command_words:
        term = re.sub(rf"\b{re.escape(cw)}\b", "", term, flags=re.IGNORECASE)

    # Clean up extra whitespace
    term = re.sub(r"\s+", " ", term).strip()

    return term if term else command


def remove_words(input_string: str, words_to_remove: list) -> str:
    """Return *input_string* with every word in *words_to_remove* erased
    (case-insensitive), preserving original spacing as much as possible."""
    words = input_string.split()
    remove_set = {w.lower() for w in words_to_remove}
    filtered = [w for w in words if w.lower() not in remove_set]
    return " ".join(filtered)

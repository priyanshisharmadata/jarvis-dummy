"""
App & website scanner for Jarvis.
=================================

Run this script once after installation to populate the SQLite database with
every app, shortcut, and website that Jarvis should be able to open.

Usage::

    python backend/scan_apps.py

The script scans:

1. Program Files directories for ``.exe`` files.
2. The Start Menu for ``.lnk`` shortcuts.
3. ``%PATH%`` executables.
4. Built-in Windows tools and UWP apps.
5. Popular third-party apps by common names.
6. Common websites (YouTube, Gmail, GitHub, etc.).

Every entry is inserted with ``INSERT OR IGNORE`` / ``INSERT OR REPLACE`` so
re-running is safe and idempotent.
"""

import glob
import os
import sqlite3
import subprocess
import sys

# -- Relative database path -----------------------------------------------
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_ROOT, "jarvis.db")


def _ensure_tables(cursor: sqlite3.Cursor) -> None:
    """Create the core tables if they don't already exist."""
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS sys_command (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100),
            path VARCHAR(1000)
        )"""
    )
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS web_command (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100),
            url VARCHAR(1000)
        )"""
    )


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    _ensure_tables(cursor)
    count = 0

    # 1. Program Files .exe files (shallow walk)
    print("Scanning Program Files...")
    for base in [r"C:\Program Files", r"C:\Program Files (x86)"]:
        if not os.path.exists(base):
            continue
        for root, dirs, files in os.walk(base):
            depth = root.replace(base, "").count(os.sep)
            if depth > 2:
                dirs.clear()
                continue
            for f in files:
                if f.endswith(".exe"):
                    name = os.path.splitext(f)[0].lower()
                    path = os.path.join(root, f)
                    try:
                        cursor.execute(
                            "INSERT OR IGNORE INTO sys_command (name, path) VALUES (?, ?)",
                            (name, path),
                        )
                        count += 1
                    except Exception:
                        pass

    # 2. Start Menu .lnk shortcuts
    print("Scanning Start Menu...")
    start_menu_bases = [
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
    ]
    for base in start_menu_bases:
        if not os.path.exists(base):
            continue
        for lnk in glob.glob(f"{base}/**/*.lnk", recursive=True):
            name = os.path.splitext(os.path.basename(lnk))[0].lower()
            if len(name) < 2:
                continue
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO sys_command (name, path) VALUES (?, ?)",
                    (name, lnk),
                )
                count += 1
            except Exception:
                pass

    # 3. PATH executables
    print("Scanning PATH...")
    try:
        result = subprocess.run(
            ["where", "*"], capture_output=True, text=True, shell=True, timeout=15
        )
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line.endswith(".exe"):
                name = os.path.splitext(os.path.basename(line))[0].lower()
                if len(name) >= 2:
                    try:
                        cursor.execute(
                            "INSERT OR IGNORE INTO sys_command (name, path) VALUES (?, ?)",
                            (name, line),
                        )
                        count += 1
                    except Exception:
                        pass
    except (subprocess.TimeoutExpired, Exception):
        print("PATH scan skipped (timeout or error)")

    # 4. Windows built-in tools
    print("Adding Windows tools...")
    windows_apps = [
        ("control panel", "control"),
        ("device manager", "devmgmt.msc"),
        ("disk management", "diskmgmt.msc"),
        ("task manager", "taskmgr"),
        ("system information", "msinfo32"),
        ("registry editor", "regedit"),
        ("msconfig", "msconfig"),
        ("services", "services.msc"),
        ("bluetooth", "ms-settings:bluetooth"),
        ("wifi", "ms-settings:network-wifi"),
        ("display settings", "ms-settings:display"),
        ("sound settings", "ms-settings:sound"),
        ("windows update", "ms-settings:windowsupdate"),
        ("camera", "shell:appsFolder\\Microsoft.WindowsCamera_8weky3b3d8bbwe!App"),
        ("calculator", "shell:appsFolder\\Microsoft.WindowsCalculator_8weky3b3d8bbwe!App"),
        ("calendar", "shell:appsFolder\\Microsoft.WindowsCalendar_8weky3b3d8bbwe!App"),
        ("photos", "shell:appsFolder\\Microsoft.Windows.Photos_8weky3b3d8bbwe!App"),
        ("settings", "shell:appsFolder\\windows.immersivecontrolpanel_cw5n1h2txyewy!microsoft.windows.immersivecontrolpanel"),
        ("mail", "shell:appsFolder\\microsoft.windowscommunicationsapps_8weky3b3d8bbwe!microsoft.windowslive.mail"),
        ("store", "shell:appsFolder\\Microsoft.WindowsStore_8weky3b3d8bbwe!App"),
        ("clock", "shell:appsFolder\\Microsoft.WindowsAlarms_8weky3b3d8bbwe!App"),
        ("weather", "shell:appsFolder\\Microsoft.BingWeather_8weky3b3d8bbwe!App"),
        ("snipping tool", "shell:appsFolder\\Microsoft.ScreenSketch_8weky3b3d8bbwe!App"),
        ("notepad", "notepad"),
        ("paint", "mspaint"),
        ("wordpad", "write"),
        ("file explorer", "explorer"),
        ("command prompt", "cmd"),
        ("powershell", "powershell"),
        ("task manager", "taskmgr"),
    ]
    for name, path in windows_apps:
        cursor.execute(
            "INSERT OR REPLACE INTO sys_command (name, path) VALUES (?, ?)",
            (name, path),
        )
        count += 1

    # 5. Popular third-party apps
    print("Adding popular apps...")
    popular = [
        ("vlc", "vlc"), ("notepad++", "notepad++"), ("spotify", "spotify"),
        ("discord", "discord"), ("zoom", "zoom"), ("telegram", "telegram"),
        ("blender", "blender"), ("git bash", "git-bash"), ("steam", "steam"),
        ("obs studio", "obs64"), ("whatsapp", "whatsapp"),
        ("sublime text", "sublime_text"), ("sublime", "sublime_text"),
        ("winrar", "winrar"), ("winzip", "winzip32"),
        ("pdf reader", "acrord32"), ("adobe reader", "acrord32"),
        ("adobe acrobat", "acrord32"), ("chrome", "chrome"),
        ("firefox", "firefox"), ("opera", "opera"), ("brave", "brave"),
        ("edge", "msedge"), ("internet explorer", "iexplore"),
        ("media player", "wmplayer"), ("groove music", "groove"),
        ("movies and tv", "ms-video"), ("snip and sketch", "ms-screensketch"),
        ("sticky notes", "stikynot"), ("xbox", "xbox"),
        ("terminal", "wt"), ("powershell", "powershell"),
        ("file explorer", "explorer"), ("explorer", "explorer"),
        ("command prompt", "cmd"), ("cmd", "cmd"),
        ("vs code", "code"), ("visual studio code", "code"),
        ("excel", "excel"), ("word", "winword"),
        ("powerpoint", "powerpnt"), ("outlook", "outlook"),
        ("onenote", "onenote"),
    ]
    for name, path in popular:
        cursor.execute(
            "INSERT OR IGNORE INTO sys_command (name, path) VALUES (?, ?)",
            (name, path),
        )
        count += 1

    # 6. Websites
    print("Adding websites...")
    sites = [
        ("youtube", "https://www.youtube.com"),
        ("google", "https://www.google.com"),
        ("gmail", "https://mail.google.com"),
        ("github", "https://github.com"),
        ("whatsapp web", "https://web.whatsapp.com"),
        ("instagram", "https://www.instagram.com"),
        ("facebook", "https://www.facebook.com"),
        ("twitter", "https://www.twitter.com"),
        ("linkedin", "https://www.linkedin.com"),
        ("reddit", "https://www.reddit.com"),
        ("amazon", "https://www.amazon.in"),
        ("flipkart", "https://www.flipkart.com"),
        ("netflix", "https://www.netflix.com"),
        ("hotstar", "https://www.hotstar.com"),
        ("prime video", "https://www.primevideo.com"),
        ("spotify web", "https://open.spotify.com"),
        ("chatgpt", "https://chat.openai.com"),
        ("claude", "https://claude.ai"),
        ("maps", "https://maps.google.com"),
        ("translate", "https://translate.google.com"),
        ("drive", "https://drive.google.com"),
        ("photos", "https://photos.google.com"),
        ("canva", "https://www.canva.com"),
        ("notion", "https://www.notion.so"),
        ("stack overflow", "https://stackoverflow.com"),
        ("wikipedia", "https://www.wikipedia.org"),
        ("zomato", "https://www.zomato.com"),
        ("swiggy", "https://www.swiggy.com"),
        ("irctc", "https://www.irctc.co.in"),
        ("paytm", "https://paytm.com"),
        ("cricbuzz", "https://www.cricbuzz.com"),
        ("leetcode", "https://leetcode.com"),
        ("hackerrank", "https://www.hackerrank.com"),
    ]
    for name, url in sites:
        cursor.execute(
            "INSERT OR IGNORE INTO web_command (name, url) VALUES (?, ?)",
            (name, url),
        )
        count += 1

    conn.commit()

    # Summary
    app_count = cursor.execute("SELECT COUNT(*) FROM sys_command").fetchone()[0]
    site_count = cursor.execute("SELECT COUNT(*) FROM web_command").fetchone()[0]
    print(f"\nDone! {app_count} apps + {site_count} websites = {app_count + site_count} total entries in database")

    print("\n--- Top 25 Apps ---")
    for row in cursor.execute(
        "SELECT name, path FROM sys_command WHERE name NOT LIKE '% %' LIMIT 25"
    ):
        print(f"  {row[0]:25s} -> {row[1][:55]}")

    conn.close()


if __name__ == "__main__":
    main()

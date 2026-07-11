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
    # Contacts table — synced with db.py schema
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY,
            name VARCHAR(200),
            Phone VARCHAR(255),
            email VARCHAR(255)
        )"""
    )


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
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
            ("camera", "shell:appsFolder\\Microsoft.WindowsCamera_8wekyb3d8bbwe!App"),
            ("calculator", "shell:appsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"),
            ("calendar", "shell:appsFolder\\Microsoft.WindowsCalendar_8wekyb3d8bbwe!App"),
            ("photos", "shell:appsFolder\\Microsoft.Windows.Photos_8wekyb3d8bbwe!App"),
            ("settings", "shell:appsFolder\\windows.immersivecontrolpanel_cw5n1h2txyewy!microsoft.windows.immersivecontrolpanel"),
            ("mail", "shell:appsFolder\\microsoft.windowscommunicationsapps_8wekyb3d8bbwe!microsoft.windowslive.mail"),
            ("store", "shell:appsFolder\\Microsoft.WindowsStore_8wekyb3d8bbwe!App"),
            ("clock", "shell:appsFolder\\Microsoft.WindowsAlarms_8wekyb3d8bbwe!App"),
            ("weather", "shell:appsFolder\\Microsoft.BingWeather_8wekyb3d8bbwe!App"),
            ("snipping tool", "shell:appsFolder\\Microsoft.ScreenSketch_8wekyb3d8bbwe!App"),
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

        # 6. Websites — comprehensive list across all major categories
        print("Adding websites...")
        sites = [
            # -- Search Engines --
            ("google", "https://www.google.com"),
            ("bing", "https://www.bing.com"),
            ("yahoo", "https://www.yahoo.com"),
            ("duckduckgo", "https://duckduckgo.com"),
            ("perplexity", "https://www.perplexity.ai"),
            # -- Social Media --
            ("facebook", "https://www.facebook.com"),
            ("instagram", "https://www.instagram.com"),
            ("twitter", "https://www.twitter.com"),
            ("linkedin", "https://www.linkedin.com"),
            ("reddit", "https://www.reddit.com"),
            ("snapchat", "https://www.snapchat.com"),
            ("pinterest", "https://www.pinterest.com"),
            ("tumblr", "https://www.tumblr.com"),
            ("threads", "https://www.threads.net"),
            ("quora", "https://www.quora.com"),
            ("whatsapp web", "https://web.whatsapp.com"),
            ("telegram web", "https://web.telegram.org"),
            ("discord", "https://discord.com/app"),
            # -- Video / Streaming --
            ("youtube", "https://www.youtube.com"),
            ("youtube music", "https://music.youtube.com"),
            ("netflix", "https://www.netflix.com"),
            ("prime video", "https://www.primevideo.com"),
            ("hotstar", "https://www.hotstar.com"),
            ("sony liv", "https://www.sonyliv.com"),
            ("zee5", "https://www.zee5.com"),
            ("jiocinema", "https://www.jiocinema.com"),
            ("mx player", "https://www.mxplayer.in"),
            ("twitch", "https://www.twitch.tv"),
            ("vimeo", "https://vimeo.com"),
            ("dailymotion", "https://www.dailymotion.com"),
            ("crunchyroll", "https://www.crunchyroll.com"),
            # -- Music --
            ("spotify", "https://open.spotify.com"),
            ("gaana", "https://gaana.com"),
            ("jiosaavn", "https://www.jiosaavn.com"),
            ("wynk music", "https://wynk.in/music"),
            ("soundcloud", "https://soundcloud.com"),
            ("hungama", "https://www.hungama.com"),
            # -- E-Commerce India --
            ("amazon", "https://www.amazon.in"),
            ("flipkart", "https://www.flipkart.com"),
            ("meesho", "https://www.meesho.com"),
            ("myntra", "https://www.myntra.com"),
            ("ajio", "https://www.ajio.com"),
            ("nykaa", "https://www.nykaa.com"),
            ("snapdeal", "https://www.snapdeal.com"),
            ("tatacliq", "https://www.tatacliq.com"),
            ("jiomart", "https://www.jiomart.com"),
            ("bigbasket", "https://www.bigbasket.com"),
            ("blinkit", "https://www.blinkit.com"),
            ("olx", "https://www.olx.in"),
            ("indiamart", "https://www.indiamart.com"),
            ("ebay", "https://www.ebay.com"),
            ("lenskart", "https://www.lenskart.com"),
            ("croma", "https://www.croma.com"),
            ("reliance digital", "https://www.reliancedigital.in"),
            # -- Food --
            ("zomato", "https://www.zomato.com"),
            ("swiggy", "https://www.swiggy.com"),
            ("dominos", "https://www.dominos.co.in"),
            # -- Travel --
            ("irctc", "https://www.irctc.co.in"),
            ("makemytrip", "https://www.makemytrip.com"),
            ("goibibo", "https://www.goibibo.com"),
            ("yatra", "https://www.yatra.com"),
            ("redbus", "https://www.redbus.in"),
            ("booking.com", "https://www.booking.com"),
            ("airbnb", "https://www.airbnb.com"),
            ("oyo", "https://www.oyorooms.com"),
            ("ixigo", "https://www.ixigo.com"),
            ("uber", "https://www.uber.com"),
            ("ola", "https://www.olacabs.com"),
            # -- Finance --
            ("paytm", "https://paytm.com"),
            ("google pay", "https://pay.google.com"),
            ("phonepe", "https://www.phonepe.com"),
            ("paypal", "https://www.paypal.com"),
            ("zerodha", "https://zerodha.com"),
            ("groww", "https://groww.in"),
            ("upstox", "https://upstox.com"),
            ("coinbase", "https://www.coinbase.com"),
            ("binance", "https://www.binance.com"),
            ("policybazaar", "https://www.policybazaar.com"),
            # -- Banking --
            ("sbi", "https://www.onlinesbi.sbi"),
            ("hdfc bank", "https://www.hdfcbank.com"),
            ("icici bank", "https://www.icicibank.com"),
            ("axis bank", "https://www.axisbank.com"),
            # -- Productivity --
            ("gmail", "https://mail.google.com"),
            ("google drive", "https://drive.google.com"),
            ("google docs", "https://docs.google.com"),
            ("google sheets", "https://sheets.google.com"),
            ("google slides", "https://slides.google.com"),
            ("google photos", "https://photos.google.com"),
            ("google calendar", "https://calendar.google.com"),
            ("google meet", "https://meet.google.com"),
            ("google maps", "https://maps.google.com"),
            ("translate", "https://translate.google.com"),
            ("notion", "https://www.notion.so"),
            ("evernote", "https://evernote.com"),
            ("trello", "https://trello.com"),
            ("asana", "https://asana.com"),
            ("slack", "https://slack.com"),
            ("microsoft teams", "https://teams.microsoft.com"),
            ("zoom", "https://zoom.us"),
            ("onedrive", "https://onedrive.live.com"),
            ("dropbox", "https://www.dropbox.com"),
            ("canva", "https://www.canva.com"),
            ("figma", "https://www.figma.com"),
            # -- AI / Chat --
            ("chatgpt", "https://chat.openai.com"),
            ("claude", "https://claude.ai"),
            ("gemini", "https://gemini.google.com"),
            ("copilot", "https://copilot.microsoft.com"),
            ("deepseek", "https://chat.deepseek.com"),
            ("midjourney", "https://www.midjourney.com"),
            ("grammarly", "https://www.grammarly.com"),
            # -- Development --
            ("github", "https://github.com"),
            ("gitlab", "https://gitlab.com"),
            ("stack overflow", "https://stackoverflow.com"),
            ("leetcode", "https://leetcode.com"),
            ("hackerrank", "https://www.hackerrank.com"),
            ("codechef", "https://www.codechef.com"),
            ("geeksforgeeks", "https://www.geeksforgeeks.org"),
            ("w3schools", "https://www.w3schools.com"),
            ("mdn", "https://developer.mozilla.org"),
            ("codeforces", "https://codeforces.com"),
            ("codepen", "https://codepen.io"),
            ("replit", "https://replit.com"),
            ("vercel", "https://vercel.com"),
            ("kaggle", "https://www.kaggle.com"),
            ("huggingface", "https://huggingface.co"),
            ("colab", "https://colab.research.google.com"),
            # -- News --
            ("google news", "https://news.google.com"),
            ("bbc", "https://www.bbc.com"),
            ("cnn", "https://www.cnn.com"),
            ("ndtv", "https://www.ndtv.com"),
            ("times of india", "https://timesofindia.indiatimes.com"),
            ("the hindu", "https://www.thehindu.com"),
            ("indian express", "https://indianexpress.com"),
            ("inshorts", "https://www.inshorts.com"),
            ("moneycontrol", "https://www.moneycontrol.com"),
            ("economic times", "https://economictimes.indiatimes.com"),
            # -- Education --
            ("coursera", "https://www.coursera.org"),
            ("udemy", "https://www.udemy.com"),
            ("edx", "https://www.edx.org"),
            ("khan academy", "https://www.khanacademy.org"),
            ("byjus", "https://byjus.com"),
            ("unacademy", "https://unacademy.com"),
            ("physics wallah", "https://www.pw.live"),
            ("duolingo", "https://www.duolingo.com"),
            ("ncert", "https://ncert.nic.in"),
            # -- Jobs --
            ("naukri", "https://www.naukri.com"),
            ("indeed", "https://www.indeed.com"),
            ("internshala", "https://internshala.com"),
            ("upwork", "https://www.upwork.com"),
            ("fiverr", "https://www.fiverr.com"),
            # -- Sports --
            ("cricbuzz", "https://www.cricbuzz.com"),
            ("espncricinfo", "https://www.espncricinfo.com"),
            ("espn", "https://www.espn.com"),
            ("ipl", "https://www.iplt20.com"),
            # -- Government --
            ("aadhaar", "https://uidai.gov.in"),
            ("passport seva", "https://www.passportindia.gov.in"),
            ("income tax", "https://www.incometax.gov.in"),
            ("digilocker", "https://www.digilocker.gov.in"),
            # -- Health --
            ("practo", "https://www.practo.com"),
            ("1mg", "https://www.1mg.com"),
            ("pharmeasy", "https://pharmeasy.in"),
            # -- Real Estate / Cars --
            ("magicbricks", "https://www.magicbricks.com"),
            ("99acres", "https://www.99acres.com"),
            ("housing", "https://housing.com"),
            ("cardekho", "https://www.cardekho.com"),
            ("carwale", "https://www.carwale.com"),
            # -- Entertainment --
            ("imdb", "https://www.imdb.com"),
            ("bookmyshow", "https://in.bookmyshow.com"),
            ("steam", "https://store.steampowered.com"),
            # -- Cloud --
            ("aws", "https://aws.amazon.com"),
            ("google cloud", "https://cloud.google.com"),
            ("microsoft azure", "https://azure.microsoft.com"),
            ("firebase", "https://firebase.google.com"),
            ("digitalocean", "https://www.digitalocean.com"),
            ("godaddy", "https://www.godaddy.com"),
            ("hostinger", "https://www.hostinger.in"),
            # -- Utility --
            ("wikipedia", "https://www.wikipedia.org"),
            ("speedtest", "https://www.speedtest.net"),
            ("weather", "https://weather.com"),
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

    finally:
        conn.close()


if __name__ == "__main__":
    main()

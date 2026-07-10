"""
Multi-process launcher for Jarvis.

Runs the Eel UI server in one process and the hot-word listener in another.

Usage::

    python run.py
"""

import multiprocessing


def startJarvis() -> None:
    """Launch the Eel UI server (process 1)."""
    print("Process 1 Starting (UI)...")
    from main import start
    start()


def listenHotword() -> None:
    """Launch the hot-word listener (process 2)."""
    print("Process 2 Starting (Hotword)...")
    from backend.feature import hotword
    hotword()


if __name__ == "__main__":
    multiprocessing.freeze_support()

    p1 = multiprocessing.Process(target=startJarvis)
    p2 = multiprocessing.Process(target=listenHotword)

    p1.start()
    p2.start()

    p1.join()

    if p2.is_alive():
        p2.terminate()
        print("Process 2 terminated.")
        p2.join()

    print("System terminated.")

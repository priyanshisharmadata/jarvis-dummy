"""
Multi-process launcher for Jarvis.

Runs the Eel UI server in one process and the hot-word listener in another.
If the hot-word process crashes it is automatically restarted.

Usage::

    python run.py
"""

import multiprocessing
import time


def startJarvis() -> None:
    """Launch the Eel UI server (process 1)."""
    print("Process 1 Starting (UI)...")
    from main import start
    start()


def listenHotword() -> None:
    """Launch the hot-word listener (process 2) with auto-restart."""
    print("Process 2 Starting (Hotword)...")
    from backend.feature import hotword
    hotword()


if __name__ == "__main__":
    multiprocessing.freeze_support()

    p1 = multiprocessing.Process(target=startJarvis)
    p1.start()

    # Hot-word process with auto-restart on crash
    _MAX_HOTWORD_RESTARTS = 5
    _restarts = 0

    while True:
        if not p1.is_alive():
            print("UI process exited — shutting down")
            break

        p2 = multiprocessing.Process(target=listenHotword)
        p2.start()
        print(f"Hotword process started (PID: {p2.pid})")

        p2.join()  # wait for hotword process to exit (crash or normal)

        if not p1.is_alive():
            print("UI process exited while hotword was running")
            if p2.is_alive():
                p2.terminate()
                p2.join()
            break

        _restarts += 1
        if _restarts > _MAX_HOTWORD_RESTARTS:
            print(
                f"Hotword process crashed {_restarts} times — "
                "giving up. Jarvis will still work with mic button."
            )
            break

        print(
            f"Hotword process crashed — restarting "
            f"(attempt {_restarts}/{_MAX_HOTWORD_RESTARTS})..."
        )
        time.sleep(1)  # brief pause before restart

    p1.join()
    print("System terminated.")

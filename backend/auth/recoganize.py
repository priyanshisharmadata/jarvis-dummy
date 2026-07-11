"""
Face-authentication runtime.
=============================

Opens the webcam, detects faces, and compares them against the trained
LBPH model to decide whether the user is authorised.

Requires
--------
* ``opencv-python`` (cv2)
* ``pyautogui``
* A trained model at ``backend/auth/trainer/trainer.yml``
* The haarcascade XML at ``backend/auth/haarcascade_frontalface_default.xml``
"""

import os
import time
import traceback

import cv2
import pyautogui as p

# LBPH confidence threshold.  Lower values = stricter matching.
# 0   → perfect match (only in laboratory conditions)
# 50  → good match (typical for well-lit, front-facing images)
# 100 → loose match (tolerates pose / lighting variance)
_CONFIDENCE_THRESHOLD = 100


def AuthenticateFace() -> int:
    """Run the face-auth loop.

    Returns
    -------
    int
        1 if the user was recognised successfully, 0 otherwise.
    """
    # Resolve paths relative to this file
    _here = os.path.dirname(os.path.abspath(__file__))
    trainer_path = os.path.join(_here, "trainer", "trainer.yml")
    cascade_path = os.path.join(_here, "haarcascade_frontalface_default.xml")

    recognizer = cv2.face.LBPHFaceRecognizer_create()

    # Load the trained model (fail gracefully if missing)
    if not os.path.exists(trainer_path):
        print(f"[AUTH] trainer.yml not found at {trainer_path}. "
              "Run trainer.py first.")
        return 0

    recognizer.read(trainer_path)

    # Initialise Haar cascade
    faceCascade = cv2.CascadeClassifier(cascade_path)
    font = cv2.FONT_HERSHEY_SIMPLEX

    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cam.isOpened():
        print("[AUTH] Cannot open webcam")
        return 0

    cam.set(3, 640)   # width
    cam.set(4, 480)   # height

    minW = int(0.1 * cam.get(3))
    minH = int(0.1 * cam.get(4))

    flag = 0
    win_name = "Face Authentication"

    try:
        while True:
            ret, img = cam.read()
            if not ret:
                print("[AUTH] Camera read failed")
                break

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            faces = faceCascade.detectMultiScale(
                gray,
                scaleFactor=1.2,
                minNeighbors=5,
                minSize=(minW, minH),
            )

            for (x, y, w, h) in faces:
                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)

                person_id, confidence = recognizer.predict(
                    gray[y:y + h, x:x + w]
                )

                if confidence < _CONFIDENCE_THRESHOLD:
                    # Confidence is LOW → good match (LBPH returns distance)
                    label = f"Person {person_id}"
                    match_pct = round(100 - confidence)
                    flag = 1
                else:
                    label = "unknown"
                    match_pct = round(100 - min(confidence, 100))
                    flag = 0

                cv2.putText(img, str(label), (x + 5, y - 5), font, 1,
                            (255, 255, 255), 2)
                cv2.putText(img, f"  {match_pct}%", (x + 5, y + h - 5),
                            font, 1, (255, 255, 0), 1)

            cv2.imshow(win_name, img)

            key = cv2.waitKey(10) & 0xFF
            if key == 27:   # ESC
                break
            if flag == 1:
                time.sleep(1.5)  # let the user see the match
                break

    except Exception as exc:
        print(f"[AUTH] Error: {exc}")
        traceback.print_exc()
    finally:
        cam.release()
        # Destroy only our own window, not every OpenCV window on the system
        try:
            cv2.destroyWindow(win_name)
        except Exception:
            pass

    return flag

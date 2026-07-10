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

import cv2
import pyautogui as p


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

    # ID -> name mapping (index 1 = first trained person, etc.)
    # The original used id=2 but that corresponds to the *second* person.
    # We keep the list extensible so you can add more names.
    names = ["", "Person 1", "Person 2", "Person 3", "Person 4", "Person 5"]

    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cam.set(3, 640)   # width
    cam.set(4, 480)   # height

    minW = int(0.1 * cam.get(3))
    minH = int(0.1 * cam.get(4))

    flag = 0

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

            person_id, accuracy = recognizer.predict(gray[y:y + h, x:x + w])

            if accuracy < 100:
                label = names[person_id] if person_id < len(names) else str(person_id)
                acc_text = f"  {round(100 - accuracy):.0f}%"
                flag = 1
            else:
                label = "unknown"
                acc_text = f"  {round(100 - accuracy):.0f}%"
                flag = 0

            cv2.putText(img, str(label), (x + 5, y - 5), font, 1,
                        (255, 255, 255), 2)
            cv2.putText(img, str(acc_text), (x + 5, y + h - 5), font, 1,
                        (255, 255, 0), 1)

        cv2.imshow("Face Authentication", img)

        key = cv2.waitKey(10) & 0xFF
        if key == 27:   # ESC
            break
        if flag == 1:
            break

    cam.release()
    cv2.destroyAllWindows()
    return flag

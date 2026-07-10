"""
Face-sample capture tool.
==========================

Captures face images from the webcam and saves them into
``backend/auth/samples/`` for use by ``trainer.py``.

Usage::

    python backend/auth/sample.py

You will be prompted for a numeric user ID.  Each person you want to
recognise should get a unique ID (1, 2, 3, …).

Press ESC to stop early, or wait until 100 samples are collected.
"""

import os
import sys

import cv2


def main() -> None:
    # Resolve paths relative to this script
    _here = os.path.dirname(os.path.abspath(__file__))
    cascade_path = os.path.join(_here, "haarcascade_frontalface_default.xml")
    samples_dir = os.path.join(_here, "samples")
    os.makedirs(samples_dir, exist_ok=True)

    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cam.set(3, 640)   # width
    cam.set(4, 480)   # height

    detector = cv2.CascadeClassifier(cascade_path)

    face_id_str = input("Enter a numeric user ID here: ").strip()
    try:
        face_id = int(face_id_str)
    except ValueError:
        print("Please enter a valid integer ID.")
        sys.exit(1)

    print("Taking samples, look at camera .......")
    count = 0

    while True:
        ret, img = cam.read()
        if not ret:
            print("Camera read failed — is the webcam connected?")
            break

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            cv2.rectangle(img, (x, y), (x + w, y + h), (255, 0, 0), 2)
            count += 1

            # Save the face crop
            sample_path = os.path.join(
                samples_dir, f"face.{face_id}.{count}.jpg"
            )
            cv2.imwrite(sample_path, gray[y:y + h, x:x + w])

            cv2.imshow("Sample Capture", img)

        key = cv2.waitKey(100) & 0xFF
        if key == 27:   # ESC
            break
        if count >= 100:
            break

    print("Samples taken, now closing the program....")
    cam.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

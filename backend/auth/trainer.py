"""
Face-model trainer.
====================

Processes the sample images in ``backend/auth/samples/`` and produces a
trained LBPH recogniser saved to ``backend/auth/trainer/trainer.yml``.

Run this after you have captured face samples with ``sample.py``::

    python backend/auth/trainer.py
"""

import os

import cv2
import numpy as np
from PIL import Image


def Images_And_Labels(path: str) -> tuple[list, list]:
    """Walk *path* and return ``(face_samples, ids)``.

    Parameters
    ----------
    path : str
        Directory containing sample images named like
        ``face.{id}.{count}.jpg``.

    Returns
    -------
    tuple[list, list]
        ``(face_samples, ids)`` where *face_samples* is a list of NumPy arrays
        and *ids* is the corresponding list of integer labels.
    """
    _here = os.path.dirname(os.path.abspath(__file__))
    cascade_path = os.path.join(_here, "haarcascade_frontalface_default.xml")
    detector = cv2.CascadeClassifier(cascade_path)

    imagePaths = [
        os.path.join(path, f)
        for f in os.listdir(path)
        if f.endswith((".jpg", ".jpeg", ".png"))
    ]

    faceSamples: list = []
    ids: list = []

    for imagePath in imagePaths:
        gray_img = Image.open(imagePath).convert("L")
        img_arr = np.array(gray_img, "uint8")

        # Face ID is embedded in the filename: "face.<id>.<count>.jpg"
        try:
            person_id = int(os.path.split(imagePath)[-1].split(".")[1])
        except (IndexError, ValueError):
            print(f"Skipping: {imagePath} (bad filename format)")
            continue

        faces = detector.detectMultiScale(img_arr)

        for (x, y, w, h) in faces:
            faceSamples.append(img_arr[y:y + h, x:x + w])
            ids.append(person_id)

    return faceSamples, ids


def main() -> None:
    _here = os.path.dirname(os.path.abspath(__file__))
    samples_dir = os.path.join(_here, "samples")
    trainer_dir = os.path.join(_here, "trainer")
    os.makedirs(trainer_dir, exist_ok=True)

    if not os.path.isdir(samples_dir) or not os.listdir(samples_dir):
        print(f"No sample images found in {samples_dir}. Run sample.py first.")
        return

    print("Training faces. It will take a few seconds. Wait ...")

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    faces, ids = Images_And_Labels(samples_dir)

    if not faces:
        print("No faces found in samples. Make sure the images contain faces.")
        return

    recognizer.train(faces, np.array(ids))
    trainer_path = os.path.join(trainer_dir, "trainer.yml")
    recognizer.write(trainer_path)

    print(f"Model trained and saved to {trainer_path}")
    print("Now you can recognize your face with recoganize.py")


if __name__ == "__main__":
    main()

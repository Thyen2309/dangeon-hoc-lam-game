"""
camera.py

This file contains a simple Camera class that uses OpenCV
to access the computer or phone camera.

The GameRoot widget in main.py uses this class to grab frames
and display them inside a Kivy Image widget.
"""

import cv2


class Camera:
    """
    Simple wrapper around OpenCV's VideoCapture.

    It:
    - Opens the default camera
    - Returns frames when requested
    - Can be released when the app closes
    """

    def __init__(self, index: int = 0):
        """
        Create a new Camera object.

        :param index: camera index (0 is usually the default camera)
        """
        self.index = index
        self.capture = cv2.VideoCapture(self.index)

    def get_frame(self):
        """
        Grab a single frame from the camera.

        :return: an image (NumPy array) or None if the frame could not be read
        """
        if not self.capture or not self.capture.isOpened():
            return None

        ret, frame = self.capture.read()
        if not ret:
            return None

        # Flip the frame horizontally so it feels like a mirror / selfie camera.
        frame = cv2.flip(frame, 1)
        return frame

    def release(self):
        """
        Release the camera resource.
        This should be called when the app closes.
        """
        if self.capture and self.capture.isOpened():
            self.capture.release()


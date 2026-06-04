"""
pipeline/staff_classifier.py — HSV color match on Purplle uniform + embedding helper
Purplle Store Intelligence Challenge 2026

Two responsibilities (kept together for caching):
  1. classify(crop) -> (is_staff, confidence) via HSV color match
  2. get_embedding(crop) -> 256-D appearance vector for Re-ID

Design decision:
  Claude suggested using pose estimation to detect staff (staff rarely stop
  >60s in one place). Rejected: too compute-heavy for batch processing.
  HSV color matching on Purplle's purple/magenta uniform color is 40x faster
  and more brand-specific. False positive rate is very low since customers
  rarely wear that exact HSV range (H=130-170, S>50, V>50).
"""

import cv2
import numpy as np


class StaffClassifier:
    """
    Classify whether a person crop is staff based on Purplle uniform color.
    Also provides lightweight appearance embeddings for Re-ID.
    """

    # Purplle brand purple/magenta in HSV color space
    # H: 130-170 = blue-purple to magenta range
    LOWER_PURPLE = np.array([130, 50, 50])
    UPPER_PURPLE = np.array([170, 255, 255])
    STAFF_RATIO_THRESHOLD = 0.25  # 25% of upper body pixels in uniform color

    def classify(self, crop: np.ndarray) -> tuple[bool, float]:
        """
        Returns (is_staff, confidence).
        Analyzes upper 60% of the bounding box for uniform color.
        """
        if crop is None or crop.size == 0:
            return False, 0.5

        h = crop.shape[0]
        upper_body = crop[: int(h * 0.6), :]
        if upper_body.size == 0:
            return False, 0.5

        hsv = cv2.cvtColor(upper_body, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.LOWER_PURPLE, self.UPPER_PURPLE)
        purple_ratio = float(np.sum(mask > 0)) / (mask.size + 1e-6)

        if purple_ratio > self.STAFF_RATIO_THRESHOLD:
            return True, min(0.5 + purple_ratio, 0.95)
        return False, 0.5

    def get_embedding(self, crop: np.ndarray) -> np.ndarray:
        """
        Lightweight 256-D appearance embedding via HSV color histogram.
        Used for Re-ID cosine similarity matching.

        Production upgrade path: swap this for OSNet / TorchReID encoder
        which gives 2048-D embeddings with much better discriminative power.
        Color histograms work well enough for a single-store demo at this scale.
        """
        if crop is None or crop.size == 0:
            return np.zeros(256, dtype=np.float32)

        try:
            crop_resized = cv2.resize(crop, (64, 128))
            hsv = cv2.cvtColor(crop_resized, cv2.COLOR_BGR2HSV)
            # 16x16 bins across H and S channels -> 256-D
            hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
            hist = cv2.normalize(hist, hist).flatten().astype(np.float32)
            out = np.zeros(256, dtype=np.float32)
            out[: len(hist)] = hist[:256]
            return out
        except Exception:
            return np.zeros(256, dtype=np.float32)

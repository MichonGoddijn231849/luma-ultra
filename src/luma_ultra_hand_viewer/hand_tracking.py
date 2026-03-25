from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


@dataclass(slots=True)
class TrackedHand:
    label: str
    score: float
    pinch_distance_px: float


@dataclass(slots=True)
class TrackingResult:
    frame_bgr: np.ndarray
    hands: list[TrackedHand]
    fps: float


def _get_model_path() -> Path:
    if getattr(sys, "frozen", False):
        app_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    else:
        app_root = Path(__file__).resolve().parents[2]

    model_path = app_root / "assets" / "hand_landmarker.task"
    if not model_path.exists():
        raise FileNotFoundError(f"MediaPipe hand model not found: {model_path}")

    return model_path


class HandTracker:
    def __init__(self) -> None:
        options = vision.HandLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(_get_model_path())),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.55,
            min_hand_presence_confidence=0.45,
            min_tracking_confidence=0.45,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._connections = vision.HandLandmarksConnections.HAND_CONNECTIONS
        self._last_fps_timestamp = time.perf_counter()
        self._smoothed_fps = 0.0
        self._last_frame_timestamp_ms = 0

    def process(self, frame_bgr: np.ndarray) -> TrackingResult:
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        results = self._landmarker.detect_for_video(mp_image, self._next_timestamp_ms())
        annotated = frame_bgr.copy()
        hands: list[TrackedHand] = []
        image_height, image_width = annotated.shape[:2]

        if results.hand_landmarks:
            for index, hand_landmarks in enumerate(results.hand_landmarks):
                handedness = "Unknown"
                score = 0.0
                if index < len(results.handedness) and results.handedness[index]:
                    category = results.handedness[index][0]
                    handedness = category.category_name or category.display_name or "Unknown"
                    score = float(category.score)

                pinch_distance = self._draw_hand(annotated, hand_landmarks, image_width, image_height)
                hands.append(
                    TrackedHand(
                        label=handedness,
                        score=score,
                        pinch_distance_px=pinch_distance,
                    )
                )

        fps = self._tick_fps()
        return TrackingResult(frame_bgr=annotated, hands=hands, fps=fps)

    def close(self) -> None:
        self._landmarker.close()

    def _next_timestamp_ms(self) -> int:
        timestamp_ms = int(time.perf_counter() * 1000)
        if timestamp_ms <= self._last_frame_timestamp_ms:
            timestamp_ms = self._last_frame_timestamp_ms + 1

        self._last_frame_timestamp_ms = timestamp_ms
        return timestamp_ms

    def _tick_fps(self) -> float:
        now = time.perf_counter()
        delta = max(now - self._last_fps_timestamp, 1e-6)
        instantaneous = 1.0 / delta
        self._smoothed_fps = (
            instantaneous if self._smoothed_fps == 0.0 else (self._smoothed_fps * 0.9 + instantaneous * 0.1)
        )
        self._last_fps_timestamp = now
        return self._smoothed_fps

    def _draw_hand(
        self,
        frame_bgr: np.ndarray,
        hand_landmarks: list,
        image_width: int,
        image_height: int,
    ) -> float:
        points: list[tuple[int, int]] = []
        for landmark in hand_landmarks:
            x = min(max(int(landmark.x * image_width), 0), image_width - 1)
            y = min(max(int(landmark.y * image_height), 0), image_height - 1)
            points.append((x, y))

        for connection in self._connections:
            start = points[connection.start]
            end = points[connection.end]
            cv2.line(frame_bgr, start, end, (0, 224, 255), 2, cv2.LINE_AA)

        for index, point in enumerate(points):
            radius = 6 if index in (4, 8, 12, 16, 20) else 4
            color = (255, 180, 32) if index in (4, 8) else (30, 255, 170)
            cv2.circle(frame_bgr, point, radius, color, -1, cv2.LINE_AA)

        thumb_tip = np.array(points[4], dtype=np.float32)
        index_tip = np.array(points[8], dtype=np.float32)
        pinch_distance = float(np.linalg.norm(thumb_tip - index_tip))
        pinch_center = tuple(np.round((thumb_tip + index_tip) * 0.5).astype(int))
        cv2.circle(frame_bgr, pinch_center, 10, (255, 255, 255), 1, cv2.LINE_AA)
        return pinch_distance

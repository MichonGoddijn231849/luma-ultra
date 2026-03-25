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
    pinch_ratio: float
    middle_pinch_ratio: float
    index_tip_px: tuple[int, int]
    index_tip_norm: tuple[float, float]


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
            min_hand_detection_confidence=0.42,
            min_hand_presence_confidence=0.32,
            min_tracking_confidence=0.35,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._connections = vision.HandLandmarksConnections.HAND_CONNECTIONS
        self._last_fps_timestamp = time.perf_counter()
        self._smoothed_fps = 0.0
        self._last_frame_timestamp_ms = 0
        self._last_primary_hand: TrackedHand | None = None
        self._last_primary_hand_time = 0.0

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

                hands.append(
                    self._draw_hand(
                        annotated,
                        hand_landmarks,
                        image_width,
                        image_height,
                        handedness,
                        score,
                    )
                )

        now = time.perf_counter()
        if len(hands) == 1:
            hands[0] = self._stabilize_hand(hands[0])
            self._last_primary_hand = hands[0]
            self._last_primary_hand_time = now
        elif not hands and self._last_primary_hand is not None and now - self._last_primary_hand_time <= 0.18:
            hands = [self._last_primary_hand]
        else:
            self._last_primary_hand = None

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

    def _stabilize_hand(self, hand: TrackedHand) -> TrackedHand:
        previous = self._last_primary_hand
        if previous is None or previous.label != hand.label:
            return hand

        position_blend = 0.24
        pinch_blend = 0.5
        smoothed_index_tip_norm = (
            previous.index_tip_norm[0] + (hand.index_tip_norm[0] - previous.index_tip_norm[0]) * position_blend,
            previous.index_tip_norm[1] + (hand.index_tip_norm[1] - previous.index_tip_norm[1]) * position_blend,
        )
        smoothed_index_tip_px = (
            int(round(previous.index_tip_px[0] + (hand.index_tip_px[0] - previous.index_tip_px[0]) * position_blend)),
            int(round(previous.index_tip_px[1] + (hand.index_tip_px[1] - previous.index_tip_px[1]) * position_blend)),
        )
        return TrackedHand(
            label=hand.label,
            score=max(hand.score, previous.score * 0.92),
            pinch_distance_px=previous.pinch_distance_px
            + (hand.pinch_distance_px - previous.pinch_distance_px) * pinch_blend,
            pinch_ratio=previous.pinch_ratio + (hand.pinch_ratio - previous.pinch_ratio) * pinch_blend,
            middle_pinch_ratio=previous.middle_pinch_ratio
            + (hand.middle_pinch_ratio - previous.middle_pinch_ratio) * pinch_blend,
            index_tip_px=smoothed_index_tip_px,
            index_tip_norm=smoothed_index_tip_norm,
        )

    def _draw_hand(
        self,
        frame_bgr: np.ndarray,
        hand_landmarks: list,
        image_width: int,
        image_height: int,
        handedness: str,
        score: float,
    ) -> TrackedHand:
        points: list[tuple[int, int]] = []
        normalized_points: list[tuple[float, float]] = []
        for landmark in hand_landmarks:
            x = min(max(int(landmark.x * image_width), 0), image_width - 1)
            y = min(max(int(landmark.y * image_height), 0), image_height - 1)
            points.append((x, y))
            normalized_points.append((float(landmark.x), float(landmark.y)))

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
        middle_tip = np.array(points[12], dtype=np.float32)
        palm_span = float(
            np.linalg.norm(np.array(points[5], dtype=np.float32) - np.array(points[17], dtype=np.float32))
        )
        palm_span = max(palm_span, 1.0)
        pinch_distance = float(np.linalg.norm(thumb_tip - index_tip))
        pinch_ratio = pinch_distance / palm_span
        middle_pinch_ratio = float(np.linalg.norm(thumb_tip - middle_tip)) / palm_span
        pinch_center = tuple(np.round((thumb_tip + index_tip) * 0.5).astype(int))
        cv2.circle(frame_bgr, pinch_center, 10, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(
            frame_bgr,
            f"{handedness} {score * 100:.0f}%",
            (points[0][0] + 10, max(28, points[0][1] - 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (240, 248, 255),
            2,
            cv2.LINE_AA,
        )
        return TrackedHand(
            label=handedness,
            score=score,
            pinch_distance_px=pinch_distance,
            pinch_ratio=pinch_ratio,
            middle_pinch_ratio=middle_pinch_ratio,
            index_tip_px=points[8],
            index_tip_norm=normalized_points[8],
        )

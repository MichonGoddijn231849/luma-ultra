from __future__ import annotations

import ctypes
from collections import deque
from dataclasses import dataclass
import time
from typing import Optional

from .hand_tracking import TrackingResult, TrackedHand


@dataclass(slots=True)
class AirMouseState:
    enabled: bool
    controlling: bool
    hand_label: str
    cursor_position: Optional[tuple[int, int]]
    primary_gesture: str
    status_text: str


class WindowsAirMouseController:
    _SM_CXSCREEN = 0
    _SM_CYSCREEN = 1
    _MOUSEEVENTF_LEFTDOWN = 0x0002
    _MOUSEEVENTF_LEFTUP = 0x0004
    _MOUSEEVENTF_RIGHTDOWN = 0x0008
    _MOUSEEVENTF_RIGHTUP = 0x0010
    _X_MARGIN = 0.14
    _Y_MARGIN = 0.18

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    def __init__(self) -> None:
        self._user32 = ctypes.windll.user32
        self._enabled = True
        self._screen_width = max(int(self._user32.GetSystemMetrics(self._SM_CXSCREEN)), 1)
        self._screen_height = max(int(self._user32.GetSystemMetrics(self._SM_CYSCREEN)), 1)
        self._smoothed_cursor: Optional[tuple[float, float]] = None
        self._last_hand: Optional[TrackedHand] = None
        self._last_hand_seen_at = 0.0
        self._left_button_down = False
        self._right_pinch_active = False
        self._pinch_anchor_cursor: Optional[tuple[float, float]] = None
        self._pinch_anchor_hand_norm: Optional[tuple[float, float]] = None
        self._drag_mode = False
        self._logs: deque[str] = deque(maxlen=120)
        self._last_status_text = ""

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        if self._enabled == enabled:
            return

        self._enabled = enabled
        self._release_buttons()
        self._smoothed_cursor = None
        self._last_hand = None
        self._log("Air mouse enabled." if enabled else "Air mouse disabled.")

    def drain_logs(self) -> list[str]:
        messages = list(self._logs)
        self._logs.clear()
        return messages

    def update(self, tracking: TrackingResult) -> AirMouseState:
        if not self._enabled:
            self._release_buttons()
            return self._state(False, "", None, "Off", "Air mouse is off.")

        hand = self._select_hand(tracking)
        if hand is None:
            self._release_buttons()
            if len(tracking.hands) == 0:
                return self._state(False, "", self._current_cursor_position(), "Idle", "Show one hand to control the cursor.")
            return self._state(False, "", self._current_cursor_position(), "Paused", "Two hands visible, cursor paused.")

        primary_gesture = self._update_buttons(hand)
        target = self._target_cursor_position(hand)
        lock_cursor = self._left_button_down and not self._drag_mode
        self._move_cursor(target, lock_cursor=lock_cursor)
        return self._state(
            True,
            hand.label,
            self._current_cursor_position(),
            primary_gesture,
            f"{hand.label} hand controls the cursor.",
        )

    def _select_hand(self, tracking: TrackingResult) -> Optional[TrackedHand]:
        now = time.perf_counter()
        if len(tracking.hands) == 1:
            self._last_hand = tracking.hands[0]
            self._last_hand_seen_at = now
            return tracking.hands[0]

        if len(tracking.hands) == 0 and self._last_hand is not None and now - self._last_hand_seen_at <= 0.16:
            return self._last_hand

        self._last_hand = None
        return None

    def _map_hand_to_screen(self, hand: TrackedHand) -> tuple[int, int]:
        x_norm, y_norm = hand.index_tip_norm
        x_norm = self._normalize_axis(x_norm, margin=self._X_MARGIN)
        y_norm = self._normalize_axis(y_norm, margin=self._Y_MARGIN)
        x = int(round(x_norm * (self._screen_width - 1)))
        y = int(round(y_norm * (self._screen_height - 1)))
        return x, y

    def _normalize_axis(self, value: float, margin: float) -> float:
        usable = max(1.0 - margin * 2.0, 1e-6)
        normalized = (value - margin) / usable
        return min(max(normalized, 0.0), 1.0)

    def _move_cursor(self, target: tuple[int, int], lock_cursor: bool) -> None:
        if self._smoothed_cursor is None:
            self._smoothed_cursor = (float(target[0]), float(target[1]))
        elif lock_cursor:
            self._smoothed_cursor = (float(target[0]), float(target[1]))
        else:
            delta_x = target[0] - self._smoothed_cursor[0]
            delta_y = target[1] - self._smoothed_cursor[1]
            distance = (delta_x * delta_x + delta_y * delta_y) ** 0.5
            blend = 0.18 if distance < 60 else 0.24
            self._smoothed_cursor = (
                self._smoothed_cursor[0] + (target[0] - self._smoothed_cursor[0]) * blend,
                self._smoothed_cursor[1] + (target[1] - self._smoothed_cursor[1]) * blend,
            )

        x = int(round(self._smoothed_cursor[0]))
        y = int(round(self._smoothed_cursor[1]))
        self._user32.SetCursorPos(x, y)

    def _update_buttons(self, hand: TrackedHand) -> str:
        primary_gesture = "Move"

        if hand.pinch_ratio < 0.34:
            if not self._left_button_down:
                self._pinch_anchor_cursor = self._cursor_anchor_position()
                self._pinch_anchor_hand_norm = hand.index_tip_norm
                self._drag_mode = False
                self._mouse_event(self._MOUSEEVENTF_LEFTDOWN)
                self._left_button_down = True
                self._log("Left pinch detected.")
            primary_gesture = "Left click"
        elif hand.pinch_ratio > 0.46 and self._left_button_down:
            self._mouse_event(self._MOUSEEVENTF_LEFTUP)
            self._left_button_down = False
            self._pinch_anchor_cursor = None
            self._pinch_anchor_hand_norm = None
            self._drag_mode = False
            self._log("Left pinch released.")

        if hand.middle_pinch_ratio < 0.33 and not self._right_pinch_active:
            self._mouse_event(self._MOUSEEVENTF_RIGHTDOWN | self._MOUSEEVENTF_RIGHTUP)
            self._right_pinch_active = True
            self._log("Right click gesture detected.")
            primary_gesture = "Right click"
        elif hand.middle_pinch_ratio > 0.45:
            self._right_pinch_active = False

        if self._left_button_down:
            primary_gesture = "Left drag" if self._drag_mode else "Left click"

        return primary_gesture

    def _target_cursor_position(self, hand: TrackedHand) -> tuple[int, int]:
        if (
            not self._left_button_down
            or self._pinch_anchor_cursor is None
            or self._pinch_anchor_hand_norm is None
        ):
            return self._map_hand_to_screen(hand)

        delta_x = hand.index_tip_norm[0] - self._pinch_anchor_hand_norm[0]
        delta_y = hand.index_tip_norm[1] - self._pinch_anchor_hand_norm[1]
        movement = (delta_x * delta_x + delta_y * delta_y) ** 0.5
        if not self._drag_mode and movement < 0.028:
            return int(round(self._pinch_anchor_cursor[0])), int(round(self._pinch_anchor_cursor[1]))

        self._drag_mode = True
        drag_x = self._pinch_anchor_cursor[0] + (
            delta_x / max(1.0 - self._X_MARGIN * 2.0, 1e-6)
        ) * (self._screen_width - 1)
        drag_y = self._pinch_anchor_cursor[1] + (
            delta_y / max(1.0 - self._Y_MARGIN * 2.0, 1e-6)
        ) * (self._screen_height - 1)
        return int(round(drag_x)), int(round(drag_y))

    def _current_cursor_position(self) -> Optional[tuple[int, int]]:
        if self._smoothed_cursor is None:
            return None
        return int(round(self._smoothed_cursor[0])), int(round(self._smoothed_cursor[1]))

    def _cursor_anchor_position(self) -> tuple[float, float]:
        if self._smoothed_cursor is not None:
            return self._smoothed_cursor

        point = self._POINT()
        self._user32.GetCursorPos(ctypes.byref(point))
        return float(point.x), float(point.y)

    def _release_buttons(self) -> None:
        if self._left_button_down:
            self._mouse_event(self._MOUSEEVENTF_LEFTUP)
            self._left_button_down = False
        self._right_pinch_active = False
        self._pinch_anchor_cursor = None
        self._pinch_anchor_hand_norm = None
        self._drag_mode = False

    def _mouse_event(self, flags: int) -> None:
        self._user32.mouse_event(flags, 0, 0, 0, 0)

    def _state(
        self,
        controlling: bool,
        hand_label: str,
        cursor_position: Optional[tuple[int, int]],
        primary_gesture: str,
        status_text: str,
    ) -> AirMouseState:
        if status_text != self._last_status_text:
            self._last_status_text = status_text
        return AirMouseState(
            enabled=self._enabled,
            controlling=controlling,
            hand_label=hand_label,
            cursor_position=cursor_position,
            primary_gesture=primary_gesture,
            status_text=status_text,
        )

    def _log(self, message: str) -> None:
        self._logs.append(f"[{time.strftime('%H:%M:%S')}] {message}")

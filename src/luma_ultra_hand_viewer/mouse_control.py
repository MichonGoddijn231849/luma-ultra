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
    _MOUSEEVENTF_LEFTDOWN = 0x0002
    _MOUSEEVENTF_LEFTUP = 0x0004
    _MOUSEEVENTF_RIGHTDOWN = 0x0008
    _MOUSEEVENTF_RIGHTUP = 0x0010
    _POINTER_GAIN_X = 2800.0
    _POINTER_GAIN_Y = 2300.0
    _CURSOR_SMOOTHING = 0.36
    _HAND_REENTRY_HOLD_SECONDS = 0.30
    _CLICK_DRAG_THRESHOLD_NORM = 0.018
    _MOTION_DEADZONE_NORM = 0.0016
    _SCENE_MOTION_COMPENSATION = 1.0
    _PINCH_ON_THRESHOLD = 0.34
    _PINCH_OFF_THRESHOLD = 0.46
    _RIGHT_CLICK_ON_THRESHOLD = 0.33
    _RIGHT_CLICK_OFF_THRESHOLD = 0.45

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    def __init__(self) -> None:
        self._user32 = ctypes.windll.user32
        self._enabled = True
        self._last_visible_hand: Optional[TrackedHand] = None
        self._last_visible_seen_at = 0.0
        self._smoothed_cursor: Optional[tuple[float, float]] = None
        self._left_button_down = False
        self._right_pinch_active = False
        self._drag_mode = False
        self._drag_motion_accum = (0.0, 0.0)
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
        self._last_visible_hand = None
        self._smoothed_cursor = None
        self._log("Air mouse enabled." if enabled else "Air mouse disabled.")

    def drain_logs(self) -> list[str]:
        messages = list(self._logs)
        self._logs.clear()
        return messages

    def update(self, tracking: TrackingResult, pose: Optional[object] = None) -> AirMouseState:
        if not self._enabled:
            self._release_buttons()
            return self._state(False, "", None, "Off", "Air mouse is off.")

        hand, hand_visible = self._select_hand(tracking)
        if hand is None:
            self._last_visible_hand = None
            self._release_buttons()
            if len(tracking.hands) == 0:
                return self._state(False, "", self._current_cursor_position(), "Idle", "Show one hand to control the cursor.")
            return self._state(False, "", self._current_cursor_position(), "Paused", "Two hands visible, cursor paused.")

        if self._smoothed_cursor is None:
            self._smoothed_cursor = self._current_cursor_position_float()

        if not hand_visible:
            return self._state(
                True,
                hand.label,
                self._current_cursor_position(),
                "Hold",
                f"{hand.label} hand briefly left frame. Cursor anchor preserved.",
            )

        if self._last_visible_hand is None:
            self._last_visible_hand = hand
            self._last_visible_seen_at = time.perf_counter()
            return self._state(
                True,
                hand.label,
                self._current_cursor_position(),
                "Ready",
                f"{hand.label} hand acquired. Move your index finger to control the cursor.",
            )

        motion_delta_norm = self._compensated_motion_delta(self._last_visible_hand, hand, tracking)
        primary_gesture = self._update_buttons(hand)
        target_cursor = self._target_cursor(motion_delta_norm)
        self._move_cursor_toward(
            target_cursor,
            lock_cursor=self._left_button_down and not self._drag_mode,
        )
        self._last_visible_hand = hand
        self._last_visible_seen_at = time.perf_counter()
        return self._state(
            True,
            hand.label,
            self._current_cursor_position(),
            primary_gesture,
            f"{hand.label} hand controls the cursor.",
        )

    def _select_hand(self, tracking: TrackingResult) -> tuple[Optional[TrackedHand], bool]:
        now = time.perf_counter()
        if len(tracking.hands) == 1:
            self._last_visible_seen_at = now
            return tracking.hands[0], True

        if (
            len(tracking.hands) == 0
            and self._last_visible_hand is not None
            and now - self._last_visible_seen_at <= self._HAND_REENTRY_HOLD_SECONDS
        ):
            return self._last_visible_hand, False

        return None, False

    def _update_buttons(self, hand: TrackedHand) -> str:
        primary_gesture = "Move"

        if hand.pinch_ratio < self._PINCH_ON_THRESHOLD:
            if not self._left_button_down:
                self._drag_mode = False
                self._drag_motion_accum = (0.0, 0.0)
                self._mouse_event(self._MOUSEEVENTF_LEFTDOWN)
                self._left_button_down = True
                self._log("Left pinch detected.")
            primary_gesture = "Left click"
        elif hand.pinch_ratio > self._PINCH_OFF_THRESHOLD and self._left_button_down:
            self._mouse_event(self._MOUSEEVENTF_LEFTUP)
            self._left_button_down = False
            self._drag_mode = False
            self._drag_motion_accum = (0.0, 0.0)
            self._log("Left pinch released.")

        if hand.middle_pinch_ratio < self._RIGHT_CLICK_ON_THRESHOLD and not self._right_pinch_active:
            self._mouse_event(self._MOUSEEVENTF_RIGHTDOWN | self._MOUSEEVENTF_RIGHTUP)
            self._right_pinch_active = True
            self._log("Right click gesture detected.")
            primary_gesture = "Right click"
        elif hand.middle_pinch_ratio > self._RIGHT_CLICK_OFF_THRESHOLD:
            self._right_pinch_active = False

        if self._left_button_down:
            primary_gesture = "Left drag" if self._drag_mode else "Left click"

        return primary_gesture

    def _target_cursor(
        self,
        motion_delta_norm: tuple[float, float],
    ) -> tuple[float, float]:
        base_cursor = self._cursor_anchor_position()
        if self._left_button_down and not self._drag_mode:
            accum_x = self._drag_motion_accum[0] + motion_delta_norm[0]
            accum_y = self._drag_motion_accum[1] + motion_delta_norm[1]
            self._drag_motion_accum = (accum_x, accum_y)
            if (accum_x * accum_x + accum_y * accum_y) ** 0.5 < self._CLICK_DRAG_THRESHOLD_NORM:
                return base_cursor
            self._drag_mode = True

        return (
            base_cursor[0] + motion_delta_norm[0] * self._POINTER_GAIN_X,
            base_cursor[1] + motion_delta_norm[1] * self._POINTER_GAIN_Y,
        )

    def _compensated_motion_delta(
        self,
        previous_hand: TrackedHand,
        current_hand: TrackedHand,
        tracking: TrackingResult,
    ) -> tuple[float, float]:
        delta_x = current_hand.index_tip_norm[0] - previous_hand.index_tip_norm[0]
        delta_y = current_hand.index_tip_norm[1] - previous_hand.index_tip_norm[1]
        scene_dx = tracking.scene_motion_norm[0] * self._SCENE_MOTION_COMPENSATION
        scene_dy = tracking.scene_motion_norm[1] * self._SCENE_MOTION_COMPENSATION
        compensated_dx = delta_x - scene_dx
        compensated_dy = delta_y - scene_dy
        if abs(compensated_dx) < self._MOTION_DEADZONE_NORM:
            compensated_dx = 0.0
        if abs(compensated_dy) < self._MOTION_DEADZONE_NORM:
            compensated_dy = 0.0
        return compensated_dx, compensated_dy

    def _move_cursor_toward(self, target: tuple[float, float], lock_cursor: bool) -> None:
        if self._smoothed_cursor is None:
            self._smoothed_cursor = target
        elif lock_cursor:
            self._smoothed_cursor = target
        else:
            self._smoothed_cursor = (
                self._smoothed_cursor[0] + (target[0] - self._smoothed_cursor[0]) * self._CURSOR_SMOOTHING,
                self._smoothed_cursor[1] + (target[1] - self._smoothed_cursor[1]) * self._CURSOR_SMOOTHING,
            )

        self._move_cursor_to(self._smoothed_cursor)

    def _current_cursor_position(self) -> tuple[int, int]:
        point = self._POINT()
        self._user32.GetCursorPos(ctypes.byref(point))
        return point.x, point.y

    def _current_cursor_position_float(self) -> tuple[float, float]:
        x, y = self._current_cursor_position()
        return float(x), float(y)

    def _move_cursor_to(self, position: tuple[float, float]) -> None:
        self._user32.SetCursorPos(int(round(position[0])), int(round(position[1])))

    def _release_buttons(self) -> None:
        if self._left_button_down:
            self._mouse_event(self._MOUSEEVENTF_LEFTUP)
            self._left_button_down = False
        self._right_pinch_active = False
        self._drag_mode = False
        self._drag_motion_accum = (0.0, 0.0)

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

    def _cursor_anchor_position(self) -> tuple[float, float]:
        if self._smoothed_cursor is not None:
            return self._smoothed_cursor
        return self._current_cursor_position_float()

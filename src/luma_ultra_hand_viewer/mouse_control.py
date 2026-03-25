from __future__ import annotations

import ctypes
from collections import deque
from dataclasses import dataclass
import math
import time
from typing import Optional

from .device_sources import PoseSnapshot
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
    _POINTER_GAIN_X = 3200.0
    _POINTER_GAIN_Y = 2600.0
    _MOVE_DEADZONE_NORM = 0.004
    _MOVE_SMOOTHING = 0.35
    _POSE_YAW_COMP = 0.16
    _POSE_PITCH_COMP = 0.18
    _POSE_POS_X_COMP = 0.28
    _POSE_POS_Y_COMP = 0.28
    _HAND_REENTRY_HOLD_SECONDS = 0.22
    _CLICK_DRAG_THRESHOLD_NORM = 0.022

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    def __init__(self) -> None:
        self._user32 = ctypes.windll.user32
        self._enabled = True
        self._smoothed_velocity = (0.0, 0.0)
        self._tracking_active = False
        self._last_hand: Optional[TrackedHand] = None
        self._last_hand_seen_at = 0.0
        self._last_pose: Optional[PoseSnapshot] = None
        self._left_button_down = False
        self._right_pinch_active = False
        self._pinch_anchor_cursor: Optional[tuple[float, float]] = None
        self._pinch_anchor_hand_norm: Optional[tuple[float, float]] = None
        self._pinch_anchor_pose: Optional[PoseSnapshot] = None
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
        self._last_hand = None
        self._last_pose = None
        self._tracking_active = False
        self._smoothed_velocity = (0.0, 0.0)
        self._log("Air mouse enabled." if enabled else "Air mouse disabled.")

    def drain_logs(self) -> list[str]:
        messages = list(self._logs)
        self._logs.clear()
        return messages

    def update(self, tracking: TrackingResult, pose: Optional[PoseSnapshot]) -> AirMouseState:
        if not self._enabled:
            self._release_buttons()
            return self._state(False, "", None, "Off", "Air mouse is off.")

        hand = self._select_hand(tracking)
        if hand is None:
            self._tracking_active = False
            self._last_pose = pose
            self._smoothed_velocity = (0.0, 0.0)
            self._release_buttons()
            if len(tracking.hands) == 0:
                return self._state(
                    False,
                    "",
                    self._current_cursor_position(),
                    "Idle",
                    "Show one hand to control the cursor.",
                )
            return self._state(
                False,
                "",
                self._current_cursor_position(),
                "Paused",
                "Two hands visible, cursor paused.",
            )

        if not self._tracking_active:
            self._tracking_active = True
            self._last_hand = hand
            self._last_pose = pose
            self._smoothed_velocity = (0.0, 0.0)
            return self._state(
                True,
                hand.label,
                self._current_cursor_position(),
                "Ready",
                f"{hand.label} hand reacquired. Cursor anchor preserved.",
            )

        primary_gesture = self._update_buttons(hand)
        if self._left_button_down:
            target_cursor = self._drag_target_cursor(hand, pose)
            self._move_cursor_to(target_cursor)
        else:
            motion_delta = self._hand_motion_delta(hand, pose)
            self._move_cursor_by(motion_delta)

        self._last_hand = hand
        self._last_pose = pose
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

        if (
            len(tracking.hands) == 0
            and self._last_hand is not None
            and now - self._last_hand_seen_at <= self._HAND_REENTRY_HOLD_SECONDS
        ):
            return self._last_hand

        self._last_hand = None
        return None

    def _update_buttons(self, hand: TrackedHand) -> str:
        primary_gesture = "Move"

        if hand.pinch_ratio < 0.34:
            if not self._left_button_down:
                self._pinch_anchor_cursor = self._current_cursor_position_float()
                self._pinch_anchor_hand_norm = hand.index_tip_norm
                self._pinch_anchor_pose = self._last_pose
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
            self._pinch_anchor_pose = None
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

    def _drag_target_cursor(
        self,
        hand: TrackedHand,
        pose: Optional[PoseSnapshot],
    ) -> tuple[float, float]:
        if (
            self._pinch_anchor_cursor is None
            or self._pinch_anchor_hand_norm is None
        ):
            return self._current_cursor_position_float()

        delta_x = hand.index_tip_norm[0] - self._pinch_anchor_hand_norm[0]
        delta_y = hand.index_tip_norm[1] - self._pinch_anchor_hand_norm[1]
        pose_dx_norm, pose_dy_norm = self._pose_compensation(self._pinch_anchor_pose, pose)
        compensated_dx = delta_x - pose_dx_norm
        compensated_dy = delta_y - pose_dy_norm
        movement = (compensated_dx * compensated_dx + compensated_dy * compensated_dy) ** 0.5
        if not self._drag_mode and movement < self._CLICK_DRAG_THRESHOLD_NORM:
            return self._pinch_anchor_cursor

        self._drag_mode = True
        drag_x = self._pinch_anchor_cursor[0] + compensated_dx * self._POINTER_GAIN_X
        drag_y = self._pinch_anchor_cursor[1] + compensated_dy * self._POINTER_GAIN_Y
        return drag_x, drag_y

    def _hand_motion_delta(
        self,
        hand: TrackedHand,
        pose: Optional[PoseSnapshot],
    ) -> tuple[float, float]:
        if self._last_hand is None:
            return (0.0, 0.0)

        raw_dx = hand.index_tip_norm[0] - self._last_hand.index_tip_norm[0]
        raw_dy = hand.index_tip_norm[1] - self._last_hand.index_tip_norm[1]
        pose_dx_norm, pose_dy_norm = self._pose_compensation(self._last_pose, pose)
        compensated_dx = raw_dx - pose_dx_norm
        compensated_dy = raw_dy - pose_dy_norm
        magnitude = (compensated_dx * compensated_dx + compensated_dy * compensated_dy) ** 0.5
        if magnitude < self._MOVE_DEADZONE_NORM:
            compensated_dx = 0.0
            compensated_dy = 0.0

        pixel_dx = compensated_dx * self._POINTER_GAIN_X
        pixel_dy = compensated_dy * self._POINTER_GAIN_Y
        self._smoothed_velocity = (
            self._smoothed_velocity[0] * (1.0 - self._MOVE_SMOOTHING) + pixel_dx * self._MOVE_SMOOTHING,
            self._smoothed_velocity[1] * (1.0 - self._MOVE_SMOOTHING) + pixel_dy * self._MOVE_SMOOTHING,
        )
        return self._smoothed_velocity

    def _pose_compensation(
        self,
        previous_pose: Optional[PoseSnapshot],
        current_pose: Optional[PoseSnapshot],
    ) -> tuple[float, float]:
        if previous_pose is None or current_pose is None:
            return (0.0, 0.0)

        prev_pitch, prev_yaw, _ = self._quaternion_to_euler(previous_pose.rotation)
        curr_pitch, curr_yaw, _ = self._quaternion_to_euler(current_pose.rotation)
        yaw_delta = self._wrap_angle(curr_yaw - prev_yaw)
        pitch_delta = self._wrap_angle(curr_pitch - prev_pitch)
        pos_dx = current_pose.position[0] - previous_pose.position[0]
        pos_dy = current_pose.position[1] - previous_pose.position[1]
        return (
            yaw_delta * self._POSE_YAW_COMP + pos_dx * self._POSE_POS_X_COMP,
            -pitch_delta * self._POSE_PITCH_COMP - pos_dy * self._POSE_POS_Y_COMP,
        )

    def _current_cursor_position(self) -> Optional[tuple[int, int]]:
        point = self._POINT()
        self._user32.GetCursorPos(ctypes.byref(point))
        return point.x, point.y

    def _current_cursor_position_float(self) -> tuple[float, float]:
        x, y = self._current_cursor_position()
        return float(x), float(y)

    def _move_cursor_by(self, delta: tuple[float, float]) -> None:
        if abs(delta[0]) < 0.01 and abs(delta[1]) < 0.01:
            return

        current_x, current_y = self._current_cursor_position_float()
        self._move_cursor_to((current_x + delta[0], current_y + delta[1]))

    def _move_cursor_to(self, position: tuple[float, float]) -> None:
        self._user32.SetCursorPos(int(round(position[0])), int(round(position[1])))

    def _release_buttons(self) -> None:
        if self._left_button_down:
            self._mouse_event(self._MOUSEEVENTF_LEFTUP)
            self._left_button_down = False
        self._right_pinch_active = False
        self._pinch_anchor_cursor = None
        self._pinch_anchor_hand_norm = None
        self._pinch_anchor_pose = None
        self._drag_mode = False

    def _mouse_event(self, flags: int) -> None:
        self._user32.mouse_event(flags, 0, 0, 0, 0)

    def _quaternion_to_euler(self, rotation: tuple[float, float, float, float]) -> tuple[float, float, float]:
        x, y, z, w = rotation
        sinr_cosp = 2.0 * (w * x + y * z)
        cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)
        sinp = 2.0 * (w * y - z * x)
        if abs(sinp) >= 1.0:
            pitch = math.copysign(math.pi / 2.0, sinp)
        else:
            pitch = math.asin(sinp)
        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        return pitch, yaw, roll

    def _wrap_angle(self, angle: float) -> float:
        while angle > math.pi:
            angle -= 2.0 * math.pi
        while angle < -math.pi:
            angle += 2.0 * math.pi
        return angle

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

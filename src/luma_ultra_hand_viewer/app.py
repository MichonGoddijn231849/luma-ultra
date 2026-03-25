from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .device_sources import BaseFrameSource, FramePacket, open_best_source
from .hand_tracking import HandTracker, TrackingResult


def get_app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))

    return Path(__file__).resolve().parents[2]


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "--") -> None:
        super().__init__()
        self.setObjectName("StatCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("StatTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatValue")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class HandViewerWindow(QMainWindow):
    def __init__(self, sdk_root: Path) -> None:
        super().__init__()
        self._sdk_root = sdk_root
        self._source: BaseFrameSource = open_best_source(sdk_root)
        self._tracker = HandTracker()
        self._last_packet_timestamp = 0.0

        self.setWindowTitle("Luma Ultra Hand Viewer")
        self.resize(1560, 920)
        self._build_ui()
        self._flush_logs()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(33)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._timer.stop()
        self._tracker.close()
        self._source.stop()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(24)

        self.video_label = QLabel("Waiting for a video source...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(980, 720)
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_label.setObjectName("VideoSurface")

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(18)

        header = QLabel("Luma Ultra Hand Viewer")
        header.setObjectName("HeroTitle")
        subheader = QLabel(
            "Live VITURE stereo feed with MediaPipe hand landmarks. "
            "If the glasses are not detected, the app automatically falls back to your webcam."
        )
        subheader.setWordWrap(True)
        subheader.setObjectName("HeroCopy")

        button_row = QHBoxLayout()
        self.reconnect_button = QPushButton("Reconnect source")
        self.reconnect_button.clicked.connect(self._reconnect_source)
        self.reset_pose_button = QPushButton("Reset pose")
        self.reset_pose_button.clicked.connect(self._reset_pose)
        button_row.addWidget(self.reconnect_button)
        button_row.addWidget(self.reset_pose_button)

        stat_grid = QGridLayout()
        stat_grid.setHorizontalSpacing(12)
        stat_grid.setVerticalSpacing(12)
        self.source_card = StatCard("Source")
        self.model_card = StatCard("Device")
        self.fps_card = StatCard("Tracker FPS")
        self.hands_card = StatCard("Hands")
        self.pose_card = StatCard("Pose")
        self.imu_card = StatCard("IMU")
        stat_grid.addWidget(self.source_card, 0, 0)
        stat_grid.addWidget(self.model_card, 0, 1)
        stat_grid.addWidget(self.fps_card, 1, 0)
        stat_grid.addWidget(self.hands_card, 1, 1)
        stat_grid.addWidget(self.pose_card, 2, 0)
        stat_grid.addWidget(self.imu_card, 2, 1)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(260)
        self.log_output.setObjectName("LogPane")

        right_layout.addWidget(header)
        right_layout.addWidget(subheader)
        right_layout.addLayout(button_row)
        right_layout.addLayout(stat_grid)
        right_layout.addWidget(self.log_output, 1)

        root_layout.addWidget(self.video_label, 1)
        root_layout.addWidget(right_panel, 0)
        self.setCentralWidget(root)
        self._apply_styles()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background: #0e1418;
                color: #f4f1ea;
                font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif;
                font-size: 14px;
            }
            #VideoSurface {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #1d2a32,
                    stop: 0.55 #111a20,
                    stop: 1 #0d1216
                );
                border: 1px solid #34454f;
                border-radius: 28px;
                padding: 16px;
            }
            #HeroTitle {
                font-size: 30px;
                font-weight: 700;
                color: #fff8ee;
            }
            #HeroCopy {
                color: #b9c6ce;
                line-height: 1.4;
            }
            QPushButton {
                background: #f2a14a;
                color: #141414;
                border: none;
                border-radius: 14px;
                padding: 12px 18px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #ffc37b;
            }
            QPushButton:pressed {
                background: #d88a37;
            }
            #StatCard {
                background: #162027;
                border: 1px solid #2f414b;
                border-radius: 18px;
            }
            #StatTitle {
                color: #91a7b3;
                font-size: 12px;
                font-weight: 700;
                text-transform: uppercase;
            }
            #StatValue {
                font-size: 20px;
                font-weight: 700;
                color: #fff5e6;
            }
            #LogPane {
                background: #121a1f;
                border: 1px solid #2f414b;
                border-radius: 18px;
                padding: 12px;
                color: #c9d4db;
            }
            """
        )

    def _reconnect_source(self) -> None:
        self._source.stop()
        self._source = open_best_source(self._sdk_root)
        self._flush_logs()

    def _reset_pose(self) -> None:
        self._source.reset_pose()
        self._flush_logs()

    def _refresh(self) -> None:
        self._flush_logs()
        packet = self._source.get_latest_packet()
        if packet is None:
            return
        if packet.timestamp == self._last_packet_timestamp:
            return

        self._last_packet_timestamp = packet.timestamp
        tracking = self._tracker.process(packet.frame_bgr)
        decorated = self._decorate_frame(packet, tracking)
        self._present_frame(decorated)
        self._update_stats(packet, tracking)

    def _flush_logs(self) -> None:
        for message in self._source.drain_logs():
            self.log_output.appendPlainText(message)
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def _decorate_frame(self, packet: FramePacket, tracking: TrackingResult) -> np.ndarray:
        frame = tracking.frame_bgr.copy()
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], 106), (10, 18, 25), -1)
        cv2.addWeighted(overlay, 0.76, frame, 0.24, 0.0, frame)

        cv2.putText(
            frame,
            "LUMA ULTRA HAND VIEWER",
            (22, 38),
            cv2.FONT_HERSHEY_DUPLEX,
            0.92,
            (248, 245, 233),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            f"{packet.source_name}  |  {packet.width}x{packet.height}  |  {tracking.fps:04.1f} fps",
            (24, 72),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (182, 202, 214),
            2,
            cv2.LINE_AA,
        )

        footer_y = frame.shape[0] - 24
        cv2.putText(
            frame,
            self._describe_hands(tracking),
            (24, footer_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.68,
            (255, 192, 105),
            2,
            cv2.LINE_AA,
        )

        if packet.pose is not None:
            cv2.putText(
                frame,
                f"Pose xyz: {packet.pose.position[0]:+.2f}, {packet.pose.position[1]:+.2f}, {packet.pose.position[2]:+.2f}",
                (24, footer_y - 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (117, 235, 201),
                2,
                cv2.LINE_AA,
            )
        return frame

    def _describe_hands(self, tracking: TrackingResult) -> str:
        if not tracking.hands:
            return "No hands detected yet. Bring your hand closer to the cameras."
        segments = [
            f"{hand.label} ({hand.score * 100:.0f}%, pinch {hand.pinch_distance_px:.0f}px)"
            for hand in tracking.hands
        ]
        return " | ".join(segments)

    def _present_frame(self, frame_bgr: np.ndarray) -> None:
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        height, width = frame_rgb.shape[:2]
        image = QImage(frame_rgb.data, width, height, frame_rgb.strides[0], QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(image.copy())
        scaled = pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.video_label.setPixmap(scaled)

    def _update_stats(self, packet: FramePacket, tracking: TrackingResult) -> None:
        self.source_card.set_value(packet.source_name)
        self.model_card.set_value(packet.market_name)
        self.fps_card.set_value(f"{tracking.fps:0.1f}")
        self.hands_card.set_value(str(len(tracking.hands)))

        if packet.pose is None:
            self.pose_card.set_value("No pose")
        else:
            self.pose_card.set_value(
                f"{packet.pose.position[0]:+.2f}, {packet.pose.position[1]:+.2f}, {packet.pose.position[2]:+.2f}"
            )

        if packet.imu is None:
            self.imu_card.set_value("No IMU")
        else:
            self.imu_card.set_value(
                f"{packet.imu[0]:+.2f}, {packet.imu[1]:+.2f}, {packet.imu[2]:+.2f}"
            )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationDisplayName("Luma Ultra Hand Viewer")
    app.setFont(QFont("Segoe UI Variable Text", 10))

    app_root = get_app_root()
    sdk_root = app_root / "VITURE_XR_Glasses_SDK_for_Windows_x86_64"
    window = HandViewerWindow(sdk_root=sdk_root)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

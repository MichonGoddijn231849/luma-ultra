from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QFont, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .diagnostics import HardwareDiagnosticsMonitor
from .device_sources import BaseFrameSource, FramePacket, open_best_source
from .hand_tracking import HandTracker, TrackingResult
from .inair_integration import (
    describe_inair_status,
    launch_inair,
    read_last_action_status,
    request_elevated_admin_action,
    run_bridge_probe,
)
from .mouse_control import AirMouseState, WindowsAirMouseController


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
        self._air_mouse = WindowsAirMouseController()
        self._air_mouse_state = AirMouseState(
            enabled=self._air_mouse.enabled,
            controlling=False,
            hand_label="",
            cursor_position=None,
            primary_gesture="Move",
            status_text="Show one hand to control the cursor.",
        )
        self._last_packet_timestamp = 0.0
        self._pending_log_messages: list[str] = []
        self._session_log_messages: list[str] = []
        self._log_file_path = self._build_log_file_path()
        self._last_frame_rgb: np.ndarray | None = None
        self._diagnostics = HardwareDiagnosticsMonitor()
        self._last_diagnostics_text = ""
        self._latest_source_summary = "Waiting for a video source..."
        self._last_inair_status_text = ""

        self.setWindowTitle("Luma Ultra Hand Viewer")
        self.resize(1560, 920)
        self._build_ui()
        self._flush_logs()
        self._diagnostics.request_refresh(self._latest_source_summary, force=True)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(33)
        self._log_timer = QTimer(self)
        self._log_timer.timeout.connect(self._flush_logs)
        self._log_timer.start(250)
        self._diagnostics_timer = QTimer(self)
        self._diagnostics_timer.timeout.connect(self._refresh_device_info)
        self._diagnostics_timer.start(5000)
        self._inair_timer = QTimer(self)
        self._inair_timer.timeout.connect(self._refresh_inair_status)
        self._inair_timer.start(4000)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._timer.stop()
        self._log_timer.stop()
        self._diagnostics_timer.stop()
        self._inair_timer.stop()
        self._tracker.close()
        self._air_mouse.set_enabled(False)
        self._source.stop()
        super().closeEvent(event)

    def changeEvent(self, event) -> None:  # type: ignore[override]
        if event.type() == QEvent.WindowStateChange:
            self._sync_fullscreen_layout()
        super().changeEvent(event)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._last_frame_rgb is not None:
            self._present_rgb_frame(self._last_frame_rgb)

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(16)

        self.video_label = QLabel("Waiting for a video source...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(320, 220)
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_label.setObjectName("VideoSurface")

        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setMinimumWidth(300)
        sidebar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        right_layout = QVBoxLayout(sidebar)
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

        button_grid = QGridLayout()
        button_grid.setHorizontalSpacing(10)
        button_grid.setVerticalSpacing(10)
        self.reconnect_button = QPushButton("Reconnect source")
        self.reconnect_button.clicked.connect(self._reconnect_source)
        self.reset_pose_button = QPushButton("Reset pose")
        self.reset_pose_button.clicked.connect(self._reset_pose)
        self.copy_logs_button = QPushButton("Copy logs")
        self.copy_logs_button.clicked.connect(self._copy_logs)
        self.clear_logs_button = QPushButton("Clear logs")
        self.clear_logs_button.clicked.connect(self._clear_logs)
        self.copy_device_info_button = QPushButton("Copy device info")
        self.copy_device_info_button.clicked.connect(self._copy_device_info)
        self.refresh_device_info_button = QPushButton("Refresh device info")
        self.refresh_device_info_button.clicked.connect(self._refresh_device_info)
        self.patch_launch_inair_button = QPushButton("Patch + launch INAIR")
        self.patch_launch_inair_button.clicked.connect(self._patch_and_launch_inair)
        self.launch_inair_button = QPushButton("Launch INAIR")
        self.launch_inair_button.clicked.connect(self._launch_inair)
        self.restore_inair_button = QPushButton("Restore INAIR")
        self.restore_inair_button.clicked.connect(self._restore_inair)
        self.probe_inair_bridge_button = QPushButton("Probe tracking bridge")
        self.probe_inair_bridge_button.clicked.connect(self._probe_inair_bridge)
        self.copy_inair_status_button = QPushButton("Copy INAIR status")
        self.copy_inair_status_button.clicked.connect(self._copy_inair_status)
        self.refresh_inair_button = QPushButton("Refresh INAIR")
        self.refresh_inair_button.clicked.connect(self._refresh_inair_status)
        self.air_mouse_button = QPushButton()
        self.air_mouse_button.clicked.connect(self._toggle_air_mouse)
        for button in (
            self.reconnect_button,
            self.reset_pose_button,
            self.air_mouse_button,
            self.copy_logs_button,
            self.clear_logs_button,
            self.copy_device_info_button,
            self.refresh_device_info_button,
            self.patch_launch_inair_button,
            self.launch_inair_button,
            self.restore_inair_button,
            self.copy_inair_status_button,
            self.refresh_inair_button,
        ):
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button_grid.addWidget(self.reconnect_button, 0, 0)
        button_grid.addWidget(self.reset_pose_button, 0, 1)
        button_grid.addWidget(self.air_mouse_button, 1, 0)
        button_grid.addWidget(self.copy_logs_button, 1, 1)
        button_grid.addWidget(self.clear_logs_button, 2, 0)
        button_grid.addWidget(self.copy_device_info_button, 2, 1)
        button_grid.addWidget(self.refresh_device_info_button, 3, 0, 1, 2)

        stat_grid = QGridLayout()
        stat_grid.setHorizontalSpacing(12)
        stat_grid.setVerticalSpacing(12)
        self.source_card = StatCard("Source")
        self.model_card = StatCard("Device")
        self.fps_card = StatCard("Tracker FPS")
        self.hands_card = StatCard("Hands")
        self.pose_card = StatCard("Pose")
        self.imu_card = StatCard("IMU")
        self.input_card = StatCard("Air Mouse")
        stat_grid.addWidget(self.source_card, 0, 0)
        stat_grid.addWidget(self.model_card, 0, 1)
        stat_grid.addWidget(self.fps_card, 1, 0)
        stat_grid.addWidget(self.hands_card, 1, 1)
        stat_grid.addWidget(self.pose_card, 2, 0)
        stat_grid.addWidget(self.imu_card, 2, 1)
        stat_grid.addWidget(self.input_card, 3, 0, 1, 2)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(180)
        self.log_output.setObjectName("LogPane")
        self.log_output.document().setMaximumBlockCount(300)
        self.log_status = QLabel("Logs are throttled and can be copied in one click.")
        self.log_status.setObjectName("LogStatus")
        self.device_info_output = QPlainTextEdit()
        self.device_info_output.setReadOnly(True)
        self.device_info_output.setMinimumHeight(180)
        self.device_info_output.setObjectName("LogPane")
        self.device_info_status = QLabel("Device info updates automatically every few seconds.")
        self.device_info_status.setObjectName("LogStatus")
        self.inair_status_output = QPlainTextEdit()
        self.inair_status_output.setReadOnly(True)
        self.inair_status_output.setMinimumHeight(180)
        self.inair_status_output.setObjectName("LogPane")
        self.inair_status_label = QLabel(
            "Patch + launch uses an elevated action because INAIR lives in Program Files. Copy INAIR status after testing on the laptop."
        )
        self.inair_status_label.setObjectName("LogStatus")

        status_tab = QWidget()
        status_layout = QVBoxLayout(status_tab)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(18)
        status_layout.addLayout(button_grid)
        status_layout.addLayout(stat_grid)
        status_layout.addStretch(1)

        logs_tab = QWidget()
        logs_layout = QVBoxLayout(logs_tab)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        logs_layout.setSpacing(12)
        logs_layout.addWidget(self.log_status)
        logs_layout.addWidget(self.log_output, 1)

        device_tab = QWidget()
        device_layout = QVBoxLayout(device_tab)
        device_layout.setContentsMargins(0, 0, 0, 0)
        device_layout.setSpacing(12)
        device_layout.addWidget(self.device_info_status)
        device_layout.addWidget(self.device_info_output, 1)

        inair_tab = QWidget()
        inair_layout = QVBoxLayout(inair_tab)
        inair_layout.setContentsMargins(0, 0, 0, 0)
        inair_layout.setSpacing(12)
        inair_button_grid = QGridLayout()
        inair_button_grid.setHorizontalSpacing(10)
        inair_button_grid.setVerticalSpacing(10)
        inair_button_grid.addWidget(self.patch_launch_inair_button, 0, 0, 1, 2)
        inair_button_grid.addWidget(self.launch_inair_button, 1, 0)
        inair_button_grid.addWidget(self.restore_inair_button, 1, 1)
        inair_button_grid.addWidget(self.probe_inair_bridge_button, 2, 0, 1, 2)
        inair_button_grid.addWidget(self.copy_inair_status_button, 3, 0)
        inair_button_grid.addWidget(self.refresh_inair_button, 3, 1)
        inair_layout.addLayout(inair_button_grid)
        inair_layout.addWidget(self.inair_status_label)
        inair_layout.addWidget(self.inair_status_output, 1)

        self.info_tabs = QTabWidget()
        self.info_tabs.setDocumentMode(True)
        self.info_tabs.setTabPosition(QTabWidget.North)
        self.info_tabs.addTab(status_tab, "Status")
        self.info_tabs.addTab(logs_tab, "Logs")
        self.info_tabs.addTab(device_tab, "Device Info")
        self.info_tabs.addTab(inair_tab, "INAIR")

        right_layout.addWidget(header)
        right_layout.addWidget(subheader)
        right_layout.addWidget(self.info_tabs, 1)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(10)
        splitter.addWidget(self.video_label)
        splitter.addWidget(sidebar)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([1000, 420])
        self.content_splitter = splitter

        root_layout.addWidget(splitter, 1)
        self.root_layout = root_layout
        self.setCentralWidget(root)
        self._install_shortcuts()
        self._apply_styles()
        self._sync_air_mouse_button()
        self._sync_fullscreen_layout()
        self._refresh_inair_status()

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
            #LogStatus {
                color: #91a7b3;
            }
            #Sidebar {
                background: transparent;
            }
            QTabWidget::pane {
                border: 1px solid #2f414b;
                border-radius: 18px;
                background: #11181d;
                padding: 12px;
            }
            QTabBar::tab {
                background: #1b262c;
                color: #b9c6ce;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                padding: 10px 14px;
                margin-right: 6px;
            }
            QTabBar::tab:selected {
                background: #f2a14a;
                color: #141414;
            }
            """
        )

    def _reconnect_source(self) -> None:
        self._source.stop()
        self._source = open_best_source(self._sdk_root)
        self._refresh_device_info()
        self._flush_logs()

    def _reset_pose(self) -> None:
        self._source.reset_pose()
        self._flush_logs()

    def _toggle_air_mouse(self) -> None:
        self._air_mouse.set_enabled(not self._air_mouse.enabled)
        self._sync_air_mouse_button()
        self._flush_logs()

    def _refresh_device_info(self) -> None:
        self._diagnostics.request_refresh(self._latest_source_summary)

    def _refresh(self) -> None:
        packet = self._source.get_latest_packet()
        if packet is None:
            return
        if packet.timestamp == self._last_packet_timestamp:
            return

        self._last_packet_timestamp = packet.timestamp
        self._latest_source_summary = (
            f"{packet.source_name} | {packet.market_name} | {packet.width}x{packet.height}"
        )
        tracking = self._tracker.process(packet.frame_bgr)
        self._air_mouse_state = self._air_mouse.update(tracking, packet.pose)
        decorated = self._decorate_frame(packet, tracking, self._air_mouse_state)
        self._present_frame(decorated)
        self._update_stats(packet, tracking)
        self._flush_logs()

    def _flush_logs(self) -> None:
        messages = self._source.drain_logs()
        messages.extend(self._air_mouse.drain_logs())
        messages.extend(self._diagnostics.drain_logs())
        if messages:
            self._append_session_logs(messages)
            self._pending_log_messages.extend(messages)

        if not self._pending_log_messages:
            self._update_device_info_view()
            return

        scroll_bar = self.log_output.verticalScrollBar()
        should_follow = scroll_bar.value() >= scroll_bar.maximum() - 4
        self.log_output.appendPlainText("\n".join(self._pending_log_messages))
        self._pending_log_messages.clear()
        if should_follow:
            scroll_bar.setValue(scroll_bar.maximum())
        self._update_log_status()
        self._update_device_info_view()

    def _copy_logs(self) -> None:
        text = "\n".join(self._session_log_messages).strip()
        if not text:
            self.log_status.setText("No logs yet.")
            return

        QApplication.clipboard().setText(text)
        self.log_status.setText(
            f"Copied {len(self._session_log_messages)} log lines from this session."
        )

    def _clear_logs(self) -> None:
        self._pending_log_messages.clear()
        self._session_log_messages.clear()
        self.log_output.clear()
        try:
            self._log_file_path.write_text("", encoding="utf-8")
        except OSError:
            pass
        self.log_status.setText("Logs cleared.")

    def _copy_device_info(self) -> None:
        text = self._diagnostics.format_snapshot().strip()
        if not text:
            self.device_info_status.setText("No device info yet.")
            return

        QApplication.clipboard().setText(text)
        self.device_info_status.setText("Copied device info for this machine.")

    def _patch_and_launch_inair(self) -> None:
        success, message = request_elevated_admin_action("patch-launch")
        self.inair_status_label.setText(message)
        if success:
            self._refresh_inair_status()

    def _launch_inair(self) -> None:
        success, message = launch_inair()
        self.inair_status_label.setText(message)
        self._refresh_inair_status()
        if success:
            self._append_session_logs([f"[{time.strftime('%H:%M:%S')}] {message}"])

    def _restore_inair(self) -> None:
        success, message = request_elevated_admin_action("restore")
        self.inair_status_label.setText(message)
        if success:
            self._refresh_inair_status()

    def _probe_inair_bridge(self) -> None:
        success, message = run_bridge_probe()
        self.inair_status_label.setText(message)
        self._refresh_inair_status()
        self._append_session_logs([f"[{time.strftime('%H:%M:%S')}] {message}"])
        if success:
            self._append_session_logs(
                [f"[{time.strftime('%H:%M:%S')}] INAIR bridge probe reported non-zero IMU samples."]
            )

    def _copy_inair_status(self) -> None:
        text = self.inair_status_output.toPlainText().strip()
        if not text:
            self.inair_status_label.setText("No INAIR status yet.")
            return

        QApplication.clipboard().setText(text)
        self.inair_status_label.setText("Copied the INAIR integration status.")

    def _sync_air_mouse_button(self) -> None:
        self.air_mouse_button.setText("Air mouse on" if self._air_mouse.enabled else "Air mouse off")

    def _build_log_file_path(self) -> Path:
        local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        log_dir = local_app_data / "LumaUltraHandViewer" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        session_stamp = time.strftime("%Y%m%d-%H%M%S")
        return log_dir / f"session-{session_stamp}.log"

    def _append_session_logs(self, messages: list[str]) -> None:
        self._session_log_messages.extend(messages)
        try:
            with self._log_file_path.open("a", encoding="utf-8") as handle:
                handle.write("\n".join(messages))
                handle.write("\n")
        except OSError:
            return

    def _update_log_status(self) -> None:
        self.log_status.setText(
            f"{len(self._session_log_messages)} log lines this session. Copy logs grabs the full session."
        )

    def _update_device_info_view(self) -> None:
        report = self._diagnostics.format_snapshot()
        if report == self._last_diagnostics_text:
            return

        self._last_diagnostics_text = report
        self.device_info_output.setPlainText(report)
        self.device_info_status.setText(
            "Copy device info and send it to me after testing on the laptop."
        )

    def _refresh_inair_status(self) -> None:
        report = describe_inair_status(get_app_root())
        if report == self._last_inair_status_text:
            last_action = read_last_action_status()
            if last_action:
                self.inair_status_label.setText(last_action.splitlines()[-1])
            return

        self._last_inair_status_text = report
        self.inair_status_output.setPlainText(report)
        last_action = read_last_action_status()
        if last_action:
            self.inair_status_label.setText(last_action.splitlines()[-1])

    def _decorate_frame(
        self,
        packet: FramePacket,
        tracking: TrackingResult,
        air_mouse_state: AirMouseState,
    ) -> np.ndarray:
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

        cursor_text = f"Air mouse: {air_mouse_state.primary_gesture}"
        if air_mouse_state.hand_label:
            cursor_text += f" with {air_mouse_state.hand_label} hand"
        cv2.putText(
            frame,
            cursor_text,
            (24, footer_y - 64),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (139, 205, 255) if air_mouse_state.enabled else (145, 145, 145),
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
        self._last_frame_rgb = frame_rgb.copy()
        self._present_rgb_frame(frame_rgb)

    def _present_rgb_frame(self, frame_rgb: np.ndarray) -> None:
        height, width = frame_rgb.shape[:2]
        image = QImage(frame_rgb.data, width, height, frame_rgb.strides[0], QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(image.copy())
        scaled = pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.video_label.setPixmap(scaled)

    def _install_shortcuts(self) -> None:
        toggle_fullscreen = QShortcut(QKeySequence("F11"), self)
        toggle_fullscreen.activated.connect(self._toggle_fullscreen)
        exit_fullscreen = QShortcut(QKeySequence(Qt.Key_Escape), self)
        exit_fullscreen.activated.connect(self._exit_fullscreen)
        self._fullscreen_shortcuts = [toggle_fullscreen, exit_fullscreen]

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _exit_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()

    def _sync_fullscreen_layout(self) -> None:
        fullscreen = self.isFullScreen()
        if fullscreen:
            self.root_layout.setContentsMargins(10, 10, 10, 10)
            self.root_layout.setSpacing(10)
            sidebar_width = min(420, max(self.width() // 3, 300))
            self.content_splitter.setSizes([max(self.width() - sidebar_width, 320), sidebar_width])
        else:
            self.root_layout.setContentsMargins(24, 24, 24, 24)
            self.root_layout.setSpacing(16)
            self.content_splitter.setSizes([1000, 420])

    def _update_stats(self, packet: FramePacket, tracking: TrackingResult) -> None:
        self.source_card.set_value(packet.source_name)
        self.model_card.set_value(packet.market_name)
        self.fps_card.set_value(f"{tracking.fps:0.1f}")
        self.hands_card.set_value(str(len(tracking.hands)))
        self.input_card.set_value(
            self._air_mouse_state.primary_gesture
            if self._air_mouse_state.enabled
            else "Disabled"
        )

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
    sdk_root = app_root / "vendor" / "viture" / "windows"
    window = HandViewerWindow(sdk_root=sdk_root)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

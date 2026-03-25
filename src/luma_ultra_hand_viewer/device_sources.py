from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


@dataclass(slots=True)
class PoseSnapshot:
    position: tuple[float, float, float]
    rotation: tuple[float, float, float, float]
    status: int


@dataclass(slots=True)
class FramePacket:
    source_name: str
    frame_bgr: np.ndarray
    timestamp: float
    width: int
    height: int
    pose: Optional[PoseSnapshot]
    imu: Optional[tuple[float, float, float, float, float, float]]
    market_name: str


class BaseFrameSource:
    def __init__(self) -> None:
        self._latest_packet: Optional[FramePacket] = None
        self._packet_lock = threading.Lock()
        self._logs: deque[str] = deque(maxlen=1000)
        self._running = False
        self._last_log_body: Optional[str] = None
        self._last_log_prefix: Optional[str] = None
        self._repeat_count = 0

    @property
    def is_running(self) -> bool:
        return self._running

    def log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        prefix = f"[{timestamp}]"
        if message == self._last_log_body:
            self._repeat_count += 1
            self._last_log_prefix = prefix
            return

        self._flush_repeated_log()
        self._logs.append(f"{prefix} {message}")
        self._last_log_body = message
        self._last_log_prefix = prefix

    def drain_logs(self) -> list[str]:
        self._flush_repeated_log()
        messages = list(self._logs)
        self._logs.clear()
        return messages

    def _flush_repeated_log(self) -> None:
        if self._repeat_count <= 0 or self._last_log_prefix is None:
            return

        suffix = "time" if self._repeat_count == 1 else "times"
        self._logs.append(
            f"{self._last_log_prefix} Previous message repeated {self._repeat_count} more {suffix}."
        )
        self._repeat_count = 0

    def get_latest_packet(self) -> Optional[FramePacket]:
        with self._packet_lock:
            if self._latest_packet is None:
                return None

            packet = self._latest_packet
            return FramePacket(
                source_name=packet.source_name,
                frame_bgr=packet.frame_bgr.copy(),
                timestamp=packet.timestamp,
                width=packet.width,
                height=packet.height,
                pose=packet.pose,
                imu=packet.imu,
                market_name=packet.market_name,
            )

    def start(self) -> bool:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def reset_pose(self) -> None:
        return None


class WebcamFrameSource(BaseFrameSource):
    def __init__(self, camera_index: int = 0) -> None:
        super().__init__()
        self._camera_index = camera_index
        self._capture: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        self._capture = cv2.VideoCapture(self._camera_index, cv2.CAP_DSHOW)
        if not self._capture.isOpened():
            self.log("Unable to open the fallback webcam.")
            return False

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        self.log("Using fallback webcam mode while VITURE hardware is unavailable.")
        return True

    def _capture_loop(self) -> None:
        assert self._capture is not None

        while self._running:
            success, frame = self._capture.read()
            if not success:
                time.sleep(0.02)
                continue

            height, width = frame.shape[:2]
            packet = FramePacket(
                source_name="Fallback webcam",
                frame_bgr=frame,
                timestamp=time.time(),
                width=width,
                height=height,
                pose=None,
                imu=None,
                market_name="Webcam",
            )
            with self._packet_lock:
                self._latest_packet = packet

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._capture is not None:
            self._capture.release()
            self._capture = None


class VitureCarinaSource(BaseFrameSource):
    _PRODUCT_ID_PATTERN = re.compile(r"PID_([0-9A-Fa-f]{4})")

    def __init__(self, sdk_root: Path) -> None:
        super().__init__()
        self._sdk_root = sdk_root
        self._bin_dir = sdk_root / "x64"
        local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        self._cache_dir = local_app_data / "LumaUltraHandViewer" / "cache" / "viture"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        self._dll_directory: Optional[os.AddDllDirectory] = None
        self._library: Optional[ctypes.CDLL] = None
        self._handle: Optional[int] = None
        self._market_name = "Unknown"
        self._imu: Optional[tuple[float, float, float, float, float, float]] = None
        self._pose: Optional[PoseSnapshot] = None
        self._callback_refs: list[object] = []

    def start(self) -> bool:
        try:
            self._load_library()
            self._bind_functions()
            product_id = self._discover_valid_product_id()
            if product_id is None:
                self.log("No connected VITURE glasses were detected.")
                return False

            self._handle = int(self._library.xr_device_provider_create(product_id))
            if not self._handle:
                self.log(f"Failed to create a provider for product id 0x{product_id:04X}.")
                return False

            self._market_name = self._get_market_name(product_id)
            self._library.xr_device_provider_set_log_level(1)
            self._register_callbacks()

            init_result = self._library.xr_device_provider_initialize(
                self._handle,
                None,
                str(self._cache_dir).encode("utf-8"),
            )
            if init_result != 0:
                self.log(f"Provider initialization failed with code {init_result}.")
                self.stop()
                return False

            start_result = self._library.xr_device_provider_start(self._handle)
            if start_result != 0:
                self.log(f"Provider start failed with code {start_result}.")
                self.stop()
                return False

            self._running = True
            self.log(f"Connected to {self._market_name} through the VITURE Windows SDK.")
            return True
        except Exception as exc:
            self.log(f"VITURE startup failed: {exc}")
            self.stop()
            return False

    def stop(self) -> None:
        self._running = False

        if self._library is not None and self._handle:
            try:
                self._library.xr_device_provider_stop(self._handle)
            except Exception:
                pass
            try:
                self._library.xr_device_provider_shutdown(self._handle)
            except Exception:
                pass
            try:
                self._library.xr_device_provider_destroy(self._handle)
            except Exception:
                pass

        self._callback_refs.clear()
        self._handle = None
        self._library = None
        if self._dll_directory is not None:
            self._dll_directory.close()
            self._dll_directory = None

    def reset_pose(self) -> None:
        if not self._library or not self._handle:
            return

        result = self._library.xr_device_provider_reset_pose_carina(self._handle)
        self.log("Pose reset requested." if result == 0 else f"Pose reset failed with code {result}.")

    def _load_library(self) -> None:
        if not self._bin_dir.exists():
            raise FileNotFoundError(f"SDK binaries not found at {self._bin_dir}")

        self._dll_directory = os.add_dll_directory(str(self._bin_dir))
        self._library = ctypes.CDLL(str(self._bin_dir / "glasses.dll"))

    def _bind_functions(self) -> None:
        assert self._library is not None

        self._library.xr_device_provider_create.argtypes = [ctypes.c_int]
        self._library.xr_device_provider_create.restype = ctypes.c_void_p

        self._library.xr_device_provider_initialize.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
        ]
        self._library.xr_device_provider_initialize.restype = ctypes.c_int

        self._library.xr_device_provider_start.argtypes = [ctypes.c_void_p]
        self._library.xr_device_provider_start.restype = ctypes.c_int

        self._library.xr_device_provider_stop.argtypes = [ctypes.c_void_p]
        self._library.xr_device_provider_stop.restype = ctypes.c_int

        self._library.xr_device_provider_shutdown.argtypes = [ctypes.c_void_p]
        self._library.xr_device_provider_shutdown.restype = ctypes.c_int

        self._library.xr_device_provider_destroy.argtypes = [ctypes.c_void_p]
        self._library.xr_device_provider_destroy.restype = None

        self._library.xr_device_provider_register_callbacks_carina.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self._library.xr_device_provider_register_callbacks_carina.restype = ctypes.c_int

        self._library.xr_device_provider_reset_pose_carina.argtypes = [ctypes.c_void_p]
        self._library.xr_device_provider_reset_pose_carina.restype = ctypes.c_int

        self._library.xr_device_provider_get_gl_pose_carina.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_double,
            ctypes.POINTER(ctypes.c_int),
        ]
        self._library.xr_device_provider_get_gl_pose_carina.restype = ctypes.c_int

        self._library.xr_device_provider_set_log_hook.argtypes = [ctypes.c_void_p]
        self._library.xr_device_provider_set_log_hook.restype = None

        self._library.xr_device_provider_set_log_level.argtypes = [ctypes.c_int]
        self._library.xr_device_provider_set_log_level.restype = None

        self._library.xr_device_provider_is_product_id_valid.argtypes = [ctypes.c_int]
        self._library.xr_device_provider_is_product_id_valid.restype = ctypes.c_bool

        self._library.xr_device_provider_get_market_name.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_int),
        ]
        self._library.xr_device_provider_get_market_name.restype = ctypes.c_int

    def _register_callbacks(self) -> None:
        assert self._library is not None
        assert self._handle is not None

        pose_callback_type = ctypes.CFUNCTYPE(None, ctypes.POINTER(ctypes.c_float), ctypes.c_double)
        vsync_callback_type = ctypes.CFUNCTYPE(None, ctypes.c_double)
        imu_callback_type = ctypes.CFUNCTYPE(None, ctypes.POINTER(ctypes.c_float), ctypes.c_double)
        camera_callback_type = ctypes.CFUNCTYPE(
            None,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_double,
            ctypes.c_int,
            ctypes.c_int,
        )
        log_callback_type = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p)

        @pose_callback_type
        def pose_callback(values_ptr: ctypes.POINTER(ctypes.c_float), timestamp: float) -> None:
            values = np.ctypeslib.as_array(values_ptr, shape=(32,)).astype(np.float32, copy=True)
            self._pose = PoseSnapshot(
                position=(float(values[0]), float(values[1]), float(values[2])),
                rotation=(float(values[3]), float(values[4]), float(values[5]), float(values[6])),
                status=0,
            )

        @vsync_callback_type
        def vsync_callback(timestamp: float) -> None:
            return None

        @imu_callback_type
        def imu_callback(values_ptr: ctypes.POINTER(ctypes.c_float), timestamp: float) -> None:
            values = np.ctypeslib.as_array(values_ptr, shape=(6,)).astype(np.float32, copy=True)
            self._imu = tuple(float(value) for value in values)

        @camera_callback_type
        def camera_callback(
            image_left0: int,
            image_right0: int,
            image_left1: int,
            image_right1: int,
            timestamp: float,
            width: int,
            height: int,
        ) -> None:
            if not image_left0 or width <= 0 or height <= 0:
                return

            frame_size = width * height
            raw_bytes = ctypes.string_at(image_left0, frame_size)
            gray = np.frombuffer(raw_bytes, dtype=np.uint8)
            if gray.size != frame_size:
                return

            gray = gray.reshape((height, width))
            frame_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            pose = self._poll_pose()
            packet = FramePacket(
                source_name="VITURE Luma Ultra",
                frame_bgr=frame_bgr,
                timestamp=float(timestamp),
                width=width,
                height=height,
                pose=pose,
                imu=self._imu,
                market_name=self._market_name,
            )

            with self._packet_lock:
                self._latest_packet = packet

        @log_callback_type
        def log_callback(level: int, tag: bytes, message: bytes) -> None:
            tag_text = tag.decode("utf-8", errors="ignore") if tag else "glasses"
            message_text = message.decode("utf-8", errors="ignore") if message else ""
            self.log(f"{tag_text}: {message_text}")

        self._callback_refs.extend(
            [pose_callback, vsync_callback, imu_callback, camera_callback, log_callback]
        )

        self._library.xr_device_provider_set_log_hook(log_callback)
        result = self._library.xr_device_provider_register_callbacks_carina(
            self._handle,
            pose_callback,
            vsync_callback,
            imu_callback,
            camera_callback,
        )
        if result != 0:
            raise RuntimeError(f"Failed to register Carina callbacks (code {result}).")

    def _poll_pose(self) -> Optional[PoseSnapshot]:
        if not self._library or not self._handle:
            return self._pose

        pose_buffer = (ctypes.c_float * 7)()
        pose_status = ctypes.c_int()
        result = self._library.xr_device_provider_get_gl_pose_carina(
            self._handle,
            pose_buffer,
            0.0,
            ctypes.byref(pose_status),
        )
        if result != 0:
            return self._pose

        pose_values = [float(value) for value in pose_buffer]
        self._pose = PoseSnapshot(
            position=(pose_values[0], pose_values[1], pose_values[2]),
            rotation=(pose_values[3], pose_values[4], pose_values[5], pose_values[6]),
            status=int(pose_status.value),
        )
        return self._pose

    def _discover_valid_product_id(self) -> Optional[int]:
        assert self._library is not None

        command = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-PnpDevice -PresentOnly | Select-Object FriendlyName,InstanceId | ConvertTo-Json -Compress",
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            self.log("Unable to enumerate connected PnP devices for VITURE discovery.")
            return None

        devices = json.loads(completed.stdout)
        if isinstance(devices, dict):
            devices = [devices]

        for device in devices:
            instance_id = device.get("InstanceId", "")
            match = self._PRODUCT_ID_PATTERN.search(instance_id)
            if not match:
                continue

            product_id = int(match.group(1), 16)
            if bool(self._library.xr_device_provider_is_product_id_valid(product_id)):
                friendly_name = device.get("FriendlyName") or instance_id
                self.log(f"Matched VITURE device candidate: {friendly_name} (0x{product_id:04X}).")
                return product_id

        return None

    def _get_market_name(self, product_id: int) -> str:
        assert self._library is not None

        buffer_size = ctypes.c_int(128)
        buffer = ctypes.create_string_buffer(buffer_size.value)
        result = self._library.xr_device_provider_get_market_name(
            product_id,
            buffer,
            ctypes.byref(buffer_size),
        )
        if result == 0 and buffer.value:
            return buffer.value.decode("utf-8", errors="ignore")
        return f"Product 0x{product_id:04X}"


def open_best_source(sdk_root: Path) -> BaseFrameSource:
    viture_source = VitureCarinaSource(sdk_root)
    if viture_source.start():
        return viture_source

    webcam_source = WebcamFrameSource()
    if webcam_source.start():
        for message in viture_source.drain_logs():
            webcam_source.log(message)
        return webcam_source

    return viture_source

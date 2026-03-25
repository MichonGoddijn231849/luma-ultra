from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_VID_PID_PATTERN = re.compile(r"VID_([0-9A-F]{4}).*PID_([0-9A-F]{4})", re.IGNORECASE)
_DISPLAY_PRODUCT_PATTERN = re.compile(r"DISPLAY\\([^\\]+)\\", re.IGNORECASE)
_DEVICE_KEYWORDS = ("viture", "inair", "xr", "glasses", "31e3", "1312")


@dataclass(slots=True)
class PnpDeviceInfo:
    status: str
    device_class: str
    friendly_name: str
    manufacturer: str
    instance_id: str


@dataclass(slots=True)
class MonitorInfo:
    instance_name: str
    manufacturer_name: str
    product_code: str
    user_friendly_name: str
    active: bool


@dataclass(slots=True)
class HardwareDiagnosticsSnapshot:
    captured_at: float
    source_summary: str
    interesting_devices: list[PnpDeviceInfo] = field(default_factory=list)
    monitors: list[MonitorInfo] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class HardwareDiagnosticsMonitor:
    def __init__(self) -> None:
        self._snapshot_lock = threading.Lock()
        self._latest_snapshot = HardwareDiagnosticsSnapshot(
            captured_at=time.time(),
            source_summary="No active source yet.",
        )
        self._logs: deque[str] = deque(maxlen=120)
        self._worker: threading.Thread | None = None
        self._refresh_requested = False

    def request_refresh(self, source_summary: str, force: bool = False) -> None:
        with self._snapshot_lock:
            self._latest_snapshot.source_summary = source_summary
        if self._worker is not None and self._worker.is_alive():
            self._refresh_requested = self._refresh_requested or force
            return

        self._worker = threading.Thread(
            target=self._refresh_worker,
            args=(source_summary,),
            daemon=True,
        )
        self._worker.start()

    def get_latest_snapshot(self) -> HardwareDiagnosticsSnapshot:
        with self._snapshot_lock:
            return self._latest_snapshot

    def drain_logs(self) -> list[str]:
        messages = list(self._logs)
        self._logs.clear()
        return messages

    def format_snapshot(self, snapshot: HardwareDiagnosticsSnapshot | None = None) -> str:
        snapshot = snapshot or self.get_latest_snapshot()
        lines = [
            "Luma Ultra hardware diagnostics",
            f"Captured: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(snapshot.captured_at))}",
            f"Active source: {snapshot.source_summary}",
            "",
            "Candidate USB and PnP devices:",
        ]

        if snapshot.interesting_devices:
            for device in snapshot.interesting_devices:
                match = _VID_PID_PATTERN.search(device.instance_id)
                vid_pid = ""
                if match:
                    vid_pid = f" | VID {match.group(1)} PID {match.group(2)}"
                lines.append(
                    f"- [{device.device_class}] {device.friendly_name or '(unnamed)'}"
                    f" | {device.manufacturer or 'Unknown'}{vid_pid}"
                )
                lines.append(f"  Status: {device.status or 'Unknown'}")
                lines.append(f"  Instance: {device.instance_id}")
        else:
            lines.append("- No VITURE/INAIR-like PnP devices were detected.")

        lines.extend(["", "Detected monitors:"])
        if snapshot.monitors:
            for monitor in snapshot.monitors:
                name = monitor.user_friendly_name or "(no EDID name)"
                active = "active" if monitor.active else "inactive"
                lines.append(
                    f"- {monitor.product_code or 'Unknown'} | {name} | {monitor.manufacturer_name or 'Unknown'} | {active}"
                )
                lines.append(f"  Instance: {monitor.instance_name}")
        else:
            lines.append("- No monitor EDID data was returned.")

        if snapshot.errors:
            lines.extend(["", "Probe notes:"])
            for error in snapshot.errors:
                lines.append(f"- {error}")

        return "\n".join(lines).strip()

    def _refresh_worker(self, source_summary: str) -> None:
        try:
            snapshot = self._collect_snapshot(source_summary)
            with self._snapshot_lock:
                self._latest_snapshot = snapshot
        finally:
            rerun = self._refresh_requested
            self._refresh_requested = False
            if rerun:
                next_summary = self.get_latest_snapshot().source_summary
                self.request_refresh(next_summary)

    def _collect_snapshot(self, source_summary: str) -> HardwareDiagnosticsSnapshot:
        payload = self._run_probe()
        errors: list[str] = []
        if payload is None:
            errors.append("PowerShell hardware probe did not return usable JSON.")
            return HardwareDiagnosticsSnapshot(
                captured_at=time.time(),
                source_summary=source_summary,
                errors=errors,
            )

        devices = [
            PnpDeviceInfo(
                status=str(item.get("Status") or ""),
                device_class=str(item.get("Class") or ""),
                friendly_name=str(item.get("FriendlyName") or ""),
                manufacturer=str(item.get("Manufacturer") or ""),
                instance_id=str(item.get("InstanceId") or ""),
            )
            for item in payload.get("pnp", [])
        ]
        monitor_activity = {
            str(item.get("InstanceName") or ""): bool(item.get("Active"))
            for item in payload.get("monitorParams", [])
        }
        monitors = [
            MonitorInfo(
                instance_name=str(item.get("InstanceName") or ""),
                manufacturer_name=_decode_wmi_string(item.get("ManufacturerName")),
                product_code=_decode_wmi_string(item.get("ProductCodeID")),
                user_friendly_name=_decode_wmi_string(item.get("UserFriendlyName")),
                active=monitor_activity.get(str(item.get("InstanceName") or ""), False),
            )
            for item in payload.get("monitors", [])
        ]
        interesting_devices = [device for device in devices if _is_interesting_device(device)]
        if not interesting_devices:
            errors.append("No candidate VITURE or INAIR USB devices matched the current probe filters.")
        if not any(monitor.active for monitor in monitors):
            errors.append("No active monitor EDID entries were flagged by WMI.")

        return HardwareDiagnosticsSnapshot(
            captured_at=time.time(),
            source_summary=source_summary,
            interesting_devices=interesting_devices,
            monitors=sorted(monitors, key=lambda item: (not item.active, item.product_code, item.user_friendly_name)),
            errors=errors,
        )

    def _run_probe(self) -> dict | None:
        script = r"""
$ErrorActionPreference = 'Stop'
$pnp = @(Get-PnpDevice -PresentOnly | Select-Object Status, Class, FriendlyName, Manufacturer, InstanceId)
$monitors = @(Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorID | Select-Object InstanceName, ManufacturerName, ProductCodeID, UserFriendlyName)
$monitorParams = @(Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorBasicDisplayParams | Select-Object InstanceName, Active)
[pscustomobject]@{
    pnp = $pnp
    monitors = $monitors
    monitorParams = $monitorParams
} | ConvertTo-Json -Depth 6 -Compress
"""
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
                creationflags=_CREATE_NO_WINDOW,
            )
        except OSError as exc:
            self._logs.append(f"[{time.strftime('%H:%M:%S')}] Device probe failed to start: {exc}")
            return None
        except subprocess.TimeoutExpired:
            self._logs.append(f"[{time.strftime('%H:%M:%S')}] Device probe timed out.")
            return None

        if completed.returncode != 0 or not completed.stdout.strip():
            self._logs.append(
                f"[{time.strftime('%H:%M:%S')}] Device probe failed: "
                f"{(completed.stderr or completed.stdout).strip()[:220]}"
            )
            return None

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            self._logs.append(f"[{time.strftime('%H:%M:%S')}] Device probe returned invalid JSON: {exc}")
            return None

        if isinstance(payload, dict):
            payload["pnp"] = _ensure_list(payload.get("pnp"))
            payload["monitors"] = _ensure_list(payload.get("monitors"))
            payload["monitorParams"] = _ensure_list(payload.get("monitorParams"))
            return payload
        return None


def _ensure_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _decode_wmi_string(value) -> str:
    if isinstance(value, list):
        chars = [chr(int(item)) for item in value if int(item) != 0]
        return "".join(chars).strip()
    return str(value or "").strip()


def _is_interesting_device(device: PnpDeviceInfo) -> bool:
    haystack = " ".join(
        [
            device.friendly_name,
            device.manufacturer,
            device.instance_id,
            device.device_class,
        ]
    ).lower()
    if any(keyword in haystack for keyword in _DEVICE_KEYWORDS):
        return True

    if device.device_class.lower() == "monitor":
        product_match = _DISPLAY_PRODUCT_PATTERN.search(device.instance_id)
        if product_match:
            return True

    return False

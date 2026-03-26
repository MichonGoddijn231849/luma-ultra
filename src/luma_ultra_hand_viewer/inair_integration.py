from __future__ import annotations

import ctypes
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from contextlib import ExitStack
from pathlib import Path


INAIR_ROOT = Path(r"C:\Program Files\INAIR Space")
INAIR_EXE = INAIR_ROOT / "INAIR Space.exe"
INAIR_PLUGIN_RELATIVE_DIR = Path("INAIRSpace") / "INAIR SpaceDesktop_Data" / "Plugins" / "x86_64"
DEFAULT_VITURE_MODE_ID = 3
PATCH_ITEMS = (
    {"asset": Path("inair.api.core.dll"), "install": Path("inair.api.core.dll"), "backup": True},
    {"asset": Path("inair.api.dfu.dll"), "install": Path("inair.api.dfu.dll"), "backup": True},
    {"asset": Path("inair.api.pipeserver.dll"), "install": Path("inair.api.pipeserver.dll"), "backup": True},
    {"asset": Path("LumaUltra.InairPatchSupport.dll"), "install": Path("LumaUltra.InairPatchSupport.dll"), "backup": False},
    {"asset": Path("unity-plugin") / "inair_dll.dll", "install": INAIR_PLUGIN_RELATIVE_DIR / "inair_dll.dll", "backup": True},
    {"asset": Path("unity-plugin") / "glasses.dll", "install": INAIR_PLUGIN_RELATIVE_DIR / "glasses.dll", "backup": False},
    {"asset": Path("unity-plugin") / "carina_vio.dll", "install": INAIR_PLUGIN_RELATIVE_DIR / "carina_vio.dll", "backup": False},
    {"asset": Path("unity-plugin") / "glew32.dll", "install": INAIR_PLUGIN_RELATIVE_DIR / "glew32.dll", "backup": False},
    {"asset": Path("unity-plugin") / "libusb-1.0.dll", "install": INAIR_PLUGIN_RELATIVE_DIR / "libusb-1.0.dll", "backup": False},
    {"asset": Path("unity-plugin") / "opencv_world4100.dll", "install": INAIR_PLUGIN_RELATIVE_DIR / "opencv_world4100.dll", "backup": False},
)
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _format_patch_item_label(item: dict[str, Path | bool]) -> str:
    install_path = Path(item["install"])
    if install_path.parent == Path("."):
        return install_path.name
    return str(install_path)


def get_app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[2]


def get_state_dir() -> Path:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    state_dir = local_app_data / "LumaUltraHandViewer" / "inair"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def get_backup_root() -> Path:
    backup_root = get_state_dir() / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    return backup_root


def get_status_file() -> Path:
    return get_state_dir() / "last-action.txt"


def get_bridge_probe_file() -> Path:
    return get_state_dir() / "last-bridge-probe.txt"


def get_patch_asset_dir(app_root: Path | None = None) -> Path:
    root = app_root or get_app_root()
    return root / "vendor" / "inair" / "patches"


def get_viture_config_path() -> Path | None:
    candidates = (
        Path(r"C:\Program Files\VITURE\SpaceWalker\config.yaml"),
        Path(r"C:\Program Files\VITURE\SpaceWalker\custom_config.yaml"),
        INAIR_ROOT / INAIR_PLUGIN_RELATIVE_DIR / "config.yaml",
        INAIR_ROOT / INAIR_PLUGIN_RELATIVE_DIR / "custom_config.yaml",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def get_app_version(app_root: Path | None = None) -> str:
    root = app_root or get_app_root()
    candidates = (
        root / "VERSION",
        Path(__file__).resolve().parents[2] / "VERSION",
    )
    for candidate in candidates:
        try:
            text = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return "unknown"


def patch_assets_present(app_root: Path | None = None) -> bool:
    patch_dir = get_patch_asset_dir(app_root)
    return all((patch_dir / item["asset"]).exists() for item in PATCH_ITEMS)


def inair_install_present() -> bool:
    return INAIR_EXE.exists() and all((INAIR_ROOT / item["install"]).exists() for item in PATCH_ITEMS if item["backup"])


def launch_inair() -> tuple[bool, str]:
    if not INAIR_EXE.exists():
        return False, f"INAIR Space was not found at {INAIR_EXE}"

    ensure_inair_state_db()
    subprocess.Popen([str(INAIR_EXE)], cwd=str(INAIR_ROOT))
    return True, f"Launched {INAIR_EXE}"


def patch_inair_install(app_root: Path | None = None) -> tuple[bool, str]:
    if not inair_install_present():
        return False, f"INAIR Space is not installed at {INAIR_ROOT}"

    if not patch_assets_present(app_root):
        return False, "Bundled INAIR patch files are missing from this app package."

    stop_running_inair()
    ensure_inair_state_db()
    patch_dir = get_patch_asset_dir(app_root)
    backup_dir = get_backup_root() / time.strftime("%Y%m%d-%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)

    for item in PATCH_ITEMS:
        install_path = INAIR_ROOT / item["install"]
        install_path.parent.mkdir(parents=True, exist_ok=True)
        if item["backup"]:
            backup_path = backup_dir / item["install"]
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(install_path, backup_path)
        shutil.copy2(patch_dir / item["asset"], install_path)

    return True, f"Patched INAIR Space and saved a backup to {backup_dir}"


def restore_inair_install() -> tuple[bool, str]:
    if not inair_install_present():
        return False, f"INAIR Space is not installed at {INAIR_ROOT}"

    stop_running_inair()
    backups = sorted(get_backup_root().glob("*"), reverse=True)
    for candidate in backups:
        if all((candidate / item["install"]).exists() for item in PATCH_ITEMS if item["backup"]):
            for item in PATCH_ITEMS:
                install_path = INAIR_ROOT / item["install"]
                if item["backup"]:
                    shutil.copy2(candidate / item["install"], install_path)
                elif install_path.exists():
                    install_path.unlink()
            return True, f"Restored INAIR Space from backup {candidate}"

    return False, "No INAIR backup set was found to restore."


def describe_inair_status(app_root: Path | None = None) -> str:
    patch_dir = get_patch_asset_dir(app_root)
    lines = [
        "INAIR integration",
        f"App version: {get_app_version(app_root)}",
        f"Installed app: {INAIR_EXE if INAIR_EXE.exists() else 'Not found'}",
        f"Bundled patch assets: {patch_dir if patch_assets_present(app_root) else 'Missing'}",
    ]

    if inair_install_present() and patch_assets_present(app_root):
        state = get_patch_state(app_root)
        lines.append(f"Patch state: {state}")
    else:
        lines.append("Patch state: unavailable")
    lines.append(f"Unity plugin target: {INAIR_ROOT / INAIR_PLUGIN_RELATIVE_DIR / 'inair_dll.dll'}")
    lines.extend(["", "Patch files:"])
    lines.extend(describe_patch_items(app_root))

    latest_backup = get_latest_backup_dir()
    lines.append(f"Latest backup: {latest_backup if latest_backup else 'None'}")
    lines.append(f"State DB: {get_inair_state_db_path()}")
    lines.append(f"State DB status: {describe_inair_state_db()}")
    lines.append(f"Preferred VITURE launch mode: {DEFAULT_VITURE_MODE_ID}")
    lines.append(f"VITURE config path: {get_viture_config_path() or 'not found'}")

    bridge_probe = read_bridge_probe_status()
    if bridge_probe:
        lines.extend(["", "Latest bridge probe:", bridge_probe])

    last_action = read_last_action_status()
    if last_action:
        lines.extend(["", "Last action:", last_action])

    log_tail = read_inair_log_tail()
    if log_tail:
        lines.extend(["", "Latest INAIR log lines:", log_tail])

    return "\n".join(lines)


def get_patch_state(app_root: Path | None = None) -> str:
    patch_dir = get_patch_asset_dir(app_root)
    matches = 0
    for item in PATCH_ITEMS:
        installed_path = INAIR_ROOT / item["install"]
        patch_path = patch_dir / item["asset"]
        if not installed_path.exists() or not patch_path.exists():
            return "unknown"
        if file_sha256(installed_path) == file_sha256(patch_path):
            matches += 1

    if matches == len(PATCH_ITEMS):
        return "patched"
    if matches == 0:
        return "unpatched"
    return "mixed"


def describe_patch_items(app_root: Path | None = None) -> list[str]:
    patch_dir = get_patch_asset_dir(app_root)
    lines: list[str] = []
    for item in PATCH_ITEMS:
        installed_path = INAIR_ROOT / item["install"]
        patch_path = patch_dir / item["asset"]
        label = _format_patch_item_label(item)
        if not patch_path.exists():
            lines.append(f"- {label}: bundled asset missing")
            continue
        if not installed_path.exists():
            lines.append(f"- {label}: installed file missing")
            continue

        state = "patched" if file_sha256(installed_path) == file_sha256(patch_path) else "different"
        lines.append(f"- {label}: {state}")

    return lines


def get_latest_backup_dir() -> Path | None:
    backups = sorted(get_backup_root().glob("*"), reverse=True)
    for candidate in backups:
        if all((candidate / item["install"]).exists() for item in PATCH_ITEMS if item["backup"]):
            return candidate
    return None


def read_last_action_status() -> str:
    status_file = get_status_file()
    if not status_file.exists():
        return ""
    try:
        return status_file.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def write_last_action_status(message: str) -> None:
    try:
        get_status_file().write_text(message.strip() + "\n", encoding="utf-8")
    except OSError:
        return


def read_bridge_probe_status() -> str:
    probe_file = get_bridge_probe_file()
    if not probe_file.exists():
        return ""
    try:
        return probe_file.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def write_bridge_probe_status(message: str) -> None:
    try:
        get_bridge_probe_file().write_text(message.strip() + "\n", encoding="utf-8")
    except OSError:
        return


def run_bridge_probe() -> tuple[bool, str]:
    success, report = probe_inair_bridge()
    stamped = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {report}"
    write_bridge_probe_status(stamped)
    first_line = next((line for line in report.splitlines() if line.strip()), "Bridge probe finished.")
    return success, first_line


def run_admin_action(action: str) -> int:
    app_root = get_app_root()
    if action == "patch-launch":
        success, message = patch_inair_install(app_root)
        if success:
            launch_success, launch_message = launch_inair()
            message = f"{message}\n{launch_message if launch_success else launch_message}"
            success = launch_success
    elif action == "restore":
        success, message = restore_inair_install()
    else:
        success, message = False, f"Unknown INAIR admin action: {action}"

    stamped = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    write_last_action_status(stamped)
    return 0 if success else 1


def request_elevated_admin_action(action: str) -> tuple[bool, str]:
    executable, parameters = get_elevation_command(action)
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, parameters, None, 1)
    if result <= 32:
        return False, "The INAIR admin action was canceled or could not be started."
    return True, "Windows opened an elevated INAIR action. Accept the UAC prompt if it appears."


def get_elevation_command(action: str) -> tuple[str, str]:
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable)), f"--inair-admin-action {action}"

    script_path = get_app_root() / "src" / "run_app.py"
    parameters = subprocess.list2cmdline([str(script_path), "--inair-admin-action", action])
    return sys.executable, parameters


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def stop_running_inair() -> None:
    subprocess.run(
        ["taskkill", "/IM", "INAIR Space.exe", "/F"],
        capture_output=True,
        text=True,
        check=False,
        creationflags=_CREATE_NO_WINDOW,
    )


def get_inair_state_db_path() -> Path:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local_app_data / "INAIR" / "WiredModeInfo.db"


def ensure_inair_state_db() -> None:
    db_path = get_inair_state_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS MonitorLayout (
                ModeID INTEGER PRIMARY KEY NOT NULL,
                ModeName TEXT UNIQUE NOT NULL,
                Volume INTEGER DEFAULT 50,
                Distance INTEGER DEFAULT 60,
                IsPrivacy INTEGER DEFAULT 0,
                IsDefault INTEGER DEFAULT 0,
                IsAutoAdjust INTEGER DEFAULT 0,
                IsVision INTEGER DEFAULT 0
            )
            """
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_default_mode ON MonitorLayout(IsDefault) WHERE IsDefault = 1"
        )
        cursor.executemany(
            """
            INSERT OR IGNORE INTO MonitorLayout
                (ModeID, ModeName, Volume, Distance, IsPrivacy, IsDefault, IsAutoAdjust, IsVision)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (1, "Ultra-wide", 50, 60, 0, 0, 0, 0),
                (2, "Dual", 50, 60, 0, 0, 0, 0),
                (3, "Triple", 50, 60, 0, 1, 0, 0),
                (4, "Quad", 50, 60, 0, 0, 0, 0),
            ),
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS GlobalMode (
                Name TEXT PRIMARY KEY NOT NULL,
                Value INTEGER DEFAULT 0
            )
            """
        )
        cursor.executemany(
            "INSERT OR IGNORE INTO GlobalMode (Name, Value) VALUES (?, ?)",
            (("IsAutoAdjust", 1), ("IsPrivacy", 0), ("IsOverease", 0)),
        )
        cursor.execute("UPDATE MonitorLayout SET Distance = 60 WHERE Distance IS NULL OR Distance < 30 OR Distance > 90")
        cursor.execute("UPDATE MonitorLayout SET IsDefault = CASE WHEN ModeID = ? THEN 1 ELSE 0 END", (DEFAULT_VITURE_MODE_ID,))
        connection.commit()


def describe_inair_state_db() -> str:
    db_path = get_inair_state_db_path()
    if not db_path.exists():
        return "missing"

    try:
        with sqlite3.connect(db_path) as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM MonitorLayout")
            monitor_rows = int(cursor.fetchone()[0] or 0)
            cursor.execute("SELECT COUNT(*) FROM GlobalMode")
            global_rows = int(cursor.fetchone()[0] or 0)
            cursor.execute("SELECT ModeID FROM MonitorLayout WHERE IsDefault = 1 LIMIT 1")
            row = cursor.fetchone()
            cursor.execute(
                """
                SELECT ModeID, Distance, IsDefault, IsPrivacy, IsAutoAdjust, IsVision
                FROM MonitorLayout
                ORDER BY ModeID
                """
            )
            mode_rows = cursor.fetchall()
    except sqlite3.Error as exc:
        return f"error: {exc}"

    default_mode = row[0] if row else "none"
    mode_summary = ", ".join(
        f"{mode_id}[d={distance},default={is_default},privacy={is_privacy},auto={is_auto_adjust},vision={is_vision}]"
        for mode_id, distance, is_default, is_privacy, is_auto_adjust, is_vision in mode_rows
    )
    return (
        f"{monitor_rows} monitor rows, {global_rows} global rows, default mode {default_mode}, "
        f"preferred mode {DEFAULT_VITURE_MODE_ID}, rows {mode_summary}"
    )


def get_inair_log_path() -> Path:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local_app_data / "inair" / "logs" / "app.log"


def read_inair_log_tail(max_lines: int = 12) -> str:
    log_path = get_inair_log_path()
    if not log_path.exists():
        return ""

    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""

    return "\n".join(lines[-max_lines:])


def probe_inair_bridge(sample_count: int = 12, sample_delay_seconds: float = 0.15) -> tuple[bool, str]:
    plugin_dir = INAIR_ROOT / INAIR_PLUGIN_RELATIVE_DIR
    plugin_path = plugin_dir / "inair_dll.dll"
    lines = [
        f"Bridge probe at {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Plugin path: {plugin_path}",
        f"Config path: {get_viture_config_path() or 'not found'}",
    ]

    if not plugin_path.exists():
        lines.append("Bridge load failed: installed inair_dll.dll was not found.")
        return False, "\n".join(lines)

    try:
        with ExitStack() as stack:
            if hasattr(os, "add_dll_directory"):
                stack.enter_context(os.add_dll_directory(str(INAIR_ROOT)))
                stack.enter_context(os.add_dll_directory(str(plugin_dir)))

            bridge = ctypes.CDLL(str(plugin_path))
            bridge.enableLog.argtypes = [ctypes.c_bool]
            bridge.enableLog.restype = None
            bridge.start_glasses_engine.argtypes = []
            bridge.start_glasses_engine.restype = ctypes.c_int
            bridge.stop_glasses_engine.argtypes = []
            bridge.stop_glasses_engine.restype = ctypes.c_int
            bridge.GetGlassesVersion.argtypes = []
            bridge.GetGlassesVersion.restype = ctypes.c_int
            bridge.GetImmersionLevel.argtypes = []
            bridge.GetImmersionLevel.restype = ctypes.c_int
            bridge.getIMU.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_longlong)]
            bridge.getIMU.restype = None
            bridge.getIMUPredicted.argtypes = [ctypes.c_float, ctypes.POINTER(ctypes.c_float)]
            bridge.getIMUPredicted.restype = None
            bridge.getIMUOffset.argtypes = [ctypes.POINTER(ctypes.c_float)]
            bridge.getIMUOffset.restype = None
            bridge.GetCurrentTimeMsec.argtypes = []
            bridge.GetCurrentTimeMsec.restype = ctypes.c_longlong

            bridge.enableLog(False)
            start_result = bridge.start_glasses_engine()
            lines.append(f"start_glasses_engine: {start_result}")
            lines.append(f"GetGlassesVersion: {bridge.GetGlassesVersion()}")
            lines.append(f"GetImmersionLevel: {bridge.GetImmersionLevel()}")
            lines.append(f"Bridge time msec: {bridge.GetCurrentTimeMsec()}")
            time.sleep(1.0)

            offset = (ctypes.c_float * 3)()
            bridge.getIMUOffset(offset)
            offset_values = [round(float(offset[index]), 5) for index in range(3)]
            lines.append(f"IMU offset: {offset_values}")

            non_zero_samples = 0
            sample_lines: list[str] = []
            for sample_index in range(sample_count):
                imu = (ctypes.c_float * 4)()
                timestamp = ctypes.c_longlong()
                bridge.getIMU(imu, ctypes.byref(timestamp))
                values = [round(float(imu[index]), 5) for index in range(4)]
                if any(abs(value) > 0.0001 for value in values):
                    non_zero_samples += 1
                if sample_index < 4 or sample_index == sample_count - 1:
                    sample_lines.append(
                        f"sample {sample_index + 1}: ts={int(timestamp.value)} imu={values}"
                    )
                time.sleep(sample_delay_seconds)

            predicted = (ctypes.c_float * 4)()
            bridge.getIMUPredicted(ctypes.c_float(0.03), predicted)
            predicted_values = [round(float(predicted[index]), 5) for index in range(4)]

            lines.append(f"Non-zero IMU samples: {non_zero_samples}/{sample_count}")
            lines.append(f"Predicted IMU (30ms): {predicted_values}")
            lines.extend(sample_lines)

            stop_result = bridge.stop_glasses_engine()
            lines.append(f"stop_glasses_engine: {stop_result}")

            success = start_result == 0 and non_zero_samples > 0
            if start_result != 0:
                lines.append("Bridge outcome: start failed, so INAIR cannot get pose from the patched plugin.")
            elif non_zero_samples == 0:
                lines.append("Bridge outcome: plugin started, but IMU samples stayed at zero.")
            else:
                lines.append("Bridge outcome: plugin started and returned non-zero IMU samples.")
            return success, "\n".join(lines)
    except OSError as exc:
        lines.append(f"Bridge load failed: {exc}")
    except Exception as exc:  # pragma: no cover - defensive hardware probing path
        lines.append(f"Bridge probe error: {exc}")

    return False, "\n".join(lines)

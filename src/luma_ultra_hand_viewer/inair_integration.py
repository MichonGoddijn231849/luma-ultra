from __future__ import annotations

import ctypes
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path


INAIR_ROOT = Path(r"C:\Program Files\INAIR Space")
INAIR_EXE = INAIR_ROOT / "INAIR Space.exe"
PATCH_FILE_NAMES = (
    "inair.api.core.dll",
    "inair.api.dfu.dll",
    "inair.api.pipeserver.dll",
    "LumaUltra.InairPatchSupport.dll",
)
BACKUP_FILE_NAMES = (
    "inair.api.core.dll",
    "inair.api.dfu.dll",
    "inair.api.pipeserver.dll",
)
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


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


def get_patch_asset_dir(app_root: Path | None = None) -> Path:
    root = app_root or get_app_root()
    return root / "vendor" / "inair" / "patches"


def patch_assets_present(app_root: Path | None = None) -> bool:
    patch_dir = get_patch_asset_dir(app_root)
    return all((patch_dir / name).exists() for name in PATCH_FILE_NAMES)


def inair_install_present() -> bool:
    return INAIR_EXE.exists() and all((INAIR_ROOT / name).exists() for name in BACKUP_FILE_NAMES)


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

    for file_name in BACKUP_FILE_NAMES:
        shutil.copy2(INAIR_ROOT / file_name, backup_dir / file_name)
    for file_name in PATCH_FILE_NAMES:
        shutil.copy2(patch_dir / file_name, INAIR_ROOT / file_name)

    return True, f"Patched INAIR Space and saved a backup to {backup_dir}"


def restore_inair_install() -> tuple[bool, str]:
    if not inair_install_present():
        return False, f"INAIR Space is not installed at {INAIR_ROOT}"

    stop_running_inair()
    backups = sorted(get_backup_root().glob("*"), reverse=True)
    for candidate in backups:
        if all((candidate / name).exists() for name in BACKUP_FILE_NAMES):
            for file_name in BACKUP_FILE_NAMES:
                shutil.copy2(candidate / file_name, INAIR_ROOT / file_name)
            helper_path = INAIR_ROOT / "LumaUltra.InairPatchSupport.dll"
            if helper_path.exists():
                helper_path.unlink()
            return True, f"Restored INAIR Space from backup {candidate}"

    return False, "No INAIR backup set was found to restore."


def describe_inair_status(app_root: Path | None = None) -> str:
    patch_dir = get_patch_asset_dir(app_root)
    lines = [
        "INAIR integration",
        f"Installed app: {INAIR_EXE if INAIR_EXE.exists() else 'Not found'}",
        f"Bundled patch assets: {patch_dir if patch_assets_present(app_root) else 'Missing'}",
    ]

    if inair_install_present() and patch_assets_present(app_root):
        state = get_patch_state(app_root)
        lines.append(f"Patch state: {state}")
    else:
        lines.append("Patch state: unavailable")

    latest_backup = get_latest_backup_dir()
    lines.append(f"Latest backup: {latest_backup if latest_backup else 'None'}")
    lines.append(f"State DB: {get_inair_state_db_path()}")
    lines.append(f"State DB status: {describe_inair_state_db()}")

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
    for file_name in PATCH_FILE_NAMES:
        installed_path = INAIR_ROOT / file_name
        patch_path = patch_dir / file_name
        if not installed_path.exists() or not patch_path.exists():
            return "unknown"
        if file_sha256(installed_path) == file_sha256(patch_path):
            matches += 1

    if matches == len(PATCH_FILE_NAMES):
        return "patched"
    if matches == 0:
        return "unpatched"
    return "mixed"


def get_latest_backup_dir() -> Path | None:
    backups = sorted(get_backup_root().glob("*"), reverse=True)
    for candidate in backups:
        if all((candidate / name).exists() for name in BACKUP_FILE_NAMES):
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
        cursor.execute("SELECT COUNT(*) FROM MonitorLayout WHERE IsDefault = 1")
        default_count = int(cursor.fetchone()[0] or 0)
        if default_count == 0:
            cursor.execute("UPDATE MonitorLayout SET IsDefault = 0")
            cursor.execute("UPDATE MonitorLayout SET IsDefault = 1 WHERE ModeID = 3")
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
    except sqlite3.Error as exc:
        return f"error: {exc}"

    default_mode = row[0] if row else "none"
    return f"{monitor_rows} monitor rows, {global_rows} global rows, default mode {default_mode}"


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

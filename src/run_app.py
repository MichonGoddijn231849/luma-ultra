from __future__ import annotations

import sys

from luma_ultra_hand_viewer.app import main
from luma_ultra_hand_viewer.inair_integration import run_admin_action

if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--inair-admin-action":
        raise SystemExit(run_admin_action(sys.argv[2]))
    raise SystemExit(main())

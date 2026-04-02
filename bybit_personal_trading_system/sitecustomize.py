from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent
root_str = str(REPO_ROOT)

if root_str not in sys.path:
    sys.path.insert(0, root_str)

# Hosted runners or plugin environments may preload unrelated top-level
# packages such as `src`. Keep this repo's packages authoritative.
for package_name in ("src", "alerts", "execution", "portfolio", "research", "strategies"):
    loaded = sys.modules.get(package_name)
    if loaded is None:
        continue
    module_file = getattr(loaded, "__file__", "") or ""
    if root_str not in module_file:
        sys.modules.pop(package_name, None)

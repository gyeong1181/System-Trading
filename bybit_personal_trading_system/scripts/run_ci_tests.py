from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(REPO_ROOT)


def _force_local_package(package_name: str) -> None:
    package_dir = REPO_ROOT / package_name
    init_path = package_dir / "__init__.py"
    if not init_path.exists():
        return

    loaded = sys.modules.get(package_name)
    if loaded is not None:
        module_file = getattr(loaded, "__file__", "") or ""
        if ROOT_STR in module_file:
            return
        sys.modules.pop(package_name, None)

    spec = importlib.util.spec_from_file_location(
        package_name,
        init_path,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"{package_name} 패키지 로딩 스펙을 만들 수 없습니다.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)


def main() -> int:
    if ROOT_STR not in sys.path:
        sys.path.insert(0, ROOT_STR)

    for package_name in ("src", "alerts", "execution", "portfolio", "research", "strategies"):
        _force_local_package(package_name)

    import src.config as config  # noqa: PLC0415
    import pytest  # noqa: PLC0415

    print(config.__file__)
    return pytest.main(["-q", "tests"])


if __name__ == "__main__":
    raise SystemExit(main())

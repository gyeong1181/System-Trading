from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(REPO_ROOT)


def _force_local_src_package() -> None:
    src_dir = REPO_ROOT / "src"
    init_path = src_dir / "__init__.py"
    config_path = src_dir / "config.py"

    if not init_path.exists() or not config_path.exists():
        raise RuntimeError("bybit_personal_trading_system/src 패키지 파일이 없습니다.")

    for package_name in ("src.config", "src.paths", "src"):
        sys.modules.pop(package_name, None)

    package = types.ModuleType("src")
    package.__file__ = str(init_path)
    package.__path__ = [str(src_dir)]
    sys.modules["src"] = package

    spec = importlib.util.spec_from_file_location("src.config", config_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("src.config 로딩 스펙을 만들 수 없습니다.")
    module = importlib.util.module_from_spec(spec)
    sys.modules["src.config"] = module
    spec.loader.exec_module(module)


def main() -> int:
    if ROOT_STR not in sys.path:
        sys.path.insert(0, ROOT_STR)

    _force_local_src_package()

    import src.config as config  # noqa: PLC0415
    import pytest  # noqa: PLC0415

    print(config.__file__)
    return pytest.main(["-q", "tests"])


if __name__ == "__main__":
    raise SystemExit(main())

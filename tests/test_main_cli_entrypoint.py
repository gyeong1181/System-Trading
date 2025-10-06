"""Tests covering execution of the main CLI module as a script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_running_main_via_script_path_succeeds() -> None:
    """Ensure the script can be executed directly without import errors."""

    script_path = Path(__file__).resolve().parents[1] / "project" / "main.py"

    result = subprocess.run(
        [sys.executable, str(script_path), "--skip-run"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        message = (
            "Execution failed with return code"
            f" {result.returncode}:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        raise AssertionError(message)


from __future__ import annotations

from src.cli import main


def test_cli_bootstrap_and_status(repo_root, capsys) -> None:
    assert main(["--root", str(repo_root), "bootstrap"]) == 0
    output = capsys.readouterr().out
    assert "초기화" in output

    assert main(["--root", str(repo_root), "status"]) == 0
    output = capsys.readouterr().out
    assert "시스템 상태" in output


def test_cli_pause_resume_kill(repo_root, capsys) -> None:
    assert main(["--root", str(repo_root), "pause"]) == 0
    assert "일시 중지" in capsys.readouterr().out

    assert main(["--root", str(repo_root), "resume"]) == 0
    assert "재개" in capsys.readouterr().out

    assert main(["--root", str(repo_root), "kill"]) == 0
    assert "킬 스위치" in capsys.readouterr().out

from __future__ import annotations

from pathlib import Path

from heyroute_video.tts.index import discover_index_tts, index_tts_doctor


def test_index_tts_discovery_accepts_explicit_project(tmp_path: Path) -> None:
    (tmp_path / "integration").mkdir()
    (tmp_path / "integration" / "generate_from_job.py").write_text("", encoding="utf-8")
    assert discover_index_tts(tmp_path) == tmp_path.resolve()


def test_current_windows_index_tts_runtime_is_reported_when_available() -> None:
    project = Path("E:/index-tts")
    if not project.exists():
        return
    result = index_tts_doctor(project)
    assert result["project_path"] == str(project.resolve())
    assert result["checks"]["integration"]["ok"] is True

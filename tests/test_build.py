from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from heyroute_video.manifest import load_manifests
from heyroute_video.pipeline import build


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_fake_build_produces_publish_bundle(tmp_path: Path) -> None:
    manifest_path = tmp_path / "job.yaml"
    manifest_path.write_text(
        "version: 1\njob_id: build-test\nvoice: {provider: fake}\n"
        f"output: {{directory: '{(tmp_path / 'output').as_posix()}'}}\nscenes:\n"
        "  - id: cover\n    visual: {type: color, color: '#173f46'}\n    duration: 0.5\n"
        "  - id: news\n    visual: {type: color, color: '#f1c48b'}\n"
        "    voiceover: {text: '本地视频测试', duration: 0.8}\n",
        encoding="utf-8",
    )
    report = build(load_manifests(manifest_path)[0])
    output = tmp_path / "output"
    assert report["status"] == "success"
    assert (output / "video.mp4").stat().st_size > 0
    assert (output / "cover.png").stat().st_size > 0
    assert (output / "subtitle.srt").exists()
    assert (output / "build-report.json").exists()

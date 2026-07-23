from __future__ import annotations

import json
from pathlib import Path

import pytest

from heyroute_video.errors import VideoError
from heyroute_video.manifest import load_manifests


def test_json_and_yaml_load_to_same_model(tmp_path: Path) -> None:
    payload = {
        "version": 1,
        "job_id": "same",
        "voice": {"provider": "fake"},
        "scenes": [
            {"id": "one", "visual": {"type": "color", "color": "#123456"}, "duration": 1}
        ],
    }
    json_path = tmp_path / "job.json"
    yaml_path = tmp_path / "job.yaml"
    json_path.write_text(json.dumps(payload), encoding="utf-8")
    yaml_path.write_text(
        "version: 1\njob_id: same\nvoice:\n  provider: fake\nscenes:\n"
        "  - id: one\n    visual:\n      type: color\n      color: '#123456'\n    duration: 1\n",
        encoding="utf-8",
    )
    assert load_manifests(json_path)[0].job_id == load_manifests(yaml_path)[0].job_id
    assert load_manifests(json_path)[0].scenes[0].visual.color == "#123456"


def test_manifest_rejects_scene_without_duration_or_voiceover(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(
        json.dumps({"version": 1, "job_id": "bad", "scenes": [{"id": "x", "visual": {"type": "color"}}]}),
        encoding="utf-8",
    )
    with pytest.raises(VideoError) as error:
        load_manifests(path)
    assert error.value.code == "manifest.duration_required"


def test_batch_manifest_expands_jobs(tmp_path: Path) -> None:
    path = tmp_path / "batch.yaml"
    path.write_text(
        "version: 1\nvoice:\n  provider: fake\njobs:\n"
        "  - job_id: a\n    scenes:\n      - id: s\n        visual: {type: color}\n        duration: 1\n"
        "  - job_id: b\n    scenes:\n      - id: s\n        visual: {type: color}\n        duration: 1\n",
        encoding="utf-8",
    )
    assert [item.job_id for item in load_manifests(path)] == ["a", "b"]

from __future__ import annotations

from pathlib import Path

from heyroute_video.manifest import load_manifests
from heyroute_video.timeline import build_timeline, write_subtitles
from heyroute_video.tts.fake import FakeTTSProvider


def test_silent_cover_is_kept_in_timeline_and_subtitles(tmp_path: Path) -> None:
    manifest_path = tmp_path / "job.yaml"
    manifest_path.write_text(
        "version: 1\njob_id: test\nvoice: {provider: fake}\nscenes:\n"
        "  - id: cover\n    visual: {type: color}\n    duration: 2\n"
        "  - id: news\n    visual: {type: color}\n    voiceover: {text: hello, duration: 1}\n",
        encoding="utf-8",
    )
    manifest = load_manifests(manifest_path)[0]
    audio_dir = tmp_path / "audio"
    segments = FakeTTSProvider().synthesize(manifest.scenes, audio_dir)
    timeline = build_timeline(manifest, segments)
    assert [item.scene.id for item in timeline] == ["cover", "news"]
    assert timeline[1].start == 2
    srt, vtt = write_subtitles(timeline, tmp_path / "out")
    assert "00:00:02,000 --> 00:00:03,000" in srt.read_text(encoding="utf-8")
    assert "WEBVTT" in vtt.read_text(encoding="utf-8")

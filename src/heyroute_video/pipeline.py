from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import VideoError
from .events import EventSink
from .manifest import Manifest, manifest_to_dict
from .render import render_video
from .timeline import build_timeline, write_subtitles
from .tools import write_silence
from .tts import FakeTTSProvider, IndexTTSProvider, TTSProvider


def provider_for(manifest: Manifest) -> TTSProvider:
    if manifest.voice.provider == "fake":
        return FakeTTSProvider()
    if manifest.voice.provider == "indextts":
        return IndexTTSProvider(manifest.voice)
    raise VideoError("tts.unsupported_provider", f"Unsupported TTS provider: {manifest.voice.provider}")


def _check_visuals(manifest: Manifest) -> None:
    for scene in manifest.scenes:
        if scene.visual.type == "image" and (not scene.visual.path or not scene.visual.path.is_file()):
            raise VideoError("asset.missing", f"Missing image for scene {scene.id}", path=str(scene.visual.path))


def build(manifest: Manifest, *, sink: EventSink | None = None) -> dict[str, Any]:
    sink = sink or EventSink()
    sink.emit("started", job_id=manifest.job_id, message="build started")
    output_dir = manifest.output.directory
    output_dir.mkdir(parents=True, exist_ok=True)
    _check_visuals(manifest)
    provider = provider_for(manifest)
    sink.emit("progress", job_id=manifest.job_id, stage="tts", provider=provider.name)
    audio_dir = output_dir / "audio"
    audio_segments = provider.synthesize(manifest.scenes, audio_dir)
    audio_by_scene = {segment.scene_id: segment for segment in audio_segments}
    for scene in manifest.scenes:
        if scene.voiceover and scene.id not in audio_by_scene:
            raise VideoError("tts.segment_missing", f"No audio generated for scene {scene.id}")
    if not audio_segments:
        raise VideoError("tts.no_audio", "At least one scene must contain voiceover")
    timeline = build_timeline(manifest, audio_segments)
    # The final audio track must cover silent scenes too (for example a cover
    # page without narration), otherwise -shortest would truncate the video.
    render_audio_paths = []
    for index, item in enumerate(timeline, start=1):
        if item.audio:
            render_audio_paths.append(item.audio.path)
        else:
            silence_path = output_dir / "audio" / f"silence_{index:03d}_{item.scene.id}.wav"
            if not silence_path.exists():
                write_silence(silence_path, item.duration)
            render_audio_paths.append(silence_path)
    sink.emit("progress", job_id=manifest.job_id, stage="subtitles")
    srt_path, vtt_path = write_subtitles(timeline, output_dir)
    sink.emit("progress", job_id=manifest.job_id, stage="render")
    artifacts = render_video(manifest, timeline, render_audio_paths)
    validation = artifacts.pop("validation")
    (output_dir / "title.txt").write_text(manifest.publish.title + "\n", encoding="utf-8")
    (output_dir / "description.txt").write_text(manifest.publish.description + "\n", encoding="utf-8")
    (output_dir / "tags.txt").write_text("\n".join(manifest.publish.tags) + "\n", encoding="utf-8")
    report = {
        "status": "success",
        "job_id": manifest.job_id,
        "profile": manifest.profile,
        "duration": sum(item.duration for item in timeline),
        "scene_count": len(timeline),
        "provider": provider.name,
        "validation": validation,
        "manifest": manifest_to_dict(manifest),
        "artifacts": {
            "video": str(artifacts["video"]),
            "audio": str(artifacts["audio"]),
            "cover": str(artifacts["cover"]),
            "subtitle_srt": str(srt_path),
            "subtitle_vtt": str(vtt_path),
            "title": str(output_dir / "title.txt"),
            "description": str(output_dir / "description.txt"),
            "tags": str(output_dir / "tags.txt"),
        },
        "segments": [
            {"scene_id": item.scene.id, "start": item.start, "duration": item.duration,
             "audio": str(item.audio.path) if item.audio else None}
            for item in timeline
        ],
    }
    report_path = output_dir / "build-report.json"
    resolved_path = output_dir / "manifest.resolved.json"
    resolved_path.write_text(json.dumps(report["manifest"], ensure_ascii=False, indent=2), encoding="utf-8")
    report["artifacts"]["report"] = str(report_path)
    report["artifacts"]["resolved_manifest"] = str(resolved_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, path in report["artifacts"].items():
        if Path(path).exists():
            sink.emit("artifact", job_id=manifest.job_id, name=name, artifact=path)
    sink.emit("completed", job_id=manifest.job_id, status="success")
    return report

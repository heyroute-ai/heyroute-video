from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import VideoError
from .manifest import Manifest, Scene
from .tts.base import AudioSegment


@dataclass(frozen=True)
class TimedScene:
    scene: Scene
    start: float
    duration: float
    audio: AudioSegment | None


def build_timeline(manifest: Manifest, audio_segments: list[AudioSegment]) -> list[TimedScene]:
    audio_by_scene = {segment.scene_id: segment for segment in audio_segments}
    result: list[TimedScene] = []
    cursor = 0.0
    for scene in manifest.scenes:
        audio = audio_by_scene.get(scene.id)
        duration = audio.duration if audio else (scene.duration or (scene.voiceover.duration if scene.voiceover else None))
        if duration is None:
            raise VideoError("timeline.duration_missing", f"No duration for scene {scene.id}")
        result.append(TimedScene(scene=scene, start=cursor, duration=duration, audio=audio))
        cursor += duration
    return result


def _timestamp(seconds: float, separator: str) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def write_subtitles(timeline: list[TimedScene], output_dir: Path) -> tuple[Path, Path]:
    srt_path = output_dir / "subtitle.srt"
    vtt_path = output_dir / "subtitle.vtt"
    entries = [item for item in timeline if item.scene.voiceover and item.scene.voiceover.text.strip()]
    srt_lines: list[str] = []
    for index, item in enumerate(entries, start=1):
        srt_lines.extend(
            [
                str(index),
                f"{_timestamp(item.start, ',')} --> {_timestamp(item.start + item.duration, ',')}",
                item.scene.voiceover.text.strip(),
                "",
            ]
        )
    vtt_lines = ["WEBVTT", ""]
    for item in entries:
        vtt_lines.extend(
            [
                f"{_timestamp(item.start, '.')} --> {_timestamp(item.start + item.duration, '.')}",
                item.scene.voiceover.text.strip(),
                "",
            ]
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    vtt_path.write_text("\n".join(vtt_lines), encoding="utf-8")
    return srt_path, vtt_path

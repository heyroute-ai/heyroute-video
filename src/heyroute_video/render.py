from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .errors import VideoError
from .manifest import Manifest
from .timeline import TimedScene
from .tools import find_executable, merge_wavs, run_command


def _ffmpeg() -> str:
    executable = find_executable("ffmpeg")
    if not executable:
        raise VideoError("runtime.ffmpeg_missing", "ffmpeg was not found on PATH")
    return executable


def _render_scene(ffmpeg: str, item: TimedScene, output: Path, manifest: Manifest) -> None:
    visual = item.scene.visual
    size = f"{manifest.output.width}:{manifest.output.height}"
    lavfi_size = f"{manifest.output.width}x{manifest.output.height}"
    filter_value = (
        f"scale={size}:force_original_aspect_ratio=increase,crop={size},format=yuv420p"
    )
    if visual.type == "image":
        if not visual.path or not visual.path.exists():
            raise VideoError("asset.missing", f"Missing image: {visual.path}", path=str(visual.path))
        command = [
            ffmpeg,
            "-y",
            "-loop",
            "1",
            "-i",
            str(visual.path),
            "-t",
            f"{item.duration:.3f}",
            "-vf",
            filter_value,
            "-r",
            str(manifest.output.fps),
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output),
        ]
    elif visual.type == "color":
        command = [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={visual.color}:s={lavfi_size}:r={manifest.output.fps}",
            "-t",
            f"{item.duration:.3f}",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output),
        ]
    else:
        raise VideoError("render.unsupported_visual", f"Unsupported visual type: {visual.type}")
    completed = run_command(command)
    if completed.returncode != 0:
        raise VideoError("render.scene_failed", completed.stderr[-2000:] or "Scene render failed")


def _concat_videos(ffmpeg: str, clips: list[Path], output: Path) -> None:
    list_path = output.parent / "video-concat.txt"
    list_path.write_text("\n".join(f"file '{path.as_posix()}'" for path in clips), encoding="utf-8")
    completed = run_command([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(output)])
    if completed.returncode != 0:
        raise VideoError("render.concat_failed", completed.stderr[-2000:] or "Video concat failed")


def validate_video_output(manifest: Manifest, video_path: Path) -> dict[str, object]:
    ffprobe = find_executable("ffprobe")
    if not ffprobe:
        raise VideoError("runtime.ffprobe_missing", "ffprobe was not found on PATH")
    completed = run_command(
        [ffprobe, "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,duration", "-of", "json", str(video_path)]
    )
    if completed.returncode != 0:
        raise VideoError("validate.probe_failed", completed.stderr[-2000:] or "ffprobe failed")
    try:
        payload = json.loads(completed.stdout)
        streams = payload["streams"]
        video = next(item for item in streams if item.get("codec_type") == "video")
        audio = next(item for item in streams if item.get("codec_type") == "audio")
        video_duration = float(video["duration"])
        audio_duration = float(audio["duration"])
    except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise VideoError("validate.probe_invalid", "Video probe did not contain usable audio/video streams") from exc
    if (video.get("width"), video.get("height")) != (manifest.output.width, manifest.output.height):
        raise VideoError(
            "validate.dimensions",
            f"Expected {manifest.output.width}x{manifest.output.height}, got {video.get('width')}x{video.get('height')}",
        )
    if abs(video_duration - audio_duration) > 0.25:
        raise VideoError(
            "validate.duration_mismatch",
            f"Audio/video duration differs by {abs(video_duration - audio_duration):.3f}s",
        )
    return {
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
        "width": video.get("width"),
        "height": video.get("height"),
        "video_duration": video_duration,
        "audio_duration": audio_duration,
        "duration_delta": abs(video_duration - audio_duration),
    }


def render_video(manifest: Manifest, timeline: list[TimedScene], audio_segments: list[Path]) -> dict[str, Path]:
    ffmpeg = _ffmpeg()
    output_dir = manifest.output.directory
    output_dir.mkdir(parents=True, exist_ok=True)
    video_path = output_dir / "video.mp4"
    audio_path = output_dir / "audio.wav"
    cover_path = output_dir / "cover.png"
    with tempfile.TemporaryDirectory(prefix="heyroute-video-", dir=output_dir) as temp:
        temp_dir = Path(temp)
        clips = []
        for index, item in enumerate(timeline, start=1):
            clip = temp_dir / f"scene_{index:03d}.mp4"
            _render_scene(ffmpeg, item, clip, manifest)
            clips.append(clip)
        silent_video = temp_dir / "silent.mp4"
        _concat_videos(ffmpeg, clips, silent_video)
        merge_wavs(audio_segments, audio_path)
        completed = run_command(
            [
                ffmpeg,
                "-y",
                "-i",
                str(silent_video),
                "-i",
                str(audio_path),
                "-shortest",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(video_path),
            ]
        )
        if completed.returncode != 0:
            raise VideoError("render.audio_mux_failed", completed.stderr[-2000:] or "Audio mux failed")
        completed = run_command(
            [ffmpeg, "-y", "-i", str(clips[0]), "-frames:v", "1", str(cover_path)]
        )
        if completed.returncode != 0:
            raise VideoError("render.cover_failed", completed.stderr[-2000:] or "Cover export failed")
    if not video_path.exists() or video_path.stat().st_size == 0:
        raise VideoError("render.output_missing", "FFmpeg did not produce video.mp4")
    validation = validate_video_output(manifest, video_path)
    return {"video": video_path, "audio": audio_path, "cover": cover_path, "validation": validation}

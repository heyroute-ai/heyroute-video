from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import VideoError


@dataclass(frozen=True)
class Visual:
    type: str
    path: Path | None = None
    color: str | None = None


@dataclass(frozen=True)
class Voiceover:
    text: str
    duration: float | None = None


@dataclass(frozen=True)
class Source:
    name: str
    url: str | None = None


@dataclass(frozen=True)
class Scene:
    id: str
    visual: Visual
    voiceover: Voiceover | None = None
    duration: float | None = None
    layout: str = "visual"
    source: Source | None = None


@dataclass(frozen=True)
class Voice:
    provider: str = "fake"
    reference_audio: Path | None = None
    language: str = "zh-CN"
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Output:
    directory: Path
    width: int = 1080
    height: int = 1920
    fps: int = 30


@dataclass(frozen=True)
class Publish:
    title: str = ""
    description: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Manifest:
    version: int
    job_id: str
    profile: str
    source_path: Path
    base_dir: Path
    output: Output
    voice: Voice
    scenes: tuple[Scene, ...]
    publish: Publish


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise VideoError("manifest.invalid_type", f"{field_name} must be an object")
    return value


def _required_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VideoError("manifest.required", f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_positive_number(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise VideoError("manifest.invalid_number", f"{field_name} must be greater than zero")
    return float(value)


def _resolve_path(raw: Any, base_dir: Path, field_name: str) -> Path:
    value = _required_string(raw, field_name)
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base_dir / path).resolve()


def _parse_scene(raw: Any, base_dir: Path, index: int) -> Scene:
    data = _mapping(raw, f"scenes[{index}]")
    scene_id = _required_string(data.get("id"), f"scenes[{index}].id")
    visual_data = _mapping(data.get("visual"), f"scenes[{index}].visual")
    visual_type = _required_string(visual_data.get("type"), f"scenes[{index}].visual.type").lower()
    if visual_type not in {"image", "color"}:
        raise VideoError("manifest.unsupported_visual", f"Unsupported visual type: {visual_type}")
    visual_path = None
    color = None
    if visual_type == "image":
        visual_path = _resolve_path(visual_data.get("path"), base_dir, f"scenes[{index}].visual.path")
    else:
        color = _required_string(visual_data.get("color", "#183f46"), f"scenes[{index}].visual.color")

    voice_data = data.get("voiceover")
    voiceover = None
    if voice_data is not None:
        voice_map = _mapping(voice_data, f"scenes[{index}].voiceover")
        voiceover = Voiceover(
            text=_required_string(voice_map.get("text"), f"scenes[{index}].voiceover.text"),
            duration=_optional_positive_number(
                voice_map.get("duration"), f"scenes[{index}].voiceover.duration"
            ),
        )

    duration = _optional_positive_number(data.get("duration"), f"scenes[{index}].duration")
    if voiceover is None and duration is None:
        raise VideoError(
            "manifest.duration_required",
            f"scenes[{index}] needs voiceover or duration",
            path=scene_id,
        )

    source = None
    if data.get("source") is not None:
        source_data = _mapping(data["source"], f"scenes[{index}].source")
        source = Source(
            name=_required_string(source_data.get("name"), f"scenes[{index}].source.name"),
            url=source_data.get("url"),
        )

    return Scene(
        id=scene_id,
        visual=Visual(type=visual_type, path=visual_path, color=color),
        voiceover=voiceover,
        duration=duration,
        layout=str(data.get("layout", "visual")),
        source=source,
    )


def _parse_payload(payload: Any, source_path: Path, *, overrides: dict[str, Any] | None = None) -> Manifest:
    if not isinstance(payload, dict):
        raise VideoError("manifest.invalid_root", "Manifest must contain an object")
    data = {**payload, **(overrides or {})}
    version = data.get("version", 1)
    if version != 1:
        raise VideoError("manifest.unsupported_version", "Only manifest version 1 is supported")
    base_dir = source_path.parent.resolve()
    output_data = _mapping(data.get("output"), "output")
    raw_output = output_data.get("directory", "./output")
    output_dir = _resolve_path(raw_output, base_dir, "output.directory")
    width = int(output_data.get("width", 1080))
    height = int(output_data.get("height", 1920))
    fps = int(output_data.get("fps", 30))
    if width <= 0 or height <= 0 or fps <= 0:
        raise VideoError("manifest.invalid_profile", "output width, height and fps must be positive")

    voice_data = _mapping(data.get("voice"), "voice")
    reference = voice_data.get("reference_audio")
    voice = Voice(
        provider=str(voice_data.get("provider", "fake")).lower(),
        reference_audio=_resolve_path(reference, base_dir, "voice.reference_audio") if reference else None,
        language=str(voice_data.get("language", "zh-CN")),
        options=_mapping(voice_data.get("options"), "voice.options"),
    )
    scenes_data = data.get("scenes")
    if not isinstance(scenes_data, list) or not scenes_data:
        raise VideoError("manifest.scenes_required", "scenes must be a non-empty array")
    scenes = tuple(_parse_scene(item, base_dir, i) for i, item in enumerate(scenes_data))
    ids = [scene.id for scene in scenes]
    if len(set(ids)) != len(ids):
        raise VideoError("manifest.duplicate_scene", "scene ids must be unique")

    publish_data = _mapping(data.get("publish"), "publish")
    tags = publish_data.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise VideoError("manifest.invalid_tags", "publish.tags must be an array of strings")
    return Manifest(
        version=1,
        job_id=_required_string(data.get("job_id"), "job_id"),
        profile=str(data.get("profile", "vertical-news-1080x1920")),
        source_path=source_path.resolve(),
        base_dir=base_dir,
        output=Output(directory=output_dir, width=width, height=height, fps=fps),
        voice=voice,
        scenes=scenes,
        publish=Publish(
            title=str(publish_data.get("title", "")),
            description=str(publish_data.get("description", "")),
            tags=tuple(tags),
        ),
    )


def _read_payload(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            payload = json.loads(text)
        elif path.suffix.lower() in {".yaml", ".yml"}:
            payload = yaml.safe_load(text)
        else:
            raise VideoError("manifest.unsupported_file", f"Use .json, .yaml or .yml: {path}")
    except json.JSONDecodeError as exc:
        raise VideoError("manifest.parse_error", str(exc), path=str(path)) from exc
    except yaml.YAMLError as exc:
        raise VideoError("manifest.parse_error", str(exc), path=str(path)) from exc
    if not isinstance(payload, dict):
        raise VideoError("manifest.invalid_root", "Manifest must contain an object", path=str(path))
    return payload


def load_manifests(path: Path) -> list[Manifest]:
    payload = _read_payload(path)
    jobs = payload.get("jobs")
    if jobs is None:
        return [_parse_payload(payload, path)]
    if not isinstance(jobs, list) or not jobs:
        raise VideoError("manifest.jobs_required", "jobs must be a non-empty array")
    shared = {key: value for key, value in payload.items() if key != "jobs"}
    manifests = []
    for index, job in enumerate(jobs):
        if not isinstance(job, dict):
            raise VideoError("manifest.invalid_job", f"jobs[{index}] must be an object")
        job_data = dict(job)
        job_id = job_data.get("job_id")
        if "output" not in job_data and isinstance(job_id, str) and job_id.strip():
            job_data["output"] = {"directory": f"./output/{job_id.strip()}"}
        manifests.append(_parse_payload(shared, path, overrides=job_data))
    return manifests


def manifest_to_dict(manifest: Manifest) -> dict[str, Any]:
    return {
        "version": manifest.version,
        "job_id": manifest.job_id,
        "profile": manifest.profile,
        "output": {
            "directory": str(manifest.output.directory),
            "width": manifest.output.width,
            "height": manifest.output.height,
            "fps": manifest.output.fps,
        },
        "voice": {
            "provider": manifest.voice.provider,
            "reference_audio": str(manifest.voice.reference_audio)
            if manifest.voice.reference_audio
            else None,
            "language": manifest.voice.language,
            "options": manifest.voice.options,
        },
        "scenes": [
            {
                "id": scene.id,
                "visual": {
                    "type": scene.visual.type,
                    "path": str(scene.visual.path) if scene.visual.path else None,
                    "color": scene.visual.color,
                },
                "voiceover": (
                    {"text": scene.voiceover.text, "duration": scene.voiceover.duration}
                    if scene.voiceover
                    else None
                ),
                "duration": scene.duration,
                "layout": scene.layout,
                "source": (
                    {"name": scene.source.name, "url": scene.source.url} if scene.source else None
                ),
            }
            for scene in manifest.scenes
        ],
        "publish": {
            "title": manifest.publish.title,
            "description": manifest.publish.description,
            "tags": list(manifest.publish.tags),
        },
    }

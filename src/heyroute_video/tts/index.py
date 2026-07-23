from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..errors import VideoError
from ..manifest import Scene, Voice
from ..tools import require_file, sha256_file, wav_duration
from .base import AudioSegment, TTSProvider


def discover_index_tts(project_path: Path | None = None) -> Path | None:
    candidates = []
    if project_path:
        candidates.append(project_path)
    env_path = os.environ.get("HEYROUTE_INDEXTTS_HOME")
    if env_path:
        candidates.append(Path(env_path))
    if sys.platform == "win32":
        candidates.append(Path("E:/index-tts"))
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if (resolved / "integration" / "generate_from_job.py").exists():
            return resolved
    return None


def index_tts_doctor(project_path: Path | None = None) -> dict[str, Any]:
    discovered = discover_index_tts(project_path)
    checks: dict[str, Any] = {"project_path": str(discovered) if discovered else None, "checks": {}}
    if not discovered:
        checks["status"] = "missing"
        checks["checks"]["project"] = {"ok": False, "message": "IndexTTS project not found"}
        return checks
    python_path = discovered / ".venv" / "Scripts" / "python.exe"
    if not python_path.exists():
        python_path = discovered / ".venv" / "bin" / "python"
    integration = discovered / "integration" / "generate_from_job.py"
    model_dir = discovered / "checkpoints"
    checks["checks"] = {
        "project": {"ok": True, "path": str(discovered)},
        "python": {"ok": python_path.exists(), "path": str(python_path)},
        "integration": {"ok": integration.exists(), "path": str(integration)},
        "model_dir": {"ok": model_dir.exists(), "path": str(model_dir)},
        "config": {"ok": (model_dir / "config.yaml").exists(), "path": str(model_dir / "config.yaml")},
    }
    checks["status"] = "ready" if all(item["ok"] for item in checks["checks"].values()) else "incomplete"
    return checks


class IndexTTSProvider(TTSProvider):
    name = "indextts"

    def __init__(self, voice: Voice):
        project_path_raw = voice.options.get("project_path")
        self.project_path = discover_index_tts(Path(project_path_raw) if project_path_raw else None)
        if not self.project_path:
            raise VideoError(
                "tts.indextts_missing",
                "IndexTTS project not found",
                hint="Set voice.options.project_path or HEYROUTE_INDEXTTS_HOME",
            )
        self.voice = voice

    def _python(self) -> Path:
        candidates = [
            self.project_path / ".venv" / "Scripts" / "python.exe",
            self.project_path / ".venv" / "bin" / "python",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise VideoError("tts.python_missing", "IndexTTS virtualenv Python not found")

    def synthesize(self, scenes: tuple[Scene, ...], output_dir: Path) -> list[AudioSegment]:
        reference = self.voice.reference_audio
        if reference is None:
            raise VideoError("tts.reference_required", "IndexTTS requires voice.reference_audio")
        require_file(reference, field="voice.reference_audio")
        narrated_scenes = [scene for scene in scenes if scene.voiceover]
        narration = [{"slide_no": index, "tts_text": scene.voiceover.text}
                     for index, scene in enumerate(narrated_scenes, start=1)]
        if not narrated_scenes:
            return []
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        cache_payload = {
            "provider": self.name,
            "texts": [item["tts_text"] for item in narration],
            "reference_sha256": sha256_file(reference),
            "language": self.voice.language,
            "options": self.voice.options,
        }
        cache_key = hashlib.sha256(
            json.dumps(cache_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        cache_path = output_dir / "cache-key.json"
        cached_segments = [
            output_dir / f"segment_{index:03d}.wav" for index in range(1, len(narration) + 1)
        ]
        if cache_path.exists() and all(path.exists() for path in cached_segments):
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                cached = {}
            if cached.get("key") == cache_key and not self.voice.options.get("force", False):
                return [
                    AudioSegment(scene.id, path, wav_duration(path), scene.voiceover.text)
                    for scene, path in zip(narrated_scenes, cached_segments, strict=True)
                ]
        job_path = output_dir / "indextts-job.json"
        payload = {
            "version": 1,
            "narration_json_path": str(output_dir / "narration.json"),
            "reference_voice_path": str(reference),
            "output_dir": str(output_dir),
            "config_path": str(self.project_path / "checkpoints" / "config.yaml"),
            "model_dir": str(self.project_path / "checkpoints"),
            "fp16": bool(self.voice.options.get("fp16", True)),
            "deepspeed": bool(self.voice.options.get("deepspeed", False)),
            "emo_vector": self.voice.options.get("emo_vector"),
            "use_random": bool(self.voice.options.get("use_random", False)),
            "temperature": float(self.voice.options.get("temperature", 0.68)),
            "interval_silence": int(self.voice.options.get("interval_silence", 150)),
            "force": bool(self.voice.options.get("force", False)),
        }
        (output_dir / "narration.json").write_text(
            json.dumps({"series": "heyroute-video", "speaker": "default", "language": self.voice.language,
                        "total_slides": len(narration), "slides": narration}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        job_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        integration = self.project_path / "integration" / "generate_from_job.py"
        completed = subprocess.run(
            [str(self._python()), str(integration), "--job", str(job_path)],
            cwd=self.project_path,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout)[-2000:]
            raise VideoError("tts.indextts_failed", detail or "IndexTTS failed")
        cache_path.write_text(
            json.dumps({"key": cache_key, "inputs": cache_payload}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        segments: list[AudioSegment] = []
        for index, scene in enumerate(narrated_scenes, start=1):
            path = output_dir / f"segment_{index:03d}.wav"
            require_file(path, field=f"IndexTTS segment {scene.id}")
            segments.append(AudioSegment(scene.id, path, wav_duration(path), scene.voiceover.text))
        return segments

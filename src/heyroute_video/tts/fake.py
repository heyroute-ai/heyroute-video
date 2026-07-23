from __future__ import annotations

from pathlib import Path

from ..manifest import Scene
from ..tools import write_silence
from .base import AudioSegment, TTSProvider


class FakeTTSProvider(TTSProvider):
    """Deterministic, offline provider used by examples and tests."""

    name = "fake"

    def synthesize(self, scenes: tuple[Scene, ...], output_dir: Path) -> list[AudioSegment]:
        segments: list[AudioSegment] = []
        for index, scene in enumerate(scenes, start=1):
            if scene.voiceover is None:
                continue
            duration = scene.voiceover.duration or max(1.0, len(scene.voiceover.text) / 5.0)
            path = output_dir / f"segment_{index:03d}_{scene.id}.wav"
            if not path.exists():
                write_silence(path, duration)
            segments.append(AudioSegment(scene.id, path, duration, scene.voiceover.text))
        return segments

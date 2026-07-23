from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..manifest import Scene


@dataclass(frozen=True)
class AudioSegment:
    scene_id: str
    path: Path
    duration: float
    text: str


class TTSProvider:
    name = "base"

    def synthesize(self, scenes: tuple[Scene, ...], output_dir: Path) -> list[AudioSegment]:
        raise NotImplementedError

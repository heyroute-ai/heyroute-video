from __future__ import annotations

import platform
import sys
from typing import Any

from .tools import find_executable


def doctor() -> dict[str, Any]:
    ffmpeg = find_executable("ffmpeg")
    ffprobe = find_executable("ffprobe")
    return {
        "status": "ready" if ffmpeg and ffprobe else "incomplete",
        "runtime": {"python": sys.version.split()[0], "platform": platform.platform()},
        "checks": {
            "ffmpeg": {"ok": bool(ffmpeg), "path": ffmpeg},
            "ffprobe": {"ok": bool(ffprobe), "path": ffprobe},
        },
    }

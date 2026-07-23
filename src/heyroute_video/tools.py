from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Sequence

from .errors import VideoError


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_file(path: Path, *, field: str) -> None:
    if not path.exists() or not path.is_file():
        raise VideoError("asset.missing", f"Missing {field}: {path}", path=str(path))


def find_executable(name: str) -> str | None:
    return shutil.which(name)


def run_command(command: Sequence[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command), cwd=cwd, text=True, capture_output=True, check=False
        )
    except OSError as exc:
        raise VideoError("runtime.unavailable", str(exc), hint=f"Install or expose {command[0]}") from exc


def wav_duration(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate()
            if rate <= 0:
                raise ValueError("invalid sample rate")
            return frames / rate
    except (wave.Error, EOFError, OSError, ValueError) as exc:
        raise VideoError("audio.invalid", f"Cannot read WAV duration: {path}") from exc


def write_silence(path: Path, duration: float, *, sample_rate: int = 16_000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = max(1, int(round(duration * sample_rate)))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * frames)


def merge_wavs(inputs: list[Path], output: Path) -> None:
    if not inputs:
        raise VideoError("audio.empty", "No audio segments to merge")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with wave.open(str(inputs[0]), "rb") as first:
            params = first.getparams()
            frames = [first.readframes(first.getnframes())]
        for path in inputs[1:]:
            with wave.open(str(path), "rb") as handle:
                other = handle.getparams()
                if (other.nchannels, other.sampwidth, other.framerate, other.comptype, other.compname) != (
                    params.nchannels,
                    params.sampwidth,
                    params.framerate,
                    params.comptype,
                    params.compname,
                ):
                    raise ValueError("incompatible WAV parameters")
                frames.append(handle.readframes(handle.getnframes()))
        with wave.open(str(output), "wb") as handle:
            handle.setparams(params)
            handle.writeframes(b"".join(frames))
    except (wave.Error, EOFError, OSError, ValueError):
        # IndexTTS may emit segments with different sample rates or sample
        # widths. Let FFmpeg normalize those inputs instead of rejecting a
        # valid batch at the final mux step.
        ffmpeg = find_executable("ffmpeg")
        if not ffmpeg:
            raise VideoError("audio.merge_failed", "WAV segments have incompatible formats and ffmpeg is unavailable")
        filter_inputs = "".join(f"[{index}:a]" for index in range(len(inputs)))
        filter_graph = f"{filter_inputs}concat=n={len(inputs)}:v=0:a=1[a]"
        command = [ffmpeg, "-y"]
        for path in inputs:
            command.extend(["-i", str(path)])
        command.extend(
            [
                "-filter_complex",
                filter_graph,
                "-map",
                "[a]",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(output),
            ]
        )
        completed = run_command(command)
        if completed.returncode != 0:
            raise VideoError("audio.merge_failed", completed.stderr[-2000:] or "FFmpeg audio merge failed")


def command_exists(name: str) -> bool:
    return os.path.isfile(name) or find_executable(name) is not None

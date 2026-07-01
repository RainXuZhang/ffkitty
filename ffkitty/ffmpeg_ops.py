"""ffmpeg command building and media probing."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ffkitty.edit_ops import EditSettings, clip_duration, merge_filter_args


PRESETS: dict[str, dict[str, str | list[str] | bool]] = {
    "Convert (copy streams)": {
        "suffix": ".mkv",
        "args": ["-c", "copy"],
    },
    "H.264 MP4": {
        "suffix": ".mp4",
        "args": ["-c:v", "libx264", "-crf", "23", "-preset", "medium", "-c:a", "aac", "-b:a", "192k"],
    },
    "H.265 MP4 (smaller)": {
        "suffix": ".mp4",
        "args": ["-c:v", "libx265", "-crf", "28", "-preset", "medium", "-c:a", "aac", "-b:a", "128k"],
    },
    "WebM VP9": {
        "suffix": ".webm",
        "args": ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0", "-c:a", "libopus", "-b:a", "128k"],
    },
    "Extract audio (MP3)": {
        "suffix": ".mp3",
        "args": ["-vn", "-c:a", "libmp3lame", "-q:a", "2"],
    },
    "Extract audio (FLAC)": {
        "suffix": ".flac",
        "args": ["-vn", "-c:a", "flac"],
    },
    "GIF (palette)": {
        "suffix": ".gif",
        "args": [
            "-vf",
            "fps=15,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
        ],
    },
    "Trim (re-encode H.264)": {
        "suffix": ".mp4",
        "args": ["-c:v", "libx264", "-crf", "23", "-c:a", "aac"],
        "needs_trim": True,
    },
}

PRESET_NAMES = list(PRESETS.keys())

_AUDIO_CODEC_FLAGS = ("-c:a", "-b:a", "-q:a")


def _strip_audio_codec_args(args: list[str]) -> list[str]:
    result: list[str] = []
    skip = False
    for arg in args:
        if skip:
            skip = False
            continue
        if arg in _AUDIO_CODEC_FLAGS:
            skip = True
            continue
        result.append(arg)
    return result


@dataclass
class MediaInfo:
    path: Path
    duration: float = 0.0
    width: int = 0
    height: int = 0
    video_codec: str = ""
    audio_codec: str = ""
    format_name: str = ""
    bitrate: int = 0
    fps: str = ""
    error: str = ""


@dataclass
class FfmpegJob:
    input_path: Path
    output_path: Path
    preset: str
    extra_args: list[str] = field(default_factory=list)
    start: str = ""
    end: str = ""
    overwrite: bool = False
    edits: EditSettings = field(default_factory=EditSettings)

    def output_duration(self, source_duration: float) -> float:
        duration = clip_duration(source_duration, self.start, self.end)
        if self.edits.speed > 0:
            duration /= self.edits.speed
        return duration

    def build_command(self) -> list[str]:
        preset = PRESETS[self.preset]
        cmd = ["ffmpeg", "-hide_banner", "-stats", "-progress", "pipe:2"]

        if self.overwrite:
            cmd.append("-y")
        else:
            cmd.append("-n")

        if self.start:
            cmd.extend(["-ss", self.start])
        cmd.extend(["-i", str(self.input_path)])
        if self.end and self.start:
            cmd.extend(["-to", self.end])
        elif self.end:
            cmd.extend(["-t", self.end])

        info = probe_media(self.input_path)
        clip_len = clip_duration(info.duration, self.start, self.end)
        vf = ",".join(self.edits.build_video_filters(source_duration=clip_len)) or None
        af = None if self.edits.mute else (",".join(self.edits.build_audio_filters()) or None)

        preset_args = list(preset["args"])  # type: ignore[arg-type]
        if self.edits.mute:
            preset_args = _strip_audio_codec_args(preset_args)
            cmd.append("-an")
        if vf or af:
            preset_args = merge_filter_args(preset_args, vf, af)
        elif vf:
            cmd.extend(["-vf", vf])
        elif af:
            cmd.extend(["-af", af])

        cmd.extend(preset_args)
        cmd.extend(self.extra_args)
        cmd.append(str(self.output_path))
        return cmd


@lru_cache(maxsize=16)
def probe_media(path: Path) -> MediaInfo:
    info = MediaInfo(path=path)
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=15)
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        info.error = str(exc)
        return info

    if result.returncode != 0:
        info.error = result.stderr.strip() or "ffprobe failed"
        return info

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        info.error = "Invalid ffprobe output"
        return info

    fmt = data.get("format", {})
    info.duration = float(fmt.get("duration", 0) or 0)
    info.format_name = fmt.get("format_long_name", fmt.get("format_name", ""))
    info.bitrate = int(fmt.get("bit_rate", 0) or 0)

    for stream in data.get("streams", []):
        codec_type = stream.get("codec_type")
        if codec_type == "video" and not info.video_codec:
            info.video_codec = stream.get("codec_name", "")
            info.width = int(stream.get("width", 0) or 0)
            info.height = int(stream.get("height", 0) or 0)
            rate = stream.get("r_frame_rate", "")
            if rate and rate != "0/0":
                info.fps = rate
        elif codec_type == "audio" and not info.audio_codec:
            info.audio_codec = stream.get("codec_name", "")

    return info


def default_output_path(input_path: Path, preset: str) -> Path:
    suffix = PRESETS[preset]["suffix"]
    stem = input_path.stem
    return input_path.with_name(f"{stem}_out{suffix}")


def format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "00:00:00"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def parse_ffmpeg_progress(line: str, duration: float) -> float | None:
    if line.startswith("out_time_ms="):
        try:
            ms = int(line.split("=", 1)[1])
            if duration > 0:
                return min(ms / 1_000_000 / duration, 1.0)
        except ValueError:
            return None
    if line.startswith("out_time="):
        match = re.match(r"out_time=(\d+):(\d+):(\d+\.\d+)", line)
        if match and duration > 0:
            h, m, s = match.groups()
            current = int(h) * 3600 + int(m) * 60 + float(s)
            return min(current / duration, 1.0)
    return None

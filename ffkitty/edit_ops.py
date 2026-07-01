"""Video editing filter building and concat jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


def parse_time(value: str) -> float | None:
    """Parse HH:MM:SS, MM:SS, or seconds into total seconds."""
    value = value.strip()
    if not value:
        return None
    if value.replace(".", "", 1).isdigit():
        return float(value)
    parts = value.split(":")
    try:
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        if len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
    except ValueError:
        return None
    return None


@dataclass
class EditSettings:
    """Transform and audio adjustments applied before/during encode."""

    crop_x: int = 0
    crop_y: int = 0
    crop_w: int = 0
    crop_h: int = 0
    scale_w: int = 0
    scale_h: int = 0
    rotate: int = 0
    hflip: bool = False
    vflip: bool = False
    speed: float = 1.0
    volume: float = 1.0
    mute: bool = False
    fade_in: float = 0.0
    fade_out: float = 0.0
    denoise: bool = False
    sharpen: bool = False
    subtitles: str = ""
    text_overlay: str = ""
    text_x: str = "10"
    text_y: str = "10"
    text_fontsize: int = 24
    text_color: str = "white"
    text_box: bool = False
    text_box_color: str = "black@0.5"

    def has_video_edits(self) -> bool:
        return bool(
            self.crop_w > 0
            or self.scale_w > 0
            or self.rotate
            or self.hflip
            or self.vflip
            or self.speed != 1.0
            or self.fade_in > 0
            or self.fade_out > 0
            or self.denoise
            or self.sharpen
            or self.subtitles.strip()
            or self.text_overlay.strip()
        )

    def has_audio_edits(self) -> bool:
        return self.mute or self.volume != 1.0 or self.speed != 1.0

    def has_any_edits(self) -> bool:
        return self.has_video_edits() or self.has_audio_edits()

    def build_video_filters(self, *, source_duration: float = 0.0) -> list[str]:
        filters: list[str] = []

        if self.crop_w > 0 and self.crop_h > 0:
            filters.append(f"crop={self.crop_w}:{self.crop_h}:{self.crop_x}:{self.crop_y}")

        if self.scale_w > 0:
            h = self.scale_h if self.scale_h > 0 else -1
            filters.append(f"scale={self.scale_w}:{h}:flags=lanczos")

        if self.hflip:
            filters.append("hflip")
        if self.vflip:
            filters.append("vflip")

        if self.rotate == 90:
            filters.append("transpose=1")
        elif self.rotate == 180:
            filters.append("hflip,vflip")
        elif self.rotate == 270:
            filters.append("transpose=2")

        if self.speed != 1.0 and self.speed > 0:
            filters.append(f"setpts=PTS/{self.speed}")

        if self.denoise:
            filters.append("hqdn3d=4:3:6:4.5")
        if self.sharpen:
            filters.append("unsharp=5:5:0.8:5:5:0.0")

        if self.fade_in > 0:
            filters.append(f"fade=t=in:st=0:d={self.fade_in}")

        if self.fade_out > 0 and source_duration > self.fade_out:
            start = max(source_duration - self.fade_out, 0)
            filters.append(f"fade=t=out:st={start}:d={self.fade_out}")

        subs = self.subtitles.strip()
        if subs:
            escaped = subs.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
            filters.append(f"subtitles='{escaped}'")

        overlay = self.text_overlay.strip()
        if overlay:
            escaped = overlay.replace("\\", "\\\\").replace("'", "\\'")
            params = [
                f"text='{escaped}'",
                f"x={self.text_x.strip() or '10'}",
                f"y={self.text_y.strip() or '10'}",
                f"fontsize={max(self.text_fontsize, 1)}",
                f"fontcolor={self.text_color.strip() or 'white'}",
            ]
            if self.text_box:
                params.append(f"box=1:boxcolor={self.text_box_color}:boxborderw=5")
            filters.append("drawtext=" + ":".join(params))

        return filters

    def build_audio_filters(self) -> list[str]:
        filters: list[str] = []
        if self.speed != 1.0 and self.speed > 0:
            filters.extend(_atempo_chain(self.speed))
        if self.volume != 1.0 and self.volume >= 0:
            filters.append(f"volume={self.volume}")
        return filters


def _atempo_chain(speed: float) -> list[str]:
    """Build atempo filter chain (each atempo must be between 0.5 and 2.0)."""
    if speed <= 0:
        return []
    filters: list[str] = []
    remaining = speed
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    if abs(remaining - 1.0) > 0.001:
        filters.append(f"atempo={remaining:.4f}")
    return filters


def merge_filter_args(args: list[str], vf: str | None, af: str | None) -> list[str]:
    """Insert or merge -vf / -af into an ffmpeg argument list."""
    result: list[str] = []
    i = 0
    merged_vf = vf
    merged_af = af
    while i < len(args):
        arg = args[i]
        if arg == "-vf" and i + 1 < len(args):
            preset_vf = args[i + 1]
            merged_vf = f"{merged_vf},{preset_vf}" if merged_vf else preset_vf
            i += 2
            continue
        if arg == "-vn":
            i += 1
            continue
        if arg in ("-c:a", "-b:a", "-q:a") and merged_af is None and af is None:
            i += 2 if i + 1 < len(args) else 1
            continue
        result.append(arg)
        i += 1
    if merged_vf:
        result.extend(["-vf", merged_vf])
    if merged_af:
        result.extend(["-af", merged_af])
    return result


def clip_duration(source_duration: float, start: str, end: str) -> float:
    """Estimate output duration after trim edits."""
    start_s = parse_time(start) or 0.0
    end_s = parse_time(end)
    if end_s is not None and start_s is not None:
        return max(end_s - start_s, 0.0)
    if end_s is not None:
        return end_s
    if start_s and source_duration:
        return max(source_duration - start_s, 0.0)
    return source_duration


def build_timeline_summary(start: str, end: str, preview: str) -> str:
    """Create a compact track-style summary for the current selection."""
    start_s = parse_time(start)
    end_s = parse_time(end)
    preview_s = parse_time(preview)

    start_text = start.strip() or "--:--:--"
    end_text = end.strip() or "--:--:--"
    preview_text = preview.strip() or "--:--:--"

    if start_s is not None and end_s is not None and end_s >= start_s:
        duration = end_s - start_s
        return f"Track: {start_text} → {end_text} ({duration:.1f}s)"
    if start_s is not None and preview_s is not None:
        return f"Track: {start_text} • {preview_text}"
    return f"Track: {start_text} • {preview_text} • {end_text}"


@dataclass
class ConcatJob:
    inputs: list[Path]
    output_path: Path
    overwrite: bool = False
    reencode: bool = False

    def build_command(self) -> list[str]:
        if len(self.inputs) < 2:
            raise ValueError("Concat requires at least two input files")

        cmd = ["ffmpeg", "-hide_banner", "-stats", "-progress", "pipe:2"]
        cmd.append("-y" if self.overwrite else "-n")

        if self.reencode:
            for path in self.inputs:
                cmd.extend(["-i", str(path)])
            n = len(self.inputs)
            v_inputs = "".join(f"[{i}:v:0]" for i in range(n))
            a_inputs = "".join(f"[{i}:a:0]" for i in range(n))
            filter_complex = (
                f"{v_inputs}concat=n={n}:v=1:a=0[vout];"
                f"{a_inputs}concat=n={n}:v=0:a=1[aout]"
            )
            cmd.extend(
                [
                    "-filter_complex",
                    filter_complex,
                    "-map",
                    "[vout]",
                    "-map",
                    "[aout]",
                    "-c:v",
                    "libx264",
                    "-crf",
                    "23",
                    "-preset",
                    "medium",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                ]
            )
        else:
            lines = "\n".join(f"file '{p}'" for p in self.inputs)
            list_path = self.output_path.with_suffix(".concat.txt")
            list_path.write_text(lines, encoding="utf-8")
            cmd.extend(["-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy"])

        cmd.append(str(self.output_path))
        return cmd

"""Kitty terminal graphics protocol helpers."""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import sys
from pathlib import Path


def is_kitty() -> bool:
    return bool(os.environ.get("KITTY_WINDOW_ID")) or os.environ.get("TERM") == "xterm-kitty"


def _kitty_size() -> tuple[int, int]:
    cols, rows = shutil.get_terminal_size(fallback=(80, 24))
    return max(cols * 8, 160), max(rows * 16, 120)


def extract_frame(
    input_path: Path,
    *,
    timestamp: str = "00:00:01",
    width: int | None = None,
    height: int | None = None,
) -> bytes | None:
    if width is None or height is None:
        width, height = _kitty_size()
        width = min(width, 640)
        height = min(height, 360)

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        timestamp,
        "-i",
        str(input_path),
        "-vframes",
        "1",
        "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=decrease",
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "pipe:1",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, check=False, timeout=30)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    return result.stdout


def display_png(png_data: bytes, *, placement_id: int = 1) -> None:
    """Send a PNG to Kitty using the graphics protocol."""
    if not png_data:
        return

    encoded = base64.b64encode(png_data).decode("ascii")
    chunk_size = 4096
    chunks = [encoded[i : i + chunk_size] for i in range(0, len(encoded), chunk_size)]

    for index, chunk in enumerate(chunks):
        more = "m=1" if index < len(chunks) - 1 else "m=0"
        sys.stdout.write(f"\033_Ga=T,f=100,{more},p={placement_id};{chunk}\033\\")
    sys.stdout.flush()


def clear_image(*, placement_id: int = 1) -> None:
    sys.stdout.write(f"\033_Ga=d,d=A,p={placement_id}\033\\")
    sys.stdout.flush()


def show_preview(input_path: Path, *, timestamp: str = "00:00:01") -> bool:
    if not is_kitty():
        return False
    png = extract_frame(input_path, timestamp=timestamp)
    if not png:
        return False
    display_png(png)
    return True

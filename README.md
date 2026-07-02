# ffkitty

Terminal GUI for [ffmpeg](https://ffmpeg.org), built for the [Kitty](https://sw.kovidgoyal.net/kitty/) terminal using Textual. Features inline video frame previews via Kitty's [graphics protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/).

> [!WARNING]
> **Compatibility Disclaimer:** This application requires the **Kitty** terminal environment to render visual video previews. Because the Kitty terminal does not natively support Windows, **ffkitty is not compatible with Windows** and is designed strictly for Linux and macOS environments.

---

## Prerequisites & Installation

Ensure you have **Python 3.11+**, **ffmpeg**, and **Kitty** installed on your system.

### 1. Install Dependencies

* **Arch Linux:**

  ```bash
  sudo pacman -S python python-pip ffmpeg kitty ttf-hack-nerd
  ```

* **Debian/Ubuntu:**

  ```bash
  sudo apt update && sudo apt install python3 python3-pip python3-venv ffmpeg kitty
  ```

* **Fedora:**

  ```bash
  sudo dnf install python3 python3-pip ffmpeg kitty hack-fonts
  ```

* **macOS:**

  ```bash
  brew install ffmpeg kitty font-hack-nerd-font
  ```

### 2. Setup Application

```bash
cd /path/to/ffkitty

# Using the automatic launcher
chmod +x run.sh && ./run.sh

# Or manual virtualenv setup
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## How to Use

Launch the application from within a Kitty terminal window:

```bash
ffkitty
```

### Essential Shortcuts

| Key | Action |
| :--- | :--- |
| `o` | Open file picker to select a video |
| `r` | Refresh preview thumbnail at the current timestamp |
| `[` | Set clip **Start** time |
| `]` | Set clip **End** time |
| `Enter` | Run ffmpeg processing |
| `q` | Quit application |

### Tab Layouts

* **Encode:** Quick container conversion (MP4, WebM, GIF, Audio extraction) and rapid video trimming.
* **Edit:** Fine-grained video adjustments including Crop, Scale, Rotate, Flip, Speed modification, Volume adjustment, Fades, and hardcoded Subtitles.
* **Concat:** Line-separated video merging via stream-copy (no re-encoding) or full H.264 re-encoding.

---

## Troubleshooting

* **Missing Icons (Boxes):** Ensure your terminal is actively using a Nerd Font. For Kitty, add `font_family Hack Nerd Font` (or your preferred Nerd Font) to your `kitty.conf`.
* **No Previews:** Previews strictly require running inside the active **Kitty terminal** environment with `ffmpeg` fully available in your system path.

## Project Structure

```text
ffkitty/
├── ffkitty/
│   ├── app.py          # Textual UI Layout & Logic
│   ├── ffmpeg_ops.py   # Presets, Probing, & Command Generation
│   ├── edit_ops.py     # Filters (Crop, Scale, Concat)
│   └── kitty_image.py  # Kitty Graphics Protocol Handling
└── pyproject.toml
```

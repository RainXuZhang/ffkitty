# ffkitty

Terminal GUI for [ffmpeg](https://ffmpeg.org), built for the [Kitty](https://sw.kovidgoyal.net/kitty/) terminal using Textual. Features inline video frame previews via Kitty's [graphics protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/).

> [!WARNING]
> **Compatibility Disclaimer:** This application requires the **Kitty** terminal environment to render visual video previews. Because the Kitty terminal does not natively support Windows, **ffkitty is not compatible with Windows** and is designed strictly for Linux and macOS environments.

---

## Quick Start (For Beginners)

### 1. Install Requirements

First, install the required software:

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install python3-pip python3-venv ffmpeg kitty

# macOS
brew install ffmpeg kitty
```

### 2. Install ffkitty

```bash
# Download and enter the folder
cd /path/to/ffkitty

# Install the app (one-time setup)
./run.sh
```

### 3. Run ffkitty

Open a Kitty terminal and run:

```bash
ffkitty
```

---

## How to Use (Step by Step)

### Basic Video Trimming

1. **Open a video:** Press `o` and select your video file
2. **Set start time:** Move the preview timestamp, then press `[`
3. **Set end time:** Move to end position, then press `]`
4. **Run:** Press `Enter` to export the trimmed clip

### Quick Actions (Sidebar Buttons)

| Button | What it does |
| :--- | :--- |
| **Open** | Pick a video file to work with |
| **Trim** | Switch to trim/encode mode |
| **Edit** | Add text, crop, rotate, adjust speed |
| **Merge** | Combine multiple videos |
| **Text** | Add captions to your video |
| **Run** | Export your changes |

### Keyboard Shortcuts

| Key | Action |
| :--- | :--- |
| `o` | Open file picker |
| `r` | Refresh preview at current time |
| `[` | Set clip **Start** time |
| `]` | Set clip **End** time |
| `Enter` | Run ffmpeg processing |
| `q` | Quit application |

### Three Main Tabs

* **Encode:** Convert videos to different formats (MP4, WebM, GIF, Audio) and trim clips
* **Edit:** Add text, crop, rotate, flip, change speed, adjust volume, add fades
* **Concat:** Merge multiple videos together

---

## Troubleshooting

* **No video preview:** Make sure you're running inside **Kitty terminal** (not another terminal)
* **ffmpeg not found:** Install ffmpeg: `sudo apt install ffmpeg` (Linux) or `brew install ffmpeg` (macOS)
* **App won't start:** Try running `./run.sh` again to reinstall dependencies

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

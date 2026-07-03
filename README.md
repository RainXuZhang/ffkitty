# ffkitty

Terminal GUI for [ffmpeg](https://ffmpeg.org), built for the [Kitty](https://sw.kovidgoyal.net/kitty/) terminal using Textual. Features inline video frame previews via Kitty's [graphics protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/).

> [!WARNING]
> **Compatibility Disclaimer:** This application requires the **Kitty** terminal environment to render visual video previews. Because the Kitty terminal does not natively support Windows, **ffkitty is not compatible with Windows** and is designed strictly for Linux and macOS environments.

> [!NOTE]
> **Nerd Font Required:** This application uses Nerd Font icons for an intuitive UI. Install from [nerdfix.com](https://www.nerdfix.com) or [github.com/ryanoasis/nerd-fonts](https://github.com/ryanoasis/nerd-fonts).

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

## Kdenlive-style TUI Interface

ffkitty now features a Kdenlive-inspired interface with:

### Main Areas

| Area | Description |
| :--- | :--- |
| **Project Bin** | Import and manage your media clips |
| **Timeline** | Arrange clips on video/audio tracks |
| **Monitor** | Preview your video with inline frame display |
| **Effects** | Add filters and transitions |
| **Properties** | Adjust clip settings (duration, speed, etc.) |

### Quick Actions (Sidebar)

| Button | Action |
| :--- | :--- |
| **Import** | Add media to project bin |
| **Add Clip** | Add current selection to timeline |
| **Cut** | Split clip at playhead position |
| **Copy** | Copy selected clip |
| **Paste** | Paste clip to timeline |
| **Render** | Export your project |

### Keyboard Shortcuts

| Key | Action |
| :--- | :--- |
| `o` | Import media file |
| `i` | Mark In point (clip start) |
| `o` | Mark Out point (clip end) |
| `x` | Cut clip at playhead |
| `c` | Copy selected clip |
| `v` | Paste clip to timeline |
| `r` | Render/export project |
| `q` | Quit application |

### Workflow

1. **Import media:** Press `o` or click "Import" to add files to your project
2. **Set in/out points:** Navigate preview, press `i` for in, `o` for out
3. **Add to timeline:** Click "Add Clip" to place on timeline
4. **Apply effects:** Switch to Effects tab to add filters
5. **Adjust properties:** Use Properties tab for speed, duration, etc.
6. **Render:** Click "Render" or press `r` to export

---

## Troubleshooting

* **No video preview:** Make sure you're running inside **Kitty terminal** (not another terminal)
* **Icons not showing:** Install Nerd Font and configure your terminal to use it
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

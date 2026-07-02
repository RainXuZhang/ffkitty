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

> **Note:** Requires Nerd Font for icons. Install from [nerdfix.com](https://www.nerdfix.com).

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

#### Encode Tab - Convert & Trim Videos

1. **Select a format:** Use the dropdown to select a preset (MP4, WebM, GIF, etc.)
2. **Set input:** Type or paste your input file path in the "Input file" field, or press `o` to browse
3. **Set output:** Type your desired output path in the "Output file" field (e.g., `output.mp4`)
4. **Trim a clip:** 
   - Type a timestamp in "Preview timestamp" (format: `HH:MM:SS` like `00:01:23`)
   - Press `r` to refresh the preview at that time
   - Press `[` to set the start time
   - Change the timestamp and press `]` to set the end time
5. **Add extra args:** Type optional ffmpeg arguments in "Extra ffmpeg args" (e.g., `-map 0 -sn`)
6. **Run:** Press `Enter` to export

#### Edit Tab - Transform & Add Text

1. **Text overlay:**
   - Use the quick buttons to insert common text: "Hello", "Title", "Timestamp", or "Clear"
   - Set position: X=10, Y=10 (top-left corner)
   - Set size: 24 (font size)
   - Set color: "white" or "yellow"
   - Check "Text box" to add a background box behind text
2. **Crop:**
   - Set crop W/H: width and height of the cropped area
   - Set crop X/Y: position of the crop (0,0 = top-left)
3. **Scale:**
   - Set Scale W: new width (0 = keep original)
   - Set Scale H: new height (0 = auto-calculate)
4. **Rotate:** Use the dropdown to select rotation: "No rotation", "Rotate 90° CW", "Rotate 180°", "Rotate 90° CCW"
5. **Flip:** Check "Flip horizontal" or "Flip vertical" to mirror the video
6. **Speed/Volume:**
   - Speed: 1.0 = normal, 2.0 = 2x faster, 0.5 = half speed
   - Volume: 1.0 = normal, 0.5 = half volume, check "Mute audio" to silence
7. **Effects:**
   - Fade in: seconds to fade in (e.g., 1.0)
   - Fade out: seconds to fade out (e.g., 2.0)
   - Check "Denoise" to reduce noise
   - Check "Sharpen" to enhance sharpness
8. **Subtitles:** Type path to .srt or .ass file in "Subtitles file" field

#### Concat Tab - Merge Videos

1. **List files:** Type or paste one video file path per line in the large text area:
   ```
   /path/to/video1.mp4
   /path/to/video2.mp4
   /path/to/video3.mp4
   ```
2. **Set output:** Type the merged output path in "Concat output file" (e.g., `merged.mp4`)
3. **Choose mode:** 
   - Select "Stream copy (fast)" for quick merging (all videos must be same format)
   - Select "Re-encode H.264 (compatible)" for different formats (slower)
4. **Run:** Press `Enter` to merge

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
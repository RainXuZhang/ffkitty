# ffkitty

Terminal GUI for [ffmpeg](https://ffmpeg.org), built for the [Kitty](https://sw.kovidgoyal.net/kitty/) terminal.

Uses Textual for the interface and Kitty's [graphics protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/) for inline video frame previews.

## What is this?

**ffkitty** is a graphical video editor that runs inside your terminal. It lets you trim, convert, and edit videos without leaving the command line. Think of it as a simple video editor with buttons and forms, but designed for the terminal instead of a desktop window.

## What you need to install

Before using ffkitty, you need three things installed on your computer:

1. **Python 3.11 or newer** — the programming language ffkitty is written in
2. **ffmpeg** — the video processing tool that does the actual work
3. **Kitty terminal** (optional) — needed only for video preview thumbnails; encoding works in any terminal

### Installing on Linux (Debian/Ubuntu)

Open a terminal and run these commands:

```bash
# Install Python and pip (Python package manager)
sudo apt update
sudo apt install python3 python3-pip python3-venv

# Install ffmpeg (the video tool)
sudo apt install ffmpeg

# Install Kitty terminal (for previews)
sudo apt install kitty
```

### Installing on Linux (Fedora/RHEL)

```bash
# Install Python and pip
sudo dnf install python3 python3-pip

# Install ffmpeg
sudo dnf install ffmpeg

# Install Kitty terminal
sudo dnf install kitty
```

### Installing on macOS

First, install [Homebrew](https://brew.sh) if you don't have it:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Then install the required tools:

```bash
# Install ffmpeg (the video tool)
brew install ffmpeg

# Install Kitty terminal (for previews)
brew install kitty
```

### Installing on Windows

1. Install [Python from python.org](https://www.python.org/downloads/) (check "Add Python to PATH" during installation)
2. Install [ffmpeg from ffmpeg.org](https://ffmpeg.org/download.html#build-windows) or use `winget install ffmpeg`
3. Install [Kitty terminal](https://sw.kovidgoyal.net/kitty/download/) for previews

## Installing Nerd Font (optional, for icons)

Nerd Fonts add special icons to your terminal. Without them, you'll see empty boxes instead of icons, but ffkitty will still work.

### Linux (Debian/Ubuntu)

```bash
# Download and install a Nerd Font (example: Hack Nerd Font)
mkdir -p ~/.local/share/fonts
cd /tmp
wget https://github.com/ryanoasis/nerd-fonts/releases/download/v3.2.1/Hack.zip
unzip Hack.zip
mv *.ttf ~/.local/share/fonts/
fc-cache -fv
```

### Linux (Fedora/RHEL)

```bash
# Install a Nerd Font
sudo dnf install hack-fonts
# Or download manually from https://www.nerdfonts.com/font-downloads
```

### macOS

```bash
# Install a Nerd Font using Homebrew
brew tap homebrew/cask-fonts
brew install font-hack-nerd-font
```

### Windows

1. Go to [nerdfonts.com/font-downloads](https://www.nerdfonts.com/font-downloads)
2. Download any font (e.g., "Hack")
3. Extract the ZIP file and double-click the `.ttf` file to install
4. In Kitty, add to `kitty.conf`: `font_family Hack Nerd Font`

## Installing ffkitty

After installing the requirements above, install ffkitty:

```bash
# Navigate to the folder where you downloaded ffkitty
cd /path/to/ffkitty

# Create a virtual environment (isolated Python environment)
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Install ffkitty and its dependencies
.venv/bin/pip install -e .
```

**Alternative:** Use the launcher script (creates the virtual environment automatically on first run):

```bash
./run.sh
```

## How to use ffkitty

### Starting the app

Make sure you're inside Kitty terminal (for previews), then run:

```bash
ffkitty
# or
python -m ffkitty
```

### Understanding the interface

The app has three main areas:

- **Left sidebar (Quick actions)** — buttons for common tasks
- **Top panels** — file info, command preview, and video preview
- **Bottom area** — settings organized in tabs

### Keyboard shortcuts

| Key | What it does |
| ----- | -------------- |
| `o` | Open a file picker to select your video |
| `r` | Refresh the preview image at the current timestamp |
| `[` (left bracket) | Mark the current preview time as the **start** of your clip |
| `]` (right bracket) | Mark the current preview time as the **end** of your clip |
| `Enter` | Run ffmpeg to process your video |
| `q` | Quit the app |

### The tabs explained

**Encode tab** — Convert or trim videos:

- **Preset** — Choose output format (MP4, WebM, GIF, etc.)
- **Input file** — Path to your source video
- **Output file** — Where to save the result
- **Start/End time** — Trim the video (set with `[` and `]` keys)
- **Preview timestamp** — Which frame to show in the preview

**Edit tab** — Apply effects to your video:

- **Text overlay** — Add text on screen (like titles)
- **Crop** — Cut away edges of the video (W=width, H=height, X/Y=position)
- **Scale** — Resize the video
- **Rotate** — Turn the video 90°, 180°, or 270°
- **Flip** — Mirror the video horizontally or vertically
- **Speed** — Make video faster (2.0 = 2× speed) or slower (0.5 = half speed)
- **Volume** — Make audio louder (2.0) or quieter (0.5)
- **Fade** — Add fade in/out effects
- **Denoise/Sharpen** — Improve video quality
- **Subtitles** — Burn subtitle files into the video

**Concat tab** — Merge multiple videos together:

- List file paths (one per line) in the order you want them joined
- Choose "Stream copy" for fast merging (no re-encoding)
- Or choose "Re-encode H.264" for better compatibility

### Quick workflow: Trim a video

1. Press `o` to open the file picker
2. Navigate and select your video file
3. Use the **Preview timestamp** field to find where you want to start
4. Press `[` to set the start point
5. Change **Preview timestamp** to find where you want to end
6. Press `]` to set the end point
7. Press `Enter` to export the trimmed clip

### Presets explained

- **Convert (copy streams)** — Changes container format without re-encoding (fastest)
- **H.264 MP4** — Standard video format for most devices
- **H.265 MP4** — Smaller files, newer format (may not play everywhere)
- **WebM VP9** — Web-friendly format for browsers
- **Extract audio (MP3/FLAC)** — Save only the audio track
- **GIF (palette)** — Create an animated GIF

## Troubleshooting

**Icons show as boxes or question marks?**

- Install a Nerd Font and configure your terminal to use it

**Preview doesn't work?**

- Make sure you're running inside Kitty terminal
- Check that ffmpeg is installed: `ffmpeg -version`

**ffmpeg not found?**

- Install ffmpeg (see installation commands above)
- Make sure it's on your PATH: `which ffmpeg`

**Permission denied when running?**

- Make sure the script is executable: `chmod +x run.sh`

## Project layout

```
ffkitty/
  ffkitty/
    app.py          # Textual UI
    ffmpeg_ops.py   # presets, probing, command building
    edit_ops.py     # crop, scale, filters, concat
    kitty_image.py  # Kitty graphics protocol
  pyproject.toml
```

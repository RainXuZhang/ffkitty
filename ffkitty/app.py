"""Textual application for ffkitty."""

from __future__ import annotations

import asyncio
import io
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    ProgressBar,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)
from textual_image.widget import AutoImage

from ffkitty import __version__
from ffkitty.edit_ops import ConcatJob, EditSettings, build_timeline_summary
from ffkitty.ffmpeg_ops import (
    PRESET_NAMES,
    FfmpegJob,
    default_output_path,
    format_duration,
    parse_ffmpeg_progress,
    probe_media,
)
from ffkitty.kitty_image import extract_frame, is_kitty


# Nerd Font icons for intuitive UI
ICON_README = "\U000f02d2"
ICON_OPEN = "\U000f0024"
ICON_TRIM = "\U000f02c8"
ICON_EDIT = "\U000f0300"
ICON_MERGE = "\U000f0211"
ICON_TEXT = "\U000f02a9"
ICON_RUN = "\U000f0409"
ICON_PREVIEW = "\U000f03d5"
ICON_START = "\U000f0307"
ICON_END = "\U000f022e"
ICON_FILE = "\U000f0055"
ICON_OUTPUT = "\U000f0214"
ICON_TIME = "\U000f0133"
ICON_ARGS = "\U000f0292"
ICON_OVERWRITE = "\U000f0218"
ICON_POSITION = "\U000f0215"
ICON_SIZE = "\U000f0216"
ICON_COLOR = "\U000f0217"
ICON_CROP = "\U000f0218"
ICON_SCALE = "\U000f0219"
ICON_ROTATE = "\U000f021a"
ICON_FLIP = "\U000f021b"
ICON_SPEED = "\U000f021c"
ICON_VOLUME = "\U000f021d"
ICON_MUTE = "\U000f021e"
ICON_FADE = "\U000f021f"
ICON_DENOISE = "\U000f0220"
ICON_SHARPEN = "\U000f0221"
ICON_SUBTITLES = "\U000f0222"
ICON_TEXTBOX = "\U000f0223"
ICON_ADD = "\U000f0224"
ICON_QUICK = "\U000f0225"


class ReadmeScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    ReadmeScreen {
        background: $surface;
        padding: 2 4;
    }

    ReadmeScreen #readme-content {
        width: 100%;
        height: 1fr;
        border: solid $primary;
        padding: 2;
        background: $panel;
        color: $text;
        overflow-y: auto;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(id="readme-content")

    def action_dismiss(self) -> None:
        self.dismiss()

    def on_mount(self) -> None:
        readme_path = Path(__file__).parent.parent / "README.md"
        if readme_path.exists():
            content = readme_path.read_text()
            # Remove the first line (title) and format for display
            lines = content.splitlines()
            if lines and lines[0].startswith("# "):
                lines = lines[1:]
            self.query_one("#readme-content", Static).update("\n".join(lines))
        else:
            self.query_one("#readme-content", Static).update("README.md not found")


class FilePicker(ModalScreen[Path | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Open"),
    ]

    def __init__(self, start_path: Path | None = None) -> None:
        super().__init__()
        self.start_path = start_path or Path.home()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield DirectoryTree(str(self.start_path), id="tree")
        yield Footer()

    @on(DirectoryTree.FileSelected)
    def on_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self.dismiss(Path(event.path))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_confirm(self) -> None:
        tree = self.query_one("#tree", DirectoryTree)
        if tree.cursor_node and tree.cursor_node.data:
            path = Path(str(tree.cursor_node.data.path))
            if path.is_file():
                self.dismiss(path)


class PreviewPanel(Vertical):
    DEFAULT_CSS = """
    PreviewPanel {
        height: auto;
        min-height: 22;
        max-height: 42;
        border: none;
        padding: 0;
        background: transparent;
        align: center middle;
    }

    PreviewPanel AutoImage {
        width: 100%;
        height: auto;
        max-height: 34;
        min-height: 20;
        content-align: center middle;
        border: solid $primary;
        padding: 1;
        background: $surface;
    }

    PreviewPanel #preview-status {
        height: auto;
        color: $text;
        padding-top: 1;
        text-align: center;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._input: Path | None = None
        self._timestamp = "00:00:01"

    def compose(self) -> ComposeResult:
        yield AutoImage(id="preview-image")
        yield Static("No preview", id="preview-status")

    def set_source(self, path: Path | None, timestamp: str = "00:00:01") -> None:
        self._input = path
        self._timestamp = timestamp
        status = self.query_one("#preview-status", Static)
        image = self.query_one("#preview-image", AutoImage)

        if not path:
            image.image = None
            status.update("No file selected")
            return

        status.update("[dim]Loading preview…[/dim]")
        self.refresh_preview()

    @work(thread=True)
    def refresh_preview(self) -> None:
        if not self._input:
            return
        png = extract_frame(self._input, timestamp=self._timestamp)
        if not png:
            self.app.call_from_thread(self._show_error, "Could not extract frame")
            return
        self.app.call_from_thread(self._show_frame, png)

    def _show_error(self, message: str) -> None:
        self.query_one("#preview-image", AutoImage).image = None
        self.query_one("#preview-status", Static).update(f"[red]{message}[/red]")

    def _show_frame(self, png: bytes) -> None:
        self.query_one("#preview-image", AutoImage).image = io.BytesIO(png)
        self.query_one("#preview-status", Static).update(
            f"[dim]Frame at {self._timestamp} — [ {ICON_START} sets start, ] {ICON_END} sets end[/dim]"
        )


class InfoPanel(Static):
    DEFAULT_CSS = """
    InfoPanel {
        height: auto;
        border: solid $primary;
        padding: 1 1;
        background: $panel;
        color: $text;
    }
    """

    def show_info(self, path: Path | None) -> None:
        if not path:
            self.update("Select a media file to inspect.")
            return

        info = probe_media(path)
        if info.error:
            self.update(f"[red]{info.error}[/red]")
            return

        lines = [
            f"[bold]{path.name}[/bold]",
            f"Format: {info.format_name or 'unknown'}",
            f"Duration: {format_duration(info.duration)}",
        ]
        if info.width and info.height:
            lines.append(f"Video: {info.video_codec} {info.width}×{info.height} @ {info.fps or '?'} fps")
        if info.audio_codec:
            lines.append(f"Audio: {info.audio_codec}")
        if info.bitrate:
            lines.append(f"Bitrate: {info.bitrate // 1000} kbps")
        self.update("\n".join(lines))


class CommandPreview(Static):
    DEFAULT_CSS = """
    CommandPreview {
        height: auto;
        max-height: 7;
        min-height: 3;
        border: solid $primary;
        padding: 1 1;
        overflow-y: auto;
        background: $panel;
        color: $text;
    }
    """

    def show_command(self, cmd: list[str]) -> None:
        self.update(" ".join(cmd))


class TimelinePanel(Static):
    DEFAULT_CSS = """
    TimelinePanel {
        height: 3;
        border: solid $primary;
        padding: 0 1;
        background: $panel;
        color: $text;
    }
    """

    def update_selection(self, start: str, end: str, preview: str) -> None:
        self.update(build_timeline_summary(start, end, preview))


class ToolPanel(Button):
    DEFAULT_CSS = """
    ToolPanel {
        height: 3;
        padding: 0 1;
        margin-bottom: 1;
        background: $panel;
        color: $text;
        border: solid $primary;
        width: 1fr;
        text-align: left;
    }

    ToolPanel:hover {
        background: $boost;
    }

    ToolPanel:focus {
        background: $secondary;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._action: str | None = None
        self._tab_id = "encode-tab"
        self._input_path: Path | None = None

    def update_context(self, tab_id: str, input_path: Path | None = None, action: str | None = None) -> None:
        self._action = action
        self._tab_id = tab_id
        self._input_path = input_path
        self.label = describe_tool_context(tab_id, input_path, action)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button is not self:
            return
        if self._action == "open":
            self.app.action_open_file()
        elif self._action == "preview":
            self.app.action_refresh_preview()
        elif self._action == "start":
            self.app.action_mark_start()
        elif self._action == "end":
            self.app.action_mark_end()
        elif self._action == "run":
            self.app.action_run_job()
        elif self._action == "encode":
            self.app._activate_tab("encode-tab")
        elif self._action == "edit":
            self.app._activate_tab("edit-tab")
        elif self._action == "concat":
            self.app._activate_tab("concat-tab")
        elif self._action == "readme":
            self.app.action_show_readme()


def describe_tool_context(tab_id: str, input_path: Path | None = None, action: str | None = None) -> str:
    if action == "open":
        return f"{ICON_OPEN} Open • Choose a file to inspect and prepare"
    if action == "preview":
        return f"{ICON_PREVIEW} Preview • Refresh the current frame at the selected timestamp"
    if action == "start":
        return f"{ICON_START} Start • Set the trim start from the preview position"
    if action == "end":
        return f"{ICON_END} End • Set the trim end from the preview position"
    if action == "run":
        return f"{ICON_RUN} Run • Export using the current preset, trim, and edits"
    if action == "trim":
        return f"{ICON_TRIM} Trim • Set a clip range and export it"
    if action == "text":
        return f"{ICON_TEXT} Text • Add captions and titles to your export"
    if action == "readme":
        return f"{ICON_README} Readme • View the application documentation"
    if tab_id == "edit-tab":
        return f"{ICON_EDIT} Edit • Transform • Text overlay"
    if tab_id == "concat-tab":
        return f"{ICON_MERGE} Concat • Merge clips • Set output"
    if input_path:
        return f"{ICON_FILE} Encode • {input_path.name} • preset / trim / output"
    return f"{ICON_FILE} Encode • Open a file to begin"


def get_quick_actions() -> list[tuple[str, str]]:
    return [
        (f"{ICON_README} Readme", "readme"),
        (f"{ICON_OPEN} Open", "open"),
        (f"{ICON_TRIM} Trim", "encode"),
        (f"{ICON_EDIT} Edit", "edit"),
        (f"{ICON_MERGE} Merge", "concat"),
        (f"{ICON_TEXT} Text", "text"),
        (f"{ICON_RUN} Run", "run"),
    ]


class FfkittyApp(App[None]):
    TITLE = "ffkitty"
    SUB_TITLE = f"v{__version__} — ffmpeg editor for Kitty"

    CSS = """
    App {
        background: $surface;
        color: $text;
    }

    Screen {
        layout: vertical;
        background: $surface;
    }

    #main {
        height: 1fr;
        padding: 1 2;
    }

    #workspace {
        height: 1fr;
    }

    #sidebar {
        width: 20;
        padding-right: 1;
    }

    #sidebar-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #sidebar Button {
        width: 1fr;
        min-width: 0;
        height: 3;
        margin-bottom: 1;
        padding: 0 1;
        background: $panel;
        color: $text;
        border: none;
        text-align: left;
    }

    #sidebar Button:hover {
        background: $primary;
    }

    #sidebar Button.-primary {
        background: $boost;
    }

    #sidebar Button.-success {
        background: $success;
    }

    #content {
        width: 1fr;
    }

    #tool-panel {
        margin-bottom: 1;
    }

    #top-bar {
        height: auto;
        margin-bottom: 1;
    }

    #top-info {
        width: 1fr;
        min-width: 30;
        margin-right: 1;
    }

    #preview {
        width: 1fr;
        min-width: 30;
    }

    #top-info, #preview, #timeline, #bottom-panel {
        background: $panel;
        border: solid $primary;
    }

    #timeline {
        height: 3;
        margin-bottom: 1;
    }

    #bottom-panel {
        height: 1fr;
        padding: 1;
    }

    #tabs {
        height: auto;
    }

    #tabs TabPane {
        padding: 1;
        background: $surface;
    }

    #controls {
        margin-top: 1;
    }

    #controls Input, #controls Select {
        margin-bottom: 1;
    }

    #controls Checkbox {
        margin-bottom: 1;
    }

    #preset-select {
        margin-bottom: 1;
    }

    #text-buttons {
        height: auto;
        margin-bottom: 1;
    }

    #text-buttons Button {
        min-width: 0;
        height: 3;
        margin-right: 1;
        padding: 0 1;
    }

    #concat-files {
        height: 8;
        margin-bottom: 1;
    }

    #progress-area {
        height: auto;
        padding: 1;
    }

    #status {
        height: auto;
        padding: 1;
    }

    Input, Select, TextArea {
        background: $surface;
        color: $text;
        border: solid $primary;
        padding: 0 1;
    }

    Button {
        background: $panel;
        color: $text;
        border: none;
        padding: 0 1;
    }

    Button.-primary {
        background: $boost;
    }

    Button.-success {
        background: $success;
    }

    Button:hover {
        background: $primary;
    }

    Button:focus {
        background: $secondary;
    }

    ProgressBar {
        color: $success;
        background: $panel;
    }

    .field-row {
        height: auto;
        margin-bottom: 1;
    }

    .field-row Input {
        width: 1fr;
    }

    .compact-row {
        height: auto;
        margin-bottom: 1;
    }

    .compact-row Label {
        min-width: 8;
        margin-right: 1;
    }

    .compact-row Input {
        width: 1fr;
    }
    """

    BINDINGS = [
        Binding("o", "open_file", "Open"),
        Binding("r", "refresh_preview", "Preview"),
        Binding("[", "mark_start", "Start"),
        Binding("]", "mark_end", "End"),
        Binding("enter", "run_job", "Run"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.theme = "textual-light"
        self.dark = False
        self.input_path: Path | None = None
        self.output_path: Path | None = None
        self.selected_preset = PRESET_NAMES[0]
        self.active_tab = "encode-tab"
        
    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main"):
            with Horizontal(id="workspace"):
                with Vertical(id="sidebar"):
                    yield Static("[bold]Quick actions[/bold]", id="sidebar-title")
                    for label, button_id in get_quick_actions():
                        if button_id == "open":
                            yield Button(label, id="btn-open", variant="primary")
                        elif button_id == "run":
                            yield Button(label, id="btn-run", variant="success")
                        elif button_id == "encode":
                            yield Button(label, id="btn-trim")
                        elif button_id == "concat":
                            yield Button(label, id="btn-concat")
                        elif button_id == "text":
                            yield Button(label, id="btn-text")
                        elif button_id == "edit":
                            yield Button(label, id="btn-edit")
                        else:
                            yield Button(label, id=f"btn-{button_id}")
                with Vertical(id="content"):
                    yield ToolPanel(id="tool-panel")
                    with Horizontal(id="top-bar"):
                        with Vertical(id="top-info"):
                            yield InfoPanel(id="info")
                            yield CommandPreview(id="command")
                        yield PreviewPanel(id="preview")
                    yield TimelinePanel(id="timeline")
                    with VerticalScroll(id="bottom-panel"):
                        with TabbedContent(id="tabs"):
                            with TabPane("Encode", id="encode-tab"):
                                yield Label(f"{ICON_FILE} Output preset")
                                yield Select(
                                    [(name, name) for name in PRESET_NAMES],
                                    value=PRESET_NAMES[0],
                                    id="preset-select",
                                )
                                with Vertical(id="controls"):
                                    yield Label(f"{ICON_FILE} Input file")
                                    yield Input(placeholder="Path to input media", id="input-path")
                                    yield Label(f"{ICON_OUTPUT} Output file")
                                    yield Input(placeholder="Output path", id="output-path")
                                    yield Label(f"{ICON_TIME} Start time (HH:MM:SS)")
                                    yield Input(placeholder="00:00:00", id="start-time")
                                    yield Label(f"{ICON_TIME} End time (HH:MM:SS)")
                                    yield Input(placeholder="00:00:00", id="end-time")
                                    yield Label(f"{ICON_PREVIEW} Preview timestamp")
                                    yield Input(value="00:00:01", id="preview-time")
                                    yield Label(f"{ICON_ARGS} Extra ffmpeg args")
                                    yield Input(placeholder="-map 0 -sn", id="extra-args")
                                    yield Select(
                                        [(f"{ICON_OVERWRITE} Fail if exists", "no"), (f"{ICON_OVERWRITE} Overwrite", "yes")],
                                        value="no",
                                        id="overwrite",
                                    )
                            with TabPane("Edit", id="edit-tab"):
                                yield Static(f"[bold]{ICON_TEXT} Text overlay[/bold]")
                                with Horizontal(classes="compact-row"):
                                    yield Label(f"{ICON_TEXT} Text")
                                    yield Input(placeholder="Hello", id="text-overlay")
                                with Horizontal(id="text-buttons"):
                                    yield Button("Hello", id="btn-text-hello", variant="primary")
                                    yield Button("Title", id="btn-text-title")
                                    yield Button("Timestamp", id="btn-text-timestamp")
                                    yield Button("Clear", id="btn-text-clear")
                                with Horizontal(classes="compact-row"):
                                    yield Label(f"{ICON_POSITION} Pos")
                                    yield Input(placeholder="10", id="text-x")
                                    yield Label("/")
                                    yield Input(placeholder="10", id="text-y")
                                with Horizontal(classes="compact-row"):
                                    yield Label(f"{ICON_SIZE} Size")
                                    yield Input(value="24", id="text-size")
                                    yield Label(f"{ICON_COLOR} Color")
                                    yield Input(value="white", id="text-color")
                                yield Checkbox(f"{ICON_TEXTBOX} Text box", id="text-box")
                                yield Static(f"[bold]{ICON_CROP} Transform[/bold]")
                                with Horizontal(classes="field-row"):
                                    yield Label(f"{ICON_CROP} Crop W")
                                    yield Input(placeholder="0", id="crop-w")
                                    yield Label("H")
                                    yield Input(placeholder="0", id="crop-h")
                                with Horizontal(classes="field-row"):
                                    yield Label(f"{ICON_CROP} Crop X")
                                    yield Input(placeholder="0", id="crop-x")
                                    yield Label("Y")
                                    yield Input(placeholder="0", id="crop-y")
                                with Horizontal(classes="field-row"):
                                    yield Label(f"{ICON_SCALE} Scale W")
                                    yield Input(placeholder="0 = off", id="scale-w")
                                    yield Label("H")
                                    yield Input(placeholder="0 = auto", id="scale-h")
                                yield Select(
                                    [(f"{ICON_ROTATE} No rotation", "0"), (f"{ICON_ROTATE} Rotate 90° CW", "90"), (f"{ICON_ROTATE} Rotate 180°", "180"), (f"{ICON_ROTATE} Rotate 90° CCW", "270")],
                                    value="0",
                                    id="rotate",
                                )
                                yield Checkbox(f"{ICON_FLIP} Flip horizontal", id="hflip")
                                yield Checkbox(f"{ICON_FLIP} Flip vertical", id="vflip")
                                yield Static(f"[bold]{ICON_SPEED} Speed & audio[/bold]")
                                yield Label(f"{ICON_SPEED} Speed (1.0 = normal, 2.0 = 2×)")
                                yield Input(value="1.0", id="speed")
                                yield Label(f"{ICON_VOLUME} Volume (1.0 = normal, 0.5 = half)")
                                yield Input(value="1.0", id="volume")
                                yield Checkbox(f"{ICON_MUTE} Mute audio", id="mute")
                                yield Static(f"[bold]{ICON_FADE} Effects[/bold]")
                                yield Label(f"{ICON_FADE} Fade in (seconds)")
                                yield Input(value="0", id="fade-in")
                                yield Label(f"{ICON_FADE} Fade out (seconds)")
                                yield Input(value="0", id="fade-out")
                                yield Checkbox(f"{ICON_DENOISE} Denoise", id="denoise")
                                yield Checkbox(f"{ICON_SHARPEN} Sharpen", id="sharpen")
                                yield Label(f"{ICON_SUBTITLES} Subtitles file (.srt / .ass)")
                                yield Input(placeholder="/path/to/subs.srt", id="subtitles")
                            with TabPane("Concat", id="concat-tab"):
                                yield Static("One file path per line, in playback order.")
                                yield TextArea(id="concat-files")
                                yield Label(f"{ICON_OUTPUT} Concat output file")
                                yield Input(placeholder="merged_out.mp4", id="concat-output")
                                yield Select(
                                    [(f"{ICON_ADD} Stream copy (fast)", "copy"), (f"{ICON_ADD} Re-encode H.264 (compatible)", "reencode")],
                                    value="copy",
                                    id="concat-mode",
                                )
                                yield Select(
                                    [(f"{ICON_OVERWRITE} Fail if exists", "no"), (f"{ICON_OVERWRITE} Overwrite", "yes")],
                                    value="no",
                                    id="concat-overwrite",
                                )
                    with Vertical(id="progress-area"):
                        yield ProgressBar(total=100, show_eta=False, id="progress")
                    yield Static("Ready.", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._install_theme()
        self._update_command_preview()
        self._update_tool_panel()
        if is_kitty():
            self.query_one("#status", Static).update("Kitty detected — inline preview enabled.")
        else:
            self.query_one("#status", Static).update(
                "Not running in Kitty — previews disabled, encoding still works."
            )

    def _install_theme(self) -> None:
        from textual.theme import Theme

        self._theme = Theme(
            name="ffkitty-light",
            primary="#3b82f6",
            secondary="#6366f1",
            accent="#8b5cf6",
            success="#22c55e",
            warning="#f59e0b",
            error="#ef4444",
            surface="#f8fafc",
            panel="#e2e8f0",
            boost="#dbeafe",
        )
        self.register_theme(self._theme)

    def _parse_int(self, widget_id: str) -> int:
        text = self.query_one(f"#{widget_id}", Input).value.strip()
        return int(text) if text.isdigit() else 0

    def _parse_float(self, widget_id: str, default: float = 0.0) -> float:
        text = self.query_one(f"#{widget_id}", Input).value.strip()
        try:
            return float(text) if text else default
        except ValueError:
            return default

    def _get_edits(self) -> EditSettings:
        rotate_val = self.query_one("#rotate", Select).value
        rotate = int(rotate_val) if rotate_val and str(rotate_val).isdigit() else 0
        return EditSettings(
            crop_x=self._parse_int("crop-x"),
            crop_y=self._parse_int("crop-y"),
            crop_w=self._parse_int("crop-w"),
            crop_h=self._parse_int("crop-h"),
            scale_w=self._parse_int("scale-w"),
            scale_h=self._parse_int("scale-h"),
            rotate=rotate,
            hflip=self.query_one("#hflip", Checkbox).value,
            vflip=self.query_one("#vflip", Checkbox).value,
            speed=max(self._parse_float("speed", 1.0), 0.01),
            volume=max(self._parse_float("volume", 1.0), 0.0),
            mute=self.query_one("#mute", Checkbox).value,
            fade_in=max(self._parse_float("fade-in"), 0.0),
            fade_out=max(self._parse_float("fade-out"), 0.0),
            denoise=self.query_one("#denoise", Checkbox).value,
            sharpen=self.query_one("#sharpen", Checkbox).value,
            subtitles=self.query_one("#subtitles", Input).value.strip(),
            text_overlay=self.query_one("#text-overlay", Input).value.strip(),
            text_x=self.query_one("#text-x", Input).value.strip(),
            text_y=self.query_one("#text-y", Input).value.strip(),
            text_fontsize=max(self._parse_int("text-size"), 1),
            text_color=self.query_one("#text-color", Input).value.strip(),
            text_box=self.query_one("#text-box", Checkbox).value,
        )

    def _get_encode_job(self) -> FfmpegJob | None:
        if not self.input_path or not self.input_path.exists():
            return None

        output_text = self.query_one("#output-path", Input).value.strip()
        output = Path(output_text) if output_text else default_output_path(self.input_path, self.selected_preset)

        extra = self.query_one("#extra-args", Input).value.strip()
        extra_args = extra.split() if extra else []

        return FfmpegJob(
            input_path=self.input_path,
            output_path=output,
            preset=self.selected_preset,
            extra_args=extra_args,
            start=self.query_one("#start-time", Input).value.strip(),
            end=self.query_one("#end-time", Input).value.strip(),
            overwrite=self.query_one("#overwrite", Select).value == "yes",
            edits=self._get_edits(),
        )

    def _get_concat_job(self) -> ConcatJob | None:
        text = self.query_one("#concat-files", TextArea).text.strip()
        if not text:
            return None
        inputs = [Path(line.strip()) for line in text.splitlines() if line.strip()]
        if len(inputs) < 2:
            return None
        for path in inputs:
            if not path.exists():
                return None

        output_text = self.query_one("#concat-output", Input).value.strip()
        if output_text:
            output = Path(output_text)
        else:
            output = inputs[0].with_name(f"{inputs[0].stem}_merged.mp4")

        return ConcatJob(
            inputs=inputs,
            output_path=output,
            overwrite=self.query_one("#concat-overwrite", Select).value == "yes",
            reencode=self.query_one("#concat-mode", Select).value == "reencode",
        )

    def _set_tool_context(self, action: str | None = None) -> None:
        self.query_one("#tool-panel", ToolPanel).update_context(self.active_tab, self.input_path, action)

    def _update_tool_panel(self) -> None:
        self._set_tool_context()

    def _update_timeline(self) -> None:
        self.query_one("#timeline", TimelinePanel).update_selection(
            self.query_one("#start-time", Input).value,
            self.query_one("#end-time", Input).value,
            self.query_one("#preview-time", Input).value,
        )

    def _update_command_preview(self) -> None:
        self._update_timeline()
        self._update_tool_panel()
        if self.active_tab == "concat-tab":
            job = self._get_concat_job()
            if job:
                try:
                    self.query_one("#command", CommandPreview).show_command(job.build_command())
                except ValueError as exc:
                    self.query_one("#command", CommandPreview).update(str(exc))
            else:
                self.query_one("#command", CommandPreview).update("Add two or more file paths to concat.")
            return

        job = self._get_encode_job()
        if job:
            self.query_one("#command", CommandPreview).show_command(job.build_command())
        else:
            self.query_one("#command", CommandPreview).update("Select an input file.")

    def _load_file(self, path: Path) -> None:
        self.input_path = path
        self.output_path = default_output_path(path, self.selected_preset)
        self.query_one("#input-path", Input).value = str(path)
        self.query_one("#output-path", Input).value = str(self.output_path)
        self.query_one("#info", InfoPanel).show_info(path)

        info = probe_media(path)
        if info.width and info.height:
            self.query_one("#crop-w", Input).placeholder = str(info.width)
            self.query_one("#crop-h", Input).placeholder = str(info.height)

        preview_time = self.query_one("#preview-time", Input).value.strip() or "00:00:01"
        self.query_one("#preview", PreviewPanel).set_source(path, preview_time)
        self._update_command_preview()
        self._update_timeline()
        self.query_one("#status", Static).update(f"Loaded {path.name}")

    @on(TabbedContent.TabActivated, "#tabs")
    def on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.pane and event.pane.id:
            self.active_tab = event.pane.id
        self._update_command_preview()

    @on(Select.Changed, "#preset-select")
    def on_preset_selected(self, event: Select.Changed) -> None:
        if event.value:
            self.selected_preset = str(event.value)
        if self.input_path:
            self.output_path = default_output_path(self.input_path, self.selected_preset)
            self.query_one("#output-path", Input).value = str(self.output_path)
        self._update_command_preview()


    @on(Input.Changed)
    def on_any_input_changed(self) -> None:
        text = self.query_one("#input-path", Input).value.strip()
        if text:
            self.input_path = Path(text)
        self._update_command_preview()

    @on(TextArea.Changed, "#concat-files")
    def on_concat_changed(self) -> None:
        self._update_command_preview()

    @on(Select.Changed)
    def on_any_select_changed(self) -> None:
        self._update_command_preview()


    @on(Button.Pressed, "#btn-open")
    def on_open_pressed(self) -> None:
        self._set_tool_context("open")
        self.action_open_file()

    @on(Button.Pressed, "#btn-trim")
    def on_trim_pressed(self) -> None:
        self._activate_tab("encode-tab", action="trim")

    @on(Button.Pressed, "#btn-edit")
    def on_edit_pressed(self) -> None:
        self._activate_tab("edit-tab", action="edit")

    @on(Button.Pressed, "#btn-concat")
    def on_concat_pressed(self) -> None:
        self._activate_tab("concat-tab", action="concat")

    @on(Button.Pressed, "#btn-text")
    def on_text_pressed(self) -> None:
        self._activate_tab("edit-tab", action="text")

    @on(Button.Pressed, "#btn-run")
    def on_run_pressed(self) -> None:
        self._set_tool_context("run")
        self.action_run_job()

    @on(Button.Pressed, "#btn-readme")
    def on_readme_pressed(self) -> None:
        self._set_tool_context("readme")
        self.action_show_readme()

    @on(Button.Pressed, "#btn-text-hello")
    def on_text_hello(self) -> None:
        self.query_one("#text-overlay", Input).value = "Hello"
        self._update_command_preview()

    @on(Button.Pressed, "#btn-text-title")
    def on_text_title(self) -> None:
        self.query_one("#text-overlay", Input).value = "Title"
        self.query_one("#text-size", Input).value = "48"
        self.query_one("#text-x", Input).value = "(w-text_w)/2"
        self.query_one("#text-y", Input).value = "10"
        self._update_command_preview()

    @on(Button.Pressed, "#btn-text-timestamp")
    def on_text_timestamp(self) -> None:
        self.query_one("#text-overlay", Input).value = "timestamp"
        self._update_command_preview()

    @on(Button.Pressed, "#btn-text-clear")
    def on_text_clear(self) -> None:
        self.query_one("#text-overlay", Input).value = ""
        self._update_command_preview()

    def _activate_tab(self, pane_id: str, action: str | None = None) -> None:
        self.active_tab = pane_id
        self.query_one("#tabs", TabbedContent).active = pane_id
        self._set_tool_context(action or pane_id)
        self._update_command_preview()

    def action_open_file(self) -> None:
        start = self.input_path.parent if self.input_path else Path.home()

        def handle_result(path: Path | None) -> None:
            if path:
                self._load_file(path)

        self.push_screen(FilePicker(start), handle_result)

    def action_refresh_preview(self) -> None:
        if not self.input_path:
            self.query_one("#status", Static).update("Select a file first.")
            return
        preview_time = self.query_one("#preview-time", Input).value.strip() or "00:00:01"
        self.query_one("#preview", PreviewPanel).set_source(self.input_path, preview_time)
        self.query_one("#status", Static).update("Refreshing preview…")

    def action_mark_start(self) -> None:
        if not self.input_path:
            return
        ts = self.query_one("#preview-time", Input).value.strip() or "00:00:01"
        self.query_one("#start-time", Input).value = ts
        self._update_command_preview()
        self.query_one("#status", Static).update(f"Start set to {ts}")

    def action_mark_end(self) -> None:
        if not self.input_path:
            return
        ts = self.query_one("#preview-time", Input).value.strip() or "00:00:01"
        self.query_one("#end-time", Input).value = ts
        self._update_command_preview()
        self.query_one("#status", Static).update(f"End set to {ts}")

    def action_run_job(self) -> None:
        if self.active_tab == "concat-tab":
            job = self._get_concat_job()
            if not job:
                self.query_one("#status", Static).update("[red]Need 2+ valid files for concat.[/red]")
                return
            if job.output_path.exists() and not job.overwrite:
                self.query_one("#status", Static).update("[red]Output exists — enable overwrite.[/red]")
                return
            self.run_ffmpeg(job)
            return

        job = self._get_encode_job()
        if not job:
            self.query_one("#status", Static).update("[red]Choose a valid input file.[/red]")
            return
        if job.output_path.exists() and not job.overwrite:
            self.query_one("#status", Static).update(
                "[red]Output exists — enable overwrite or change path.[/red]"
            )
            return
        self.run_ffmpeg(job)

    def action_show_readme(self) -> None:
        self.push_screen(ReadmeScreen())

    @work(exclusive=True)
    async def run_ffmpeg(self, job: FfmpegJob | ConcatJob) -> None:
        progress = self.query_one("#progress", ProgressBar)
        status = self.query_one("#status", Static)
        run_btn = self.query_one("#btn-run", Button)

        progress.update(progress=0)
        run_btn.disabled = True
        status.update(f"Running ffmpeg → {job.output_path.name}")

        if isinstance(job, FfmpegJob):
            info = probe_media(job.input_path)
            duration = job.output_duration(info.duration)
        else:
            duration = sum(probe_media(p).duration for p in job.inputs)

        cmd = job.build_command()

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        assert proc.stderr is not None
        while True:
            line_bytes = await proc.stderr.readline()
            if not line_bytes:
                break
            line = line_bytes.decode(errors="replace").strip()
            pct = parse_ffmpeg_progress(line, duration)
            if pct is not None:
                progress.update(progress=int(pct * 100))

        code = await proc.wait()
        run_btn.disabled = False

        if isinstance(job, ConcatJob) and not job.reencode:
            list_path = job.output_path.with_suffix(".concat.txt")
            if list_path.exists():
                list_path.unlink()

        if code == 0:
            progress.update(progress=100)
            status.update(f"[green]Done:[/green] {job.output_path}")
        else:
            progress.update(progress=0)
            status.update(f"[red]ffmpeg failed (exit {code})[/red]")


def main() -> None:
    FfkittyApp().run()


if __name__ == "__main__":
    main()
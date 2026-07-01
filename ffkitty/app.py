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
        border: round #94a3b8;
        padding: 1;
        background: rgba(255, 255, 255, 0.98);
    }

    PreviewPanel #preview-status {
        height: auto;
        color: #475569;
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
            f"[dim]Frame at {self._timestamp} — [ sets start, ] sets end[/dim]"
        )


class InfoPanel(Static):
    DEFAULT_CSS = """
    InfoPanel {
        height: auto;
        border: round #94a3b8;
        padding: 1 1;
        background: rgba(255, 255, 255, 0.98);
        color: #0f172a;
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
        border: round #94a3b8;
        padding: 1 1;
        overflow-y: auto;
        background: rgba(255, 255, 255, 0.98);
        color: #0f172a;
    }
    """

    def show_command(self, cmd: list[str]) -> None:
        self.update(" ".join(cmd))


class TimelinePanel(Static):
    DEFAULT_CSS = """
    TimelinePanel {
        height: auto;
        min-height: 3;
        border: round #94a3b8;
        padding: 0 1;
        background: transparent;
        color: #0f172a;
    }
    """

    def update_selection(self, start: str, end: str, preview: str) -> None:
        self.update(build_timeline_summary(start, end, preview))


class ToolPanel(Button):
    DEFAULT_CSS = """
    ToolPanel {
        height: auto;
        min-height: 3;
        padding: 0 1;
        margin-bottom: 1;
        background: rgba(255, 255, 255, 0.96);
        color: #374151;
        border: round #d1d5db;
        width: 1fr;
        text-align: left;
    }

    ToolPanel:hover {
        background: #f9fafb;
        border: round #cbd5e1;
    }

    ToolPanel:focus {
        border: heavy #60a5fa;
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


def describe_tool_context(tab_id: str, input_path: Path | None = None, action: str | None = None) -> str:
    if action == "open":
        return "Open • Choose a file to inspect and prepare"
    if action == "preview":
        return "Preview • Refresh the current frame at the selected timestamp"
    if action == "start":
        return "Start • Set the trim start from the preview position"
    if action == "end":
        return "End • Set the trim end from the preview position"
    if action == "run":
        return "Run • Export using the current preset, trim, and edits"
    if action == "trim":
        return "Trim • Set a clip range and export it"
    if action == "text":
        return "Text • Add captions and titles to your export"
    if tab_id == "edit-tab":
        return "Edit • Transform • Text overlay"
    if tab_id == "concat-tab":
        return "Concat • Merge clips • Set output"
    if input_path:
        return f"Encode • {input_path.name} • preset / trim / output"
    return "Encode • Open a file to begin"


def get_quick_actions() -> list[tuple[str, str]]:
    return [
        ("Open", "open"),
        ("Trim", "encode"),
        ("Edit", "edit"),
        ("Merge", "concat"),
        ("Text", "text"),
        ("Run", "run"),
    ]


class FfkittyApp(App[None]):
    TITLE = "ffkitty"
    SUB_TITLE = f"v{__version__} — ffmpeg editor for Kitty"

    CSS = """
    App {
        background: transparent;
        color: #1f2937;
    }

    * {
        transition: none;
    }

    Screen {
        layout: vertical;
        background: transparent;
        color: #1f2937;
    }

    #main {
        height: 1fr;
        padding: 1 2 1 2;
        background: rgba(248, 250, 252, 0.97);
    }

    #workspace {
        height: 1fr;
        min-height: 0;
    }

    #sidebar {
        width: 24;
        min-width: 20;
        padding-right: 1;
    }

    #sidebar-title {
        color: #6366f1;
        text-style: bold;
        margin-bottom: 1;
    }

    #sidebar Button {
        width: 1fr;
        min-width: 0;
        margin-bottom: 1;
        padding: 0 1;
        background: #f9fafb;
        color: #111827;
        border: none;
        text-align: left;
    }

    #sidebar Button:hover {
        background: #e5e7eb;
        color: #0f172a;
    }

    #sidebar Button.-primary {
        background: #eff6ff;
        color: #1d4ed8;
    }

    #sidebar Button.-success {
        background: #f0fdf4;
        color: #166534;
    }

    #content {
        width: 1fr;
        min-width: 0;
    }

    #tool-panel {
        margin-bottom: 1;
    }

    #top-bar {
        height: auto;
        min-height: 24;
        align: center middle;
        margin-bottom: 1;
    }

    #top-info {
        width: 1.1fr;
        min-width: 38;
        margin-right: 1;
    }

    #preview {
        width: 2.2fr;
        min-width: 48;
    }

    #top-info, #preview, #timeline, #bottom-panel {
        background: rgba(255, 255, 255, 0.98);
        border: round #94a3b8;
    }

    #timeline {
        height: auto;
        min-height: 3;
        margin-bottom: 1;
    }

    #bottom-panel {
        height: 1fr;
        min-height: 32;
        padding: 0 1 1 1;
    }

    #tabs {
        height: auto;
        min-height: 24;
    }

    #tabs TabPane {
        padding: 1 1 0 1;
        background: rgba(248, 250, 252, 0.97);
    }

    #controls Input, #controls Select {
        margin-bottom: 1;
    }

    #controls Checkbox {
        margin-bottom: 1;
    }

    #preset-list {
        height: 9;
        border: round #94a3b8;
        margin-bottom: 1;
        background: #f8fafc;
        color: #0f172a;
    }

    #edit-tab, #concat-tab {
        padding: 0 1;
    }

    #concat-files {
        height: 8;
        margin-bottom: 1;
    }

    #actions {
        height: auto;
        align: left middle;
        padding: 0 1;
        margin-top: 1;
    }

    #actions Button {
        margin-right: 1;
    }

    #progress-area {
        height: auto;
        padding: 0 1;
    }

    #status {
        height: auto;
        padding: 0 1;
    }

    Input, Select, TextArea {
        background: #ffffff;
        color: #0f172a;
        border: solid #94a3b8;
        padding: 0 1;
    }

    Button {
        background: #f8fafc;
        color: #0f172a;
        border: none;
        padding: 0 1;
        min-width: 8;
    }

    Button.-primary {
        background: #eff6ff;
        color: #1d4ed8;
    }

    Button.-success {
        background: #f0fdf4;
        color: #166534;
    }

    Button:hover {
        background: #e2e8f0;
        color: #020617;
    }

    Button:focus {
        background: #bfdbfe;
        color: #0f172a;
    }

    ProgressBar {
        color: #2563eb;
        background: #e2e8f0;
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
        min-width: 10;
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
                            yield Button(f" {label}", id="btn-open", variant="primary")
                        elif button_id == "run":
                            yield Button(f" {label}", id="btn-run", variant="success")
                        elif button_id == "encode":
                            yield Button(f" {label}", id="btn-trim")
                        elif button_id == "concat":
                            yield Button(f" {label}", id="btn-concat")
                        elif button_id == "text":
                            yield Button(f" {label}", id="btn-text")
                        elif button_id == "edit":
                            yield Button(f" {label}", id="btn-edit")
                        else:
                            yield Button(f"  {label}", id=f"btn-{button_id}")
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
                                yield Label("Output preset")
                                yield ListView(*[ListItem(Label(name)) for name in PRESET_NAMES], id="preset-list")
                                with Vertical(id="controls"):
                                    yield Label("Input file")
                                    yield Input(placeholder="Path to input media", id="input-path")
                                    yield Label("Output file")
                                    yield Input(placeholder="Output path", id="output-path")
                                    yield Label("Start time (HH:MM:SS)")
                                    yield Input(placeholder="00:00:00", id="start-time")
                                    yield Label("End time (HH:MM:SS)")
                                    yield Input(placeholder="00:00:00", id="end-time")
                                    yield Label("Preview timestamp")
                                    yield Input(value="00:00:01", id="preview-time")
                                    yield Label("Extra ffmpeg args")
                                    yield Input(placeholder="-map 0 -sn", id="extra-args")
                                    yield Select(
                                        [(label, value) for label, value in [("Fail if exists", "no"), ("Overwrite", "yes")]],
                                        value="no",
                                        id="overwrite",
                                    )
                            with TabPane("Edit", id="edit-tab"):
                                yield Static("[bold]Text overlay[/bold]")
                                with Horizontal(classes="compact-row"):
                                    yield Label("Text")
                                    yield Input(placeholder="Hello", id="text-overlay")
                                with Horizontal(classes="compact-row"):
                                    yield Label("Pos")
                                    yield Input(placeholder="10", id="text-x")
                                    yield Label("/")
                                    yield Input(placeholder="10", id="text-y")
                                with Horizontal(classes="compact-row"):
                                    yield Label("Size")
                                    yield Input(value="24", id="text-size")
                                    yield Label("Color")
                                    yield Input(value="white", id="text-color")
                                yield Checkbox("Text box", id="text-box")
                                yield Static("[bold]Transform[/bold]")
                                with Horizontal(classes="field-row"):
                                    yield Label("Crop W")
                                    yield Input(placeholder="0", id="crop-w")
                                    yield Label("H")
                                    yield Input(placeholder="0", id="crop-h")
                                with Horizontal(classes="field-row"):
                                    yield Label("Crop X")
                                    yield Input(placeholder="0", id="crop-x")
                                    yield Label("Y")
                                    yield Input(placeholder="0", id="crop-y")
                                with Horizontal(classes="field-row"):
                                    yield Label("Scale W")
                                    yield Input(placeholder="0 = off", id="scale-w")
                                    yield Label("H")
                                    yield Input(placeholder="0 = auto", id="scale-h")
                                yield Select(
                                    [(label, val) for label, val in [
                                        ("No rotation", "0"),
                                        ("Rotate 90° CW", "90"),
                                        ("Rotate 180°", "180"),
                                        ("Rotate 90° CCW", "270"),
                                    ]],
                                    value="0",
                                    id="rotate",
                                )
                                yield Checkbox("Flip horizontal", id="hflip")
                                yield Checkbox("Flip vertical", id="vflip")
                                yield Static("[bold]Speed & audio[/bold]")
                                yield Label("Speed (1.0 = normal, 2.0 = 2×)")
                                yield Input(value="1.0", id="speed")
                                yield Label("Volume (1.0 = normal, 0.5 = half)")
                                yield Input(value="1.0", id="volume")
                                yield Checkbox("Mute audio", id="mute")
                                yield Static("[bold]Effects[/bold]")
                                yield Label("Fade in (seconds)")
                                yield Input(value="0", id="fade-in")
                                yield Label("Fade out (seconds)")
                                yield Input(value="0", id="fade-out")
                                yield Checkbox("Denoise", id="denoise")
                                yield Checkbox("Sharpen", id="sharpen")
                                yield Label("Subtitles file (.srt / .ass)")
                                yield Input(placeholder="/path/to/subs.srt", id="subtitles")
                            with TabPane("Concat", id="concat-tab"):
                                yield Static("One file path per line, in playback order.")
                                yield TextArea(id="concat-files")
                                yield Label("Concat output file")
                                yield Input(placeholder="merged_out.mp4", id="concat-output")
                                yield Select(
                                    [(label, val) for label, val in [
                                        ("Stream copy (fast)", "copy"),
                                        ("Re-encode H.264 (compatible)", "reencode"),
                                    ]],
                                    value="copy",
                                    id="concat-mode",
                                )
                                yield Select(
                                    [(label, value) for label, value in [("Fail if exists", "no"), ("Overwrite", "yes")]],
                                    value="no",
                                    id="concat-overwrite",
                                )
                    with Vertical(id="progress-area"):
                        yield ProgressBar(total=100, show_eta=False, id="progress")
                    yield Static("Ready.", id="status")
        yield Footer()

    def on_mount(self) -> None:
        preset_list = self.query_one("#preset-list", ListView)
        preset_list.index = 0
        self._update_command_preview()
        self._update_tool_panel()
        if is_kitty():
            self.query_one("#status", Static).update("Kitty detected — inline preview enabled.")
        else:
            self.query_one("#status", Static).update(
                "Not running in Kitty — previews disabled, encoding still works."
            )

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

    @on(ListView.Selected, "#preset-list")
    def on_preset_selected(self, event: ListView.Selected) -> None:
        if event.index is not None:
            self.selected_preset = PRESET_NAMES[event.index]
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

    @on(Checkbox.Changed)
    def on_any_checkbox_changed(self) -> None:
        self._update_command_preview()

    @on(Button.Pressed, "#btn-open")
    def on_open_pressed(self) -> None:
        self._set_tool_context("open")
        self.action_open_file()

    @on(Button.Pressed, "#btn-preview")
    def on_preview_pressed(self) -> None:
        self._set_tool_context("preview")
        self.action_refresh_preview()

    @on(Button.Pressed, "#btn-trim")
    def on_trim_pressed(self) -> None:
        self._activate_tab("encode-tab", action="trim")

    @on(Button.Pressed, "#btn-start")
    def on_start_pressed(self) -> None:
        self._set_tool_context("start")
        self.action_mark_start()

    @on(Button.Pressed, "#btn-end")
    def on_end_pressed(self) -> None:
        self._set_tool_context("end")
        self.action_mark_end()

    @on(Button.Pressed, "#btn-encode")
    def on_encode_pressed(self) -> None:
        self._activate_tab("encode-tab", action="encode")

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

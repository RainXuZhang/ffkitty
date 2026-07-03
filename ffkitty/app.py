"""Textual application for ffkitty - Kdenlive-style TUI video editor."""

from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass, field
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
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
ICON_PROJECT = "\U000f0055"
ICON_CLIP = "\U000f0214"
ICON_EFFECTS = "\U000f0215"
ICON_PROPERTIES = "\U000f0216"
ICON_MONITOR = "\U000f0217"
ICON_RENDER = "\U000f0218"
ICON_PLAY = "\U000f0219"
ICON_STOP = "\U000f021a"
ICON_ADD = "\U000f021b"
ICON_REMOVE = "\U000f021c"
ICON_CUT = "\U000f021d"
ICON_COPY = "\U000f021e"
ICON_PASTE = "\U000f021f"
ICON_UNDO = "\U000f0220"
ICON_REDO = "\U000f0221"
ICON_ZOOM = "\U000f0222"
ICON_AUDIO = "\U000f0223"
ICON_VIDEO = "\U000f0224"
ICON_TEXT = "\U000f0225"
ICON_TRANSITION = "\U000f0226"
ICON_KEYFRAME = "\U000f0227"
ICON_LOCK = "\U000f0228"
ICON_MUTE = "\U000f0229"
ICON_SNAP = "\U000f022a"
ICON_MARKER = "\U000f022b"
ICON_TIMELINE = "\U000f022c"
ICON_TRACK = "\U000f022d"
ICON_SPACING = "\U000f022e"
ICON_ROLL = "\U000f022f"
ICON_CROP = "\U000f0230"
ICON_SCALE = "\U000f0231"
ICON_ROTATE = "\U000f0232"
ICON_FLIP = "\U000f0233"
ICON_SPEED = "\U000f0234"
ICON_VOLUME = "\U000f0235"
ICON_FADE = "\U000f0236"
ICON_DENOISE = "\U000f0237"
ICON_SHARPEN = "\U000f0238"
ICON_SUBTITLES = "\U000f0239"
ICON_OVERWRITE = "\U000f023a"
ICON_TIME = "\U000f023b"
ICON_PRESET = "\U000f023c"
ICON_EXPORT = "\U000f023d"
ICON_IMPORT = "\U000f023e"
ICON_SAVE = "\U000f023f"
ICON_OPEN = "\U000f0240"


@dataclass
class Clip:
    """Represents a media clip in the project bin."""
    path: Path
    duration: float = 0.0
    in_point: str = "00:00:00"
    out_point: str = ""
    track: int = 0
    start_time: str = "00:00:00"
    name: str = ""
    
    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.path.name


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
            f"[dim]Frame at {self._timestamp} — [ {ICON_ADD} sets in, ] {ICON_CUT} sets out[/dim]"
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
            lines.append(f"Video: {info.video_codec} {info.width}x{info.height} @ {info.fps or '?'} fps")
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
    """Timeline panel showing clip positions and selection."""
    DEFAULT_CSS = """
    TimelinePanel {
        height: 3;
        border: solid $primary;
        padding: 0 1;
        background: $panel;
        color: $text;
    }
    """

    def update_selection(self, start: str, end: str, preview_time: str) -> None:
        """Update the timeline display with current selection."""
        # Simple placeholder implementation
        self.update(f"{ICON_TIMELINE} Timeline: {start or '—'} → {end or '—'} | Preview: {preview_time or '00:00:01'}")


class TimelineTrack(Static):
    """A single track in the timeline."""
    DEFAULT_CSS = """
    TimelineTrack {
        height: 3;
        border: solid $primary;
        padding: 0 1;
        background: $panel;
        color: $text;
    }
    """


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
        self._tab_id = "project-tab"
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
            self.app.action_mark_in()
        elif self._action == "end":
            self.app.action_mark_out()
        elif self._action == "run":
            self.app.action_render()
        elif self._action == "add_clip":
            self.app.action_add_clip()
        elif self._action == "cut":
            self.app.action_cut()
        elif self._action == "copy":
            self.app.action_copy()
        elif self._action == "paste":
            self.app.action_paste()


def describe_tool_context(tab_id: str, input_path: Path | None = None, action: str | None = None) -> str:
    if action == "open":
        return f"{ICON_IMPORT} Import • Add media to project bin"
    if action == "preview":
        return f"{ICON_MONITOR} Monitor • Preview current frame"
    if action == "start":
        return f"{ICON_ADD} Mark In • Set clip start point"
    if action == "end":
        return f"{ICON_CUT} Mark Out • Set clip end point"
    if action == "run":
        return f"{ICON_RENDER} Render • Export your project"
    if action == "add_clip":
        return f"{ICON_ADD} Add Clip • Add to timeline"
    if action == "cut":
        return f"{ICON_CUT} Cut • Split clip at playhead"
    if action == "copy":
        return f"{ICON_COPY} Copy • Copy selected clip"
    if action == "paste":
        return f"{ICON_PASTE} Paste • Paste clip to timeline"
    if tab_id == "project-tab":
        return f"{ICON_PROJECT} Project • Manage clips and assets"
    if tab_id == "timeline-tab":
        return f"{ICON_TIMELINE} Timeline • Arrange and edit clips"
    if tab_id == "effects-tab":
        return f"{ICON_EFFECTS} Effects • Add filters and transitions"
    if tab_id == "properties-tab":
        return f"{ICON_PROPERTIES} Properties • Adjust clip settings"
    return f"{ICON_PROJECT} ffkitty • Kdenlive-style TUI editor"


def get_quick_actions() -> list[tuple[str, str]]:
    return [
        (f"{ICON_IMPORT} Import", "open"),
        (f"{ICON_ADD} Add Clip", "add_clip"),
        (f"{ICON_CUT} Cut", "cut"),
        (f"{ICON_COPY} Copy", "copy"),
        (f"{ICON_PASTE} Paste", "paste"),
        (f"{ICON_RENDER} Render", "run"),
    ]


class FfkittyApp(App[None]):
    TITLE = "ffkitty"
    SUB_TITLE = f"v{__version__} — Kdenlive-style TUI video editor"

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
        Binding("o", "open_file", "Import"),
        Binding("i", "mark_in", "Mark In"),
        Binding("o", "mark_out", "Mark Out"),
        Binding("x", "cut", "Cut"),
        Binding("c", "copy", "Copy"),
        Binding("v", "paste", "Paste"),
        Binding("r", "render", "Render"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.theme = "textual-light"
        self.dark = False
        self.input_path: Path | None = None
        self.output_path: Path | None = None
        self.selected_preset = PRESET_NAMES[0]
        self.active_tab = "project-tab"
        self.clips: list[Clip] = []
        self.current_time: str = "00:00:01"

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
                        elif button_id == "add_clip":
                            yield Button(label, id="btn-add-clip")
                        elif button_id == "cut":
                            yield Button(label, id="btn-cut")
                        elif button_id == "copy":
                            yield Button(label, id="btn-copy")
                        elif button_id == "paste":
                            yield Button(label, id="btn-paste")
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
                            with TabPane("Project", id="project-tab"):
                                yield Static(f"[bold]{ICON_CLIP} Project Bin[/bold]")
                                yield ListView(id="clip-list")
                                with Horizontal(classes="compact-row"):
                                    yield Button(f"{ICON_IMPORT} Import", id="btn-import", variant="primary")
                                    yield Button(f"{ICON_ADD} Add", id="btn-add-to-timeline")
                            with TabPane("Timeline", id="timeline-tab"):
                                yield Static(f"[bold]{ICON_TIMELINE} Timeline[/bold]")
                                yield Label(f"{ICON_TRACK} Video Track 1")
                                yield ListView(id="timeline-track-1")
                                yield Label(f"{ICON_AUDIO} Audio Track 1")
                                yield ListView(id="timeline-track-2")
                            with TabPane("Effects", id="effects-tab"):
                                yield Static(f"[bold]{ICON_EFFECTS} Effects & Filters[/bold]")
                                yield Select(
                                    [(f"{ICON_CROP} Crop", "crop"), (f"{ICON_SCALE} Scale", "scale"),
                                     (f"{ICON_ROTATE} Rotate", "rotate"), (f"{ICON_FLIP} Flip", "flip")],
                                    value="crop",
                                    id="effect-type",
                                )
                            with TabPane("Properties", id="properties-tab"):
                                yield Static(f"[bold]{ICON_PROPERTIES} Clip Properties[/bold]")
                                yield Label(f"{ICON_TIME} Duration")
                                yield Input(placeholder="00:00:00", id="prop-duration")
                                yield Label(f"{ICON_SPEED} Speed")
                                yield Input(value="1.0", id="prop-speed")
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
        try:
            text = self.query_one(f"#{widget_id}", Input).value.strip()
            return int(text) if text.isdigit() else 0
        except NoMatches:
            return 0

    def _parse_float(self, widget_id: str, default: float = 0.0) -> float:
        try:
            text = self.query_one(f"#{widget_id}", Input).value.strip()
            return float(text) if text else default
        except NoMatches:
            return default

    def _get_edits(self) -> EditSettings:
        try:
            rotate_val = self.query_one("#rotate", Select).value
            rotate = int(rotate_val) if rotate_val and str(rotate_val).isdigit() else 0
        except NoMatches:
            rotate = 0
        return EditSettings(
            crop_x=self._parse_int("crop-x"),
            crop_y=self._parse_int("crop-y"),
            crop_w=self._parse_int("crop-w"),
            crop_h=self._parse_int("crop-h"),
            scale_w=self._parse_int("scale-w"),
            scale_h=self._parse_int("scale-h"),
            rotate=rotate,
            hflip=self._get_checkbox("hflip"),
            vflip=self._get_checkbox("vflip"),
            speed=max(self._parse_float("speed", 1.0), 0.01),
            volume=max(self._parse_float("volume", 1.0), 0.0),
            mute=self._get_checkbox("mute"),
            fade_in=max(self._parse_float("fade-in"), 0.0),
            fade_out=max(self._parse_float("fade-out"), 0.0),
            denoise=self._get_checkbox("denoise"),
            sharpen=self._get_checkbox("sharpen"),
            subtitles=self._get_input("subtitles"),
            text_overlay=self._get_input("text-overlay"),
            text_x=self._get_input("text-x"),
            text_y=self._get_input("text-y"),
            text_fontsize=max(self._parse_int("text-size"), 1),
            text_color=self._get_input("text-color"),
            text_box=self._get_checkbox("text-box"),
        )

    def _get_checkbox(self, widget_id: str) -> bool:
        try:
            return self.query_one(f"#{widget_id}", Checkbox).value
        except NoMatches:
            return False

    def _get_input(self, widget_id: str, default: str = "") -> str:
        try:
            return self.query_one(f"#{widget_id}", Input).value.strip()
        except NoMatches:
            return default

    def _get_select(self, widget_id: str) -> str | None:
        try:
            return str(self.query_one(f"#{widget_id}", Select).value)
        except NoMatches:
            return None

    def _get_encode_job(self) -> FfmpegJob | None:
        if not self.input_path or not self.input_path.exists():
            return None

        output_text = self._get_input("output-path")
        output = Path(output_text) if output_text else default_output_path(self.input_path, self.selected_preset)

        extra = self._get_input("extra-args")
        extra_args = extra.split() if extra else []

        return FfmpegJob(
            input_path=self.input_path,
            output_path=output,
            preset=self.selected_preset,
            extra_args=extra_args,
            start=self._get_input("start-time"),
            end=self._get_input("end-time"),
            overwrite=self._get_select("overwrite") == "yes",
            edits=self._get_edits(),
        )

    def _get_concat_job(self) -> ConcatJob | None:
        text = self.query_one("#concat-files", TextArea).text.strip() if self.query_one("#concat-files", TextArea) else ""
        if not text:
            return None
        inputs = [Path(line.strip()) for line in text.splitlines() if line.strip()]
        if len(inputs) < 2:
            return None
        for path in inputs:
            if not path.exists():
                return None

        output_text = self.query_one("#concat-output", Input).value.strip() if self.query_one("#concat-output", Input) else ""
        if output_text:
            output = Path(output_text)
        else:
            output = inputs[0].with_name(f"{inputs[0].stem}_merged.mp4")

        return ConcatJob(
            inputs=inputs,
            output_path=output,
            overwrite=self.query_one("#concat-overwrite", Select).value == "yes" if self.query_one("#concat-overwrite", Select) else False,
            reencode=self.query_one("#concat-mode", Select).value == "reencode" if self.query_one("#concat-mode", Select) else False,
        )

    def _set_tool_context(self, action: str | None = None) -> None:
        self.query_one("#tool-panel", ToolPanel).update_context(self.active_tab, self.input_path, action)

    def _update_tool_panel(self) -> None:
        self._set_tool_context()

    def _update_timeline(self) -> None:
        # These input widgets may not exist in the current UI, so handle gracefully
        start = ""
        end = ""
        preview_time = ""
        try:
            start = self.query_one("#start-time", Input).value
        except NoMatches:
            pass
        try:
            end = self.query_one("#end-time", Input).value
        except NoMatches:
            pass
        try:
            preview_time = self.query_one("#preview-time", Input).value
        except NoMatches:
            pass
        self.query_one("#timeline", TimelinePanel).update_selection(start, end, preview_time)

    def _update_command_preview(self) -> None:
        self._update_timeline()
        self._update_tool_panel()
        job = self._get_encode_job()
        if job:
            self.query_one("#command", CommandPreview).show_command(job.build_command())
        else:
            self.query_one("#command", CommandPreview).update("Select a file to begin editing.")

    def _load_file(self, path: Path) -> None:
        self.input_path = path
        self.output_path = default_output_path(path, self.selected_preset)
        try:
            self.query_one("#input-path", Input).value = str(path)
        except NoMatches:
            pass
        try:
            self.query_one("#output-path", Input).value = str(self.output_path)
        except NoMatches:
            pass
        self.query_one("#info", InfoPanel).show_info(path)

        info = probe_media(path)
        if info.width and info.height:
            try:
                self.query_one("#crop-w", Input).placeholder = str(info.width)
            except NoMatches:
                pass
            try:
                self.query_one("#crop-h", Input).placeholder = str(info.height)
            except NoMatches:
                pass

        preview_time = self._get_input("preview-time", "00:00:01")
        self.query_one("#preview", PreviewPanel).set_source(path, preview_time or "00:00:01")
        self._update_command_preview()
        self._update_timeline()
        self.query_one("#status", Static).update(f"Loaded {path.name}")

    @on(TabbedContent.TabActivated, "#tabs")
    def on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.pane and event.pane.id:
            self.active_tab = event.pane.id
        self._update_command_preview()

    @on(Input.Changed)
    def on_any_input_changed(self) -> None:
        text = self._get_input("input-path")
        if text:
            self.input_path = Path(text)
        self._update_command_preview()

    @on(Button.Pressed, "#btn-open")
    def on_open_pressed(self) -> None:
        self._set_tool_context("open")
        self.action_open_file()

    @on(Button.Pressed, "#btn-run")
    def on_run_pressed(self) -> None:
        self._set_tool_context("run")
        self.action_run_job()

    @on(Button.Pressed, "#btn-import")
    def on_import_pressed(self) -> None:
        self._set_tool_context("open")
        self.action_open_file()

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
        preview_time = self._get_input("preview-time", "00:00:01")
        self.query_one("#preview", PreviewPanel).set_source(self.input_path, preview_time or "00:00:01")
        self.query_one("#status", Static).update("Refreshing preview…")

    def action_mark_in(self) -> None:
        if not self.input_path:
            return
        ts = self._get_input("preview-time", "00:00:01")
        try:
            self.query_one("#start-time", Input).value = ts or "00:00:01"
        except NoMatches:
            pass
        self._update_command_preview()
        self.query_one("#status", Static).update(f"{ICON_ADD} In point: {ts}")

    def action_mark_out(self) -> None:
        if not self.input_path:
            return
        ts = self._get_input("preview-time", "00:00:01")
        try:
            self.query_one("#end-time", Input).value = ts or "00:00:01"
        except NoMatches:
            pass
        self._update_command_preview()
        self.query_one("#status", Static).update(f"{ICON_CUT} Out point: {ts}")

    def action_add_clip(self) -> None:
        if not self.input_path:
            return
        info = probe_media(self.input_path)
        clip = Clip(
            path=self.input_path,
            duration=info.duration,
            in_point=self._get_input("start-time", "00:00:00"),
            out_point=self._get_input("end-time", ""),
        )
        self.clips.append(clip)
        self.query_one("#status", Static).update(f"{ICON_ADD} Added {clip.name} to project")

    def action_cut(self) -> None:
        self.query_one("#status", Static).update(f"{ICON_CUT} Cut at current position")

    def action_copy(self) -> None:
        self.query_one("#status", Static).update(f"{ICON_COPY} Copied clip")

    def action_paste(self) -> None:
        self.query_one("#status", Static).update(f"{ICON_PASTE} Pasted clip to timeline")

    def action_render(self) -> None:
        self._set_tool_context("run")
        self.action_run_job()

    def action_run_job(self) -> None:
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
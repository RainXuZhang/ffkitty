"""Textual application for ffkitty - Kdenlive-style TUI video editor."""

from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Checkbox, DirectoryTree, Footer, Header,
    Input, Label, ListView, ProgressBar, Select,
    Static, TabbedContent, TabPane, TextArea,
)
from textual_image.widget import AutoImage

from ffkitty import __version__
from ffkitty.edit_ops import ConcatJob, EditSettings
from ffkitty.ffmpeg_ops import (
    PRESET_NAMES, FfmpegJob, default_output_path,
    format_duration, parse_ffmpeg_progress, probe_media,
)
from ffkitty.kitty_image import extract_frame, is_kitty

NF = {
    "PROJECT": "\U000f0055", "CLIP": "\U000f0214",
    "EFFECTS": "\U000f0215", "PROPERTIES": "\U000f0216",
    "MONITOR": "\U000f0217", "RENDER": "\U000f0218",
    "PLAY": "\U000f0219", "STOP": "\U000f021a",
    "ADD": "\U000f021b", "CUT": "\U000f021d",
    "COPY": "\U000f021e", "PASTE": "\U000f021f",
    "UNDO": "\U000f0220", "REDO": "\U000f0221",
    "ZOOM": "\U000f0222", "AUDIO": "\U000f0223",
    "VIDEO": "\U000f0224", "TIMELINE": "\U000f022c",
    "TRACK": "\U000f022d", "SAVE": "\U000f023f",
    "OPEN": "\U000f0240", "FOLDER": "\U000f0241",
    "FILE": "\U000f0242", "MENU": "\U000f0243",
    "SETTINGS": "\U000f0244", "HELP": "\U000f0245",
    "EXPORT": "\U000f023d", "IMPORT": "\U000f023e",
    "TRASH": "\U000f02b8", "HISTORY": "\U000f02b6",
    "SEARCH": "\U000f024b", "NEW": "\U000f024d",
    "EXIT": "\U000f024f", "DISC": "\U000f02bd",
    "CLOCK": "\U000f0269", "CHECK": "\U000f0249",
    "CLOSE": "\U000f024a", "WARNING": "\U000f0608",
    "ERROR": "\U000f0609", "INFO": "\U000f060a",
    "PLUS": "\U000f060f", "MINUS": "\U000f0610",
    "MUSIC": "\U000f029b", "RECORD": "\U000f0347",
    "REFRESH": "\U000f0276", "SYNC": "\U000f0277",
    "SPEED": "\U000f0234", "VOLUME": "\U000f0235",
    "FADE": "\U000f0236", "TIME": "\U000f023b",
    "CROP": "\U000f0230", "SCALE": "\U000f0231",
    "ROTATE": "\U000f0232", "FLIP": "\U000f0233",
    "LOCK": "\U000f0228", "MUTE": "\U000f0229",
    "SNAP": "\U000f022a", "MARKER": "\U000f022b",
    "TRANSITION": "\U000f0226", "KEYFRAME": "\U000f0227",
    "TEXT": "\U000f0225", "FILM": "\U000f032b",
    "MOVIE": "\U000f032a", "LIGHT": "\U000f0282",
    "DARK": "\U000f0283", "HOME": "\U000f024c",
}


@dataclass
class Clip:
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
    BINDINGS = [Binding("escape", "dismiss", "Close")]
    DEFAULT_CSS = """
    ReadmeScreen { background: $surface; padding: 2 4; }
    ReadmeScreen #readme-content {
        width: 100%; height: 1fr; border: solid $primary;
        padding: 2; background: $panel; color: $text; overflow-y: auto;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(id="readme-content")

    def on_mount(self) -> None:
        p = Path(__file__).parent.parent / "README.md"
        if p.exists():
            c = p.read_text()
            lines = c.splitlines()
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
            p = Path(str(tree.cursor_node.data.path))
            if p.is_file():
                self.dismiss(p)


class PreviewPanel(Vertical):
    DEFAULT_CSS = """
    PreviewPanel { height: auto; min-height: 22; max-height: 42;
        border: none; padding: 0; background: transparent; align: center middle; }
    PreviewPanel AutoImage { width: 100%; height: auto; max-height: 34;
        min-height: 20; content-align: center middle; border: solid $primary;
        padding: 1; background: $surface; }
    PreviewPanel #preview-status { height: auto; color: $text;
        padding-top: 1; text-align: center; }
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
        st = self.query_one("#preview-status", Static)
        img = self.query_one("#preview-image", AutoImage)
        if not path:
            img.image = None
            st.update("No file selected")
            return
        st.update("[dim]Loading preview...[/dim]")
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

    def _show_error(self, msg: str) -> None:
        self.query_one("#preview-image", AutoImage).image = None
        self.query_one("#preview-status", Static).update(f"[red]{msg}[/red]")

    def _show_frame(self, png: bytes) -> None:
        self.query_one("#preview-image", AutoImage).image = io.BytesIO(png)
        self.query_one("#preview-status", Static).update(
            f"[dim]Frame at {self._timestamp}[/dim]"
        )


class InfoPanel(Static):
    DEFAULT_CSS = """
    InfoPanel { height: auto; border: solid $primary;
        padding: 1; background: $panel; color: $text; }
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
            lines.append(
                f"Video: {info.video_codec} {info.width}x{info.height} @ "
                f"{info.fps or '?'} fps"
            )
        if info.audio_codec:
            lines.append(f"Audio: {info.audio_codec}")
        if info.bitrate:
            lines.append(f"Bitrate: {info.bitrate // 1000} kbps")
        self.update("\n".join(lines))


class CommandPreview(Static):
    DEFAULT_CSS = """
    CommandPreview { height: auto; max-height: 7; min-height: 3;
        border: solid $primary; padding: 1; overflow-y: auto;
        background: $panel; color: $text; }
    """

    def show_command(self, cmd: list[str]) -> None:
        self.update(" ".join(cmd))


class TimelinePanel(Static):
    DEFAULT_CSS = """
    TimelinePanel { height: 3; border: solid $primary;
        padding: 0 1; background: $panel; color: $text; }
    """

    def update_selection(self, start: str, end: str, preview_time: str) -> None:
        self.update(
            f"{NF['TIMELINE']} Timeline: {start or '---'} -> "
            f"{end or '---'} | Preview: {preview_time or '00:00:01'}"
        )


class FfkittyApp(App[None]):
    TITLE = "ffkitty"
    SUB_TITLE = f"v{__version__}"

    CSS = """
    App { background: $surface; color: $text; }
    Screen { layout: vertical; background: $surface; }
    #menu { height: 3; }
    #menu Button { height: 3; min-width: 10; background: transparent;
        border: none; padding: 0 2; text-align: center; }
    #menu Button:hover { background: $boost; }
    #menu Button:focus { background: $secondary; }
    #main { height: 1fr; padding: 0 1 1 1; }
    #sidebar { width: 22; padding-right: 1; }
    #sidebar-title { text-style: bold; margin-bottom: 1; padding: 0 1; }
    #sidebar Button { width: 1fr; min-width: 0; height: 3;
        margin-bottom: 1; padding: 0 1; background: $panel;
        color: $text; border: none; text-align: left; }
    #sidebar Button:hover { background: $primary; }
    #sidebar Button.-primary { background: $boost; }
    #sidebar Button.-success { background: $success; }
    #content { width: 1fr; }
    #top-bar { height: auto; margin-bottom: 1; }
    #top-info { width: 1fr; min-width: 30; margin-right: 1; }
    #top-info, #preview, #timeline, #bottom-panel {
        background: $panel; border: solid $primary; }
    #timeline { height: 3; margin-bottom: 1; }
    #bottom-panel { height: 1fr; padding: 1; }
    #tabs TabPane { padding: 1; background: $surface; }
    #progress-area { height: auto; padding: 1; }
    #status { height: auto; padding: 1; }
    Input, Select, TextArea { background: $surface; color: $text;
        border: solid $primary; padding: 0 1; }
    Button { background: $panel; color: $text; border: none; padding: 0 1; }
    Button.-primary { background: $boost; }
    Button.-success { background: $success; }
    Button:hover { background: $primary; }
    Button:focus { background: $secondary; }
    ProgressBar { color: $success; background: $panel; }
    .compact-row { height: auto; margin-bottom: 1; }
    .compact-row Label { min-width: 8; margin-right: 1; }
    .compact-row Input { width: 1fr; }
    """

    BINDINGS = [
        Binding("o", "open_file", "Browse Files"),
        Binding("i", "mark_in", "Mark In"),
        Binding("u", "mark_out", "Mark Out"),
        Binding("x", "cut", "Cut"),
        Binding("c", "copy", "Copy"),
        Binding("v", "paste", "Paste"),
        Binding("r", "render", "Render"),
        Binding("escape", "show_readme", "README"),
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
        yield Header(show_clock=True)
        with Horizontal(id="menu"):
            yield Button(f"{NF['FOLDER']} Browse Files", id="mnu-browse", variant="primary")
            yield Button(f"{NF['ADD']} Add Clip", id="mnu-add")
            yield Button(f"{NF['CUT']} Cut", id="mnu-cut")
            yield Button(f"{NF['COPY']} Copy", id="mnu-copy")
            yield Button(f"{NF['PASTE']} Paste", id="mnu-paste")
            yield Button(f"{NF['RENDER']} Render", id="mnu-render", variant="success")
            yield Button(f"{NF['HELP']} README", id="mnu-readme")
        with Vertical(id="main"):
            with Horizontal(id="workspace"):
                with Vertical(id="sidebar"):
                    yield Static("[bold]Project Tools[/bold]", id="sidebar-title")
                    yield Button(f"{NF['FOLDER']} Browse Files", id="btn-open", variant="primary")
                    yield Button(f"{NF['ADD']} Add Clip", id="btn-add-clip")
                    yield Button(f"{NF['CUT']} Cut", id="btn-cut")
                    yield Button(f"{NF['COPY']} Copy", id="btn-copy")
                    yield Button(f"{NF['PASTE']} Paste", id="btn-paste")
                    yield Button(f"{NF['RENDER']} Render", id="btn-run", variant="success")
                    yield Button(f"{NF['HELP']} README", id="btn-readme")
                    yield Button(f"{NF['EXIT']} Quit", id="btn-quit")
                with Vertical(id="content"):
                    with Horizontal(id="top-bar"):
                        with Vertical(id="top-info"):
                            yield InfoPanel(id="info")
                            yield CommandPreview(id="command")
                        yield PreviewPanel(id="preview")
                    yield TimelinePanel(id="timeline")
                    with VerticalScroll(id="bottom-panel"):
                        with TabbedContent(id="tabs"):
                            with TabPane(f"{NF['PROJECT']} Project", id="project-tab"):
                                yield Static(f"[bold]{NF['CLIP']} Project Bin[/bold]")
                                yield ListView(id="clip-list")
                                with Horizontal(classes="compact-row"):
                                    yield Button(f"{NF['FOLDER']} Browse Files", id="btn-import", variant="primary")
                                    yield Button(f"{NF['ADD']} Add to Timeline", id="btn-add-to-timeline")
                            with TabPane(f"{NF['TIMELINE']} Timeline", id="timeline-tab"):
                                yield Static(f"[bold]{NF['TIMELINE']} Timeline[/bold]")
                                yield Label(f"{NF['VIDEO']} Video Track 1")
                                yield ListView(id="timeline-track-1")
                                yield Label(f"{NF['AUDIO']} Audio Track 1")
                                yield ListView(id="timeline-track-2")
                            with TabPane(f"{NF['EFFECTS']} Effects", id="effects-tab"):
                                yield Static(f"[bold]{NF['EFFECTS']} Effects & Filters[/bold]")
                                yield Select(
                                    [(f"{NF['CROP']} Crop", "crop"),
                                     (f"{NF['SCALE']} Scale", "scale"),
                                     (f"{NF['ROTATE']} Rotate", "rotate"),
                                     (f"{NF['FLIP']} Flip", "flip")],
                                    value="crop", id="effect-type",
                                )
                            with TabPane(f"{NF['PROPERTIES']} Properties", id="properties-tab"):
                                yield Static(f"[bold]{NF['PROPERTIES']} Clip Properties[/bold]")
                                yield Label(f"{NF['CLOCK']} Duration")
                                yield Input(placeholder="00:00:00", id="prop-duration")
                                yield Label(f"{NF['SPEED']} Speed")
                                yield Input(value="1.0", id="prop-speed")
                    with Vertical(id="progress-area"):
                        yield ProgressBar(total=100, show_eta=False, id="progress")
                    yield Static(f"{NF['CHECK']} Ready.", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._install_theme()
        self._update_command_preview()
        if is_kitty():
            self.query_one("#status", Static).update(
                f"{NF['CHECK']} Kitty detected - inline preview enabled."
            )
        else:
            self.query_one("#status", Static).update(
                f"{NF['INFO']} Not in Kitty - previews disabled, encoding works."
            )

    def _install_theme(self) -> None:
        from textual.theme import Theme
        self._theme = Theme(
            name="ffkitty-light", primary="#3b82f6",
            secondary="#6366f1", accent="#8b5cf6",
            success="#22c55e", warning="#f59e0b",
            error="#ef4444", surface="#f8fafc",
            panel="#e2e8f0", boost="#dbeafe",
        )
        self.register_theme(self._theme)

    def _get_input(self, wid: str, default: str = "") -> str:
        try:
            return self.query_one(f"#{wid}", Input).value.strip()
        except NoMatches:
            return default

    def _get_checkbox(self, wid: str) -> bool:
        try:
            return self.query_one(f"#{wid}", Checkbox).value
        except NoMatches:
            return False

    def _get_select(self, wid: str) -> str | None:
        try:
            return str(self.query_one(f"#{wid}", Select).value)
        except NoMatches:
            return None

    def _parse_int(self, wid: str) -> int:
        t = self._get_input(wid)
        return int(t) if t.isdigit() else 0

    def _parse_float(self, wid: str, default: float = 0.0) -> float:
        t = self._get_input(wid)
        try:
            return float(t) if t else default
        except ValueError:
            return default

    def _get_edits(self) -> EditSettings:
        rv = self._get_select("rotate")
        rot = int(rv) if rv and rv.isdigit() else 0
        return EditSettings(
            crop_x=self._parse_int("crop-x"),
            crop_y=self._parse_int("crop-y"),
            crop_w=self._parse_int("crop-w"),
            crop_h=self._parse_int("crop-h"),
            scale_w=self._parse_int("scale-w"),
            scale_h=self._parse_int("scale-h"),
            rotate=rot,
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
            text_x=self._get_input("text-x", "10"),
            text_y=self._get_input("text-y", "10"),
            text_fontsize=max(self._parse_int("text-size"), 1),
            text_color=self._get_input("text-color", "white"),
            text_box=self._get_checkbox("text-box"),
        )

    def _get_encode_job(self) -> FfmpegJob | None:
        if not self.input_path or not self.input_path.exists():
            return None
        ot = self._get_input("output-path")
        out = Path(ot) if ot else default_output_path(self.input_path, self.selected_preset)
        extra = self._get_input("extra-args")
        return FfmpegJob(
            input_path=self.input_path, output_path=out,
            preset=self.selected_preset,
            extra_args=extra.split() if extra else [],
            start=self._get_input("start-time"),
            end=self._get_input("end-time"),
            overwrite=self._get_select("overwrite") == "yes",
            edits=self._get_edits(),
        )

    def _get_concat_job(self) -> ConcatJob | None:
        try:
            text = self.query_one("#concat-files", TextArea).text.strip()
        except NoMatches:
            return None
        if not text:
            return None
        inputs = [Path(l.strip()) for l in text.splitlines() if l.strip()]
        if len(inputs) < 2:
            return None
        for p in inputs:
            if not p.exists():
                return None
        ot = self._get_input("concat-output")
        out = Path(ot) if ot else inputs[0].with_name(f"{inputs[0].stem}_merged.mp4")
        return ConcatJob(
            inputs=inputs, output_path=out,
            overwrite=self._get_select("concat-overwrite") == "yes",
            reencode=self._get_select("concat-mode") == "reencode",
        )

    def _update_timeline(self) -> None:
        self.query_one("#timeline", TimelinePanel).update_selection(
            self._get_input("start-time"),
            self._get_input("end-time"),
            self._get_input("preview-time"),
        )

    def _update_command_preview(self) -> None:
        self._update_timeline()
        job = self._get_encode_job()
        if job:
            self.query_one("#command", CommandPreview).show_command(job.build_command())
        else:
            self.query_one("#command", CommandPreview).update(
                f"{NF['INFO']} Select a file to begin editing."
            )

    def _load_file(self, path: Path) -> None:
        self.input_path = path
        self.output_path = default_output_path(path, self.selected_preset)
        self.query_one("#info", InfoPanel).show_info(path)
        pt = self._get_input("preview-time", "00:00:01")
        self.query_one("#preview", PreviewPanel).set_source(path, pt or "00:00:01")
        self._update_command_preview()
        self.query_one("#status", Static).update(f"{NF['FILE']} Loaded {path.name}")

    @on(Button.Pressed, "#btn-open")
    @on(Button.Pressed, "#btn-import")
    @on(Button.Pressed, "#mnu-browse")
    def action_open_file(self) -> None:
        start = self.input_path.parent if self.input_path else Path.home()
        self.push_screen(FilePicker(start), lambda p: self._load_file(p) if p else None)

    @on(Button.Pressed, "#btn-readme")
    @on(Button.Pressed, "#mnu-readme")
    def action_show_readme(self) -> None:
        self.push_screen(ReadmeScreen())

    @on(Button.Pressed, "#btn-add-clip")
    @on(Button.Pressed, "#mnu-add")
    @on(Button.Pressed, "#btn-add-to-timeline")
    def action_add_clip(self) -> None:
        if not self.input_path:
            self.query_one("#status", Static).update(
                f"{NF['WARNING']} No file selected. Browse for a file first."
            )
            return
        info = probe_media(self.input_path)
        self.clips.append(Clip(
            path=self.input_path, duration=info.duration,
            in_point=self._get_input("start-time", "00:00:00"),
            out_point=self._get_input("end-time"),
        ))
        self.query_one("#status", Static).update(f"{NF['ADD']} Added clip to project")

    @on(Button.Pressed, "#btn-cut")
    @on(Button.Pressed, "#mnu-cut")
    def action_cut(self) -> None:
        self.query_one("#status", Static).update(f"{NF['CUT']} Cut at position")

    @on(Button.Pressed, "#btn-copy")
    @on(Button.Pressed, "#mnu-copy")
    def action_copy(self) -> None:
        self.query_one("#status", Static).update(f"{NF['COPY']} Copied clip")

    @on(Button.Pressed, "#btn-paste")
    @on(Button.Pressed, "#mnu-paste")
    def action_paste(self) -> None:
        self.query_one("#status", Static).update(f"{NF['PASTE']} Pasted clip")

    @on(Button.Pressed, "#btn-run")
    @on(Button.Pressed, "#mnu-render")
    def action_render(self) -> None:
        self.action_run_job()

    @on(Button.Pressed, "#btn-quit")
    def action_quit(self) -> None:
        self.exit()

    def action_run_job(self) -> None:
        job = self._get_encode_job()
        if not job:
            self.query_one("#status", Static).update(f"{NF['ERROR']} Choose a valid input file.")
            return
        if job.output_path.exists() and not job.overwrite:
            self.query_one("#status", Static).update(
                f"{NF['WARNING']} Output exists - enable overwrite."
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
        status.update(f"{NF['SYNC']} Running ffmpeg -> {job.output_path.name}")

        if isinstance(job, FfmpegJob):
            info = probe_media(job.input_path)
            duration = job.output_duration(info.duration)
        else:
            duration = sum(probe_media(p).duration for p in job.inputs)

        cmd = job.build_command()
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        assert proc.stderr is not None
        while True:
            line = (await proc.stderr.readline()).decode(errors="replace").strip()
            if not line:
                break
            pct = parse_ffmpeg_progress(line, duration)
            if pct is not None:
                progress.update(progress=int(pct * 100))

        code = await proc.wait()
        run_btn.disabled = False

        if isinstance(job, ConcatJob) and not job.reencode:
            lp = job.output_path.with_suffix(".concat.txt")
            if lp.exists():
                lp.unlink()

        if code == 0:
            progress.update(progress=100)
            status.update(f"{NF['CHECK']} Done: {job.output_path}")
        else:
            progress.update(progress=0)
            status.update(f"{NF['ERROR']} ffmpeg failed (exit {code})")

    @on(TabbedContent.TabActivated, "#tabs")
    def on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.pane and event.pane.id:
            self.active_tab = event.pane.id
        self._update_command_preview()

    @on(Input.Changed)
    def on_any_input_changed(self) -> None:
        t = self._get_input("input-path")
        if t:
            self.input_path = Path(t)
        self._update_command_preview()


def main() -> None:
    FfkittyApp().run()


if __name__ == "__main__":
    main()

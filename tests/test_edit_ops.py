from pathlib import Path

from ffkitty.app import ToolPanel, describe_tool_context
from ffkitty.edit_ops import EditSettings, build_timeline_summary


def test_drawtext_filter_is_built_from_overlay_settings() -> None:
    settings = EditSettings(text_overlay="Hello", text_x="10", text_y="10")

    filters = settings.build_video_filters()

    assert any("drawtext" in filter_name for filter_name in filters)
    assert any("Hello" in filter_name for filter_name in filters)


def test_timeline_summary_reports_selection_duration() -> None:
    summary = build_timeline_summary("00:00:10", "00:00:20", "00:00:15")

    assert summary == "Track: 00:00:10 → 00:00:20 (10.0s)"


def test_tool_context_describes_edit_mode() -> None:
    summary = describe_tool_context("edit-tab")

    assert summary == "Edit • Transform • Text overlay"


def test_tool_panel_uses_button_label_for_context() -> None:
    panel = ToolPanel(id="tool-panel")
    panel.update_context("encode-tab", Path("clip.mp4"), "open")

    assert panel.label == "Open • Choose a file to inspect and prepare"

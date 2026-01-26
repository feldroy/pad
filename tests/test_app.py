"""Tests for pad.app module."""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import App

from rich.markup import MarkupError

from pad.app import ContentSearchModal


class _TestApp(App):
    """Minimal app to host a modal for testing."""

    def __init__(self, modal: ContentSearchModal) -> None:
        super().__init__()
        self._modal = modal

    async def on_mount(self) -> None:
        self.push_screen(self._modal)


def test_content_search_handles_markup_in_results(monkeypatch, tmp_path: Path) -> None:
    """Should not crash when results contain invalid markup syntax."""
    file_path = tmp_path / "example.txt"
    file_path.write_text("[broken markup\n")
    modal = ContentSearchModal(tmp_path)

    import importlib

    pad_app = importlib.import_module("pad.app")

    class RaisingLabel(pad_app.Label):
        def __init__(self, renderable="", *args, **kwargs):
            if (
                isinstance(renderable, str)
                and "[broken markup" in renderable
                and kwargs.get("markup", True)
            ):
                raise MarkupError("bad markup")
            super().__init__(renderable, *args, **kwargs)

    def fake_find(*_args, **_kwargs):
        return iter([
            {
                "path": str(file_path),
                "line_number": 3,
                "line_text": "[broken markup",
            }
        ])

    monkeypatch.setattr(pad_app, "Label", RaisingLabel)
    monkeypatch.setattr(pad_app.vexy_glob, "find", fake_find)

    async def run_test() -> None:
        app = _TestApp(modal)
        async with app.run_test() as pilot:
            await pilot.pause()
            modal._perform_search("br")
            await pilot.pause()

            results_container = modal.query_one("#content-results")
            assert len(list(results_container.children)) == 1

    asyncio.run(run_test())


def test_content_search_skips_binary_files(monkeypatch, tmp_path: Path) -> None:
    """Should ignore matches that come from binary files."""
    text_file = tmp_path / "notes.txt"
    text_file.write_text("hello world\n")
    binary_file = tmp_path / "blob.bin"
    binary_file.write_bytes(b"\x00\xff\x00\x10")

    modal = ContentSearchModal(tmp_path)

    def fake_find(*_args, **_kwargs):
        return iter([
            {
                "path": str(binary_file),
                "line_number": 1,
                "line_text": "\x00\xff\x00",
            },
            {
                "path": str(text_file),
                "line_number": 1,
                "line_text": "hello world",
            },
        ])

    import importlib

    pad_app = importlib.import_module("pad.app")
    monkeypatch.setattr(pad_app.vexy_glob, "find", fake_find)

    async def run_test() -> None:
        app = _TestApp(modal)
        async with app.run_test() as pilot:
            await pilot.pause()
            modal._perform_search("he")
            await pilot.pause()

            assert len(modal.results) == 1
            assert modal.results[0][0] == text_file

    asyncio.run(run_test())

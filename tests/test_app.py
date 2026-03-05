"""Tests for pad.app module."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from textual.app import App
from textual.screen import ModalScreen

from rich.markup import MarkupError

from pad.app import (
    ContentSearchModal,
    GoToLineModal,
    PadApp,
    SaveExitConfirmModal,
    TextSearchModal,
)


class _TestApp(App):
    """Minimal app to host a modal for testing."""

    def __init__(self, modal: ModalScreen[object]) -> None:
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
        return iter(
            [
                {
                    "path": str(file_path),
                    "line_number": 3,
                    "line_text": "[broken markup",
                }
            ]
        )

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
        return iter(
            [
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
            ]
        )

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


def test_text_search_modal_renders_at_bottom() -> None:
    """Text search modal should be docked to the bottom of the screen."""
    modal = TextSearchModal("sample text", lambda _position: None)

    async def run_test() -> None:
        app = _TestApp(modal)
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()

            container = modal.query_one("#text-search-container")
            screen_bottom = app.screen.region.bottom

            assert modal.styles.align == ("center", "bottom")
            assert screen_bottom - container.region.bottom == 1

    asyncio.run(run_test())


def test_goto_line_modal_renders_at_bottom() -> None:
    """Go-to-line modal should be docked to the bottom of the screen."""
    modal = GoToLineModal(200)

    async def run_test() -> None:
        app = _TestApp(modal)
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()

            container = modal.query_one("#goto-container")
            screen_bottom = app.screen.region.bottom

            assert modal.styles.align == ("center", "bottom")
            assert screen_bottom - container.region.bottom == 1

    asyncio.run(run_test())


def test_save_and_exit_prompts_when_modified_and_saves_on_confirm(
    monkeypatch, tmp_path: Path
) -> None:
    """Ctrl+W should prompt, then save and exit after confirmation."""
    file_path = tmp_path / "example.txt"
    file_path.write_text("before")

    app = PadApp(tmp_path)
    app.current_file = file_path
    app.editor = SimpleNamespace(text="after", focus=lambda: None)
    app.file_modified = True

    exited = False
    prompted = False

    def fake_exit() -> None:
        nonlocal exited
        exited = True

    def fake_push_screen(modal, callback) -> None:
        nonlocal prompted
        prompted = True
        assert isinstance(modal, SaveExitConfirmModal)
        callback(True)

    monkeypatch.setattr(app, "exit", fake_exit)
    monkeypatch.setattr(app, "notify", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "push_screen", fake_push_screen)

    app.action_save_and_exit()

    assert prompted
    assert file_path.read_text() == "after"
    assert exited


def test_save_and_exit_does_not_save_or_exit_when_prompt_cancelled(
    monkeypatch, tmp_path: Path
) -> None:
    """Ctrl+W should not save or exit when user cancels the prompt."""
    file_path = tmp_path / "example.txt"
    file_path.write_text("before")

    app = PadApp(tmp_path)
    app.current_file = file_path

    focused = False

    def fake_focus() -> None:
        nonlocal focused
        focused = True

    app.editor = SimpleNamespace(text="after", focus=fake_focus)
    app.file_modified = True

    exited = False

    def fake_exit() -> None:
        nonlocal exited
        exited = True

    def fake_push_screen(_modal, callback) -> None:
        callback(False)

    monkeypatch.setattr(app, "exit", fake_exit)
    monkeypatch.setattr(app, "notify", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "push_screen", fake_push_screen)

    app.action_save_and_exit()

    assert file_path.read_text() == "before"
    assert focused
    assert not exited


def test_save_and_exit_does_not_exit_on_save_error_after_confirm(
    monkeypatch, tmp_path: Path
) -> None:
    """Ctrl+W should not exit if save fails after confirmation."""
    file_path = tmp_path / "missing" / "example.txt"

    app = PadApp(tmp_path)
    app.current_file = file_path
    app.editor = SimpleNamespace(text="after", focus=lambda: None)
    app.file_modified = True

    exited = False

    def fake_exit() -> None:
        nonlocal exited
        exited = True

    def fake_push_screen(_modal, callback) -> None:
        callback(True)

    monkeypatch.setattr(app, "exit", fake_exit)
    monkeypatch.setattr(app, "notify", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "push_screen", fake_push_screen)

    app.action_save_and_exit()

    assert not exited

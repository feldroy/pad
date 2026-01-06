"""Pad - A command-line code editor built with Textual."""

import fnmatch
from pathlib import Path
from typing import Iterable

import vexy_glob

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    Static,
    TextArea,
)


class GitignoreFilter:
    """Parses and applies .gitignore patterns."""

    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path
        self.patterns: list[tuple[str, bool]] = []  # (pattern, is_negation)
        self._load_gitignore()

    def _load_gitignore(self) -> None:
        """Load patterns from .gitignore file."""
        gitignore_path = self.root_path / ".gitignore"
        if not gitignore_path.exists():
            return

        try:
            content = gitignore_path.read_text()
            for line in content.splitlines():
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Check for negation
                is_negation = line.startswith("!")
                if is_negation:
                    line = line[1:]

                self.patterns.append((line, is_negation))
        except Exception:
            pass  # Ignore errors reading .gitignore

    def is_ignored(self, path: Path) -> bool:
        """Check if a path should be ignored based on .gitignore patterns."""
        try:
            relative = path.relative_to(self.root_path)
        except ValueError:
            return False

        # Check the path itself and all parent directories
        # If any parent is ignored, the path should be ignored too
        paths_to_check = [relative] + list(relative.parents)[:-1]  # Exclude '.'

        for check_path in paths_to_check:
            if self._path_matches_patterns(check_path, path if check_path == relative else self.root_path / check_path):
                return True

        return False

    def _path_matches_patterns(self, relative: Path, full_path: Path) -> bool:
        """Check if a specific path matches any gitignore pattern."""
        relative_str = str(relative)
        name = relative.name

        ignored = False
        for pattern, is_negation in self.patterns:
            matched = False

            # Handle directory-only patterns (ending with /)
            if pattern.endswith("/"):
                if full_path.is_dir():
                    pattern = pattern[:-1]
                else:
                    continue

            # Handle patterns with /
            if "/" in pattern and not pattern.startswith("/"):
                # Pattern with / matches from root
                matched = fnmatch.fnmatch(relative_str, pattern) or fnmatch.fnmatch(
                    relative_str, f"**/{pattern}"
                )
            elif pattern.startswith("/"):
                # Anchored to root
                matched = fnmatch.fnmatch(relative_str, pattern[1:])
            else:
                # Match against name only, or full path with **
                matched = fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(
                    relative_str, f"**/{pattern}"
                )

            if matched:
                ignored = not is_negation

        return ignored


class FilteredDirectoryTree(DirectoryTree):
    """DirectoryTree that respects .gitignore patterns."""

    # Always exclude these directories (they're not typically in .gitignore)
    ALWAYS_EXCLUDED = {".git", ".venv", "__pycache__"}

    def __init__(
        self,
        path: Path,
        gitignore_filter: GitignoreFilter | None = None,
        show_ignored: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(path, **kwargs)
        self.gitignore_filter = gitignore_filter
        self.show_ignored = show_ignored

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """Filter out gitignored paths."""
        if self.show_ignored:
            return paths

        result = []
        for p in paths:
            # Always skip .git, .venv, __pycache__
            if p.name in self.ALWAYS_EXCLUDED:
                continue
            # Skip gitignored files
            if self.gitignore_filter and self.gitignore_filter.is_ignored(p):
                continue
            result.append(p)
        return result


class FileSearchModal(ModalScreen[Path | None]):
    """Modal for searching and opening files."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    FileSearchModal {
        align: center middle;
    }

    #search-container {
        width: 60%;
        max-width: 80;
        height: auto;
        max-height: 20;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }

    #search-input {
        width: 100%;
        margin-bottom: 1;
    }

    #search-results {
        height: auto;
        max-height: 15;
        overflow-y: auto;
    }

    .search-result {
        padding: 0 1;
    }

    .search-result:hover {
        background: $accent;
    }

    .search-result.--selected {
        background: $accent;
    }
    """

    def __init__(
        self,
        root_path: Path,
        gitignore_filter: GitignoreFilter | None = None,
        show_ignored: bool = False,
    ) -> None:
        super().__init__()
        self.root_path = root_path
        self.gitignore_filter = gitignore_filter
        self.show_ignored = show_ignored
        self.results: list[Path] = []
        self.selected_index = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="search-container"):
            yield Input(placeholder="Search for files...", id="search-input")
            yield Vertical(id="search-results")

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.lower()
        results_container = self.query_one("#search-results", Vertical)
        results_container.remove_children()

        if not query:
            self.results = []
            return

        # Search for files matching the query
        self.results = []
        # Always exclude these directories (they're not typically in .gitignore)
        always_excluded = {".git", ".venv", "__pycache__"}
        try:
            for path in self.root_path.rglob("*"):
                # Always skip .git, .venv, __pycache__ unless show_ignored
                if not self.show_ignored:
                    if any(part in always_excluded for part in path.parts):
                        continue
                    # Also skip gitignored files
                    if (
                        self.gitignore_filter
                        and self.gitignore_filter.is_ignored(path)
                    ):
                        continue
                if path.is_file() and query in path.name.lower():
                    self.results.append(path)
                    if len(self.results) >= 20:
                        break
        except PermissionError:
            pass

        self.selected_index = 0
        for i, path in enumerate(self.results):
            relative = path.relative_to(self.root_path)
            label = Label(str(relative), classes="search-result")
            if i == 0:
                label.add_class("--selected")
            results_container.mount(label)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.results:
            self.dismiss(self.results[self.selected_index])
        else:
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "down" and self.results:
            self._update_selection(1)
            event.prevent_default()
        elif event.key == "up" and self.results:
            self._update_selection(-1)
            event.prevent_default()

    def _update_selection(self, delta: int) -> None:
        if not self.results:
            return

        results = self.query(".search-result")
        if results:
            results[self.selected_index].remove_class("--selected")

        self.selected_index = (self.selected_index + delta) % len(self.results)

        if results:
            results[self.selected_index].add_class("--selected")

    def action_cancel(self) -> None:
        self.dismiss(None)


class TextSearchModal(ModalScreen[None]):
    """Modal for searching text within the file."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    TextSearchModal {
        align: center middle;
    }

    #text-search-container {
        width: 60%;
        max-width: 80;
        height: auto;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }

    #text-search-input {
        width: 100%;
        margin-bottom: 1;
    }

    #match-count {
        height: 1;
        color: $text-muted;
    }
    """

    def __init__(self, text: str, navigate_callback) -> None:
        super().__init__()
        self.text = text
        self.navigate_callback = navigate_callback
        self.matches: list[tuple[int, int]] = []  # List of (row, col) positions
        self.current_match_index = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="text-search-container"):
            yield Input(placeholder="Search...", id="text-search-input")
            yield Label("", id="match-count")

    def on_mount(self) -> None:
        self.query_one("#text-search-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value
        match_label = self.query_one("#match-count", Label)

        if not query:
            self.matches = []
            self.current_match_index = 0
            match_label.update("")
            return

        # Find all matches
        self.matches = []
        lines = self.text.split("\n")
        for row, line in enumerate(lines):
            col = 0
            while True:
                pos = line.find(query, col)
                if pos == -1:
                    break
                self.matches.append((row, pos))
                col = pos + 1

        self.current_match_index = 0
        if self.matches:
            match_label.update(f"1 of {len(self.matches)} matches")
            # Navigate to first match
            self.navigate_callback(self.matches[0])
        else:
            match_label.update("No matches")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if not self.matches:
            return

        # Move to next match
        self.current_match_index = (self.current_match_index + 1) % len(self.matches)
        match_label = self.query_one("#match-count", Label)
        match_label.update(
            f"{self.current_match_index + 1} of {len(self.matches)} matches"
        )

        # Navigate to the match
        self.navigate_callback(self.matches[self.current_match_index])

    def action_cancel(self) -> None:
        self.dismiss(None)


class ContentSearchModal(ModalScreen[tuple[Path, int] | None]):
    """Modal for searching content across all files in the project."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    ContentSearchModal {
        align: center middle;
    }

    #content-search-container {
        width: 60%;
        max-width: 100;
        height: 80%;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }

    #content-search-header {
        height: auto;
        margin-bottom: 1;
    }

    #content-search-input {
        width: 100%;
        margin-bottom: 1;
    }

    #case-sensitive-container {
        height: 1;
        margin-bottom: 1;
    }

    #case-sensitive-label {
        margin-left: 1;
    }

    #content-results {
        height: 1fr;
        overflow-y: auto;
    }

    .content-result {
        padding: 0 1;
    }

    .content-result:hover {
        background: $accent;
    }

    .content-result.--selected {
        background: $accent;
    }

    #search-status {
        height: 1;
        color: $text-muted;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        root_path: Path,
        gitignore_filter: GitignoreFilter | None = None,
        show_ignored: bool = False,
    ) -> None:
        super().__init__()
        self.root_path = root_path
        self.gitignore_filter = gitignore_filter
        self.show_ignored = show_ignored
        self.results: list[tuple[Path, int, str]] = []  # (path, line_num, line_text)
        self.selected_index = 0
        self.case_sensitive = False
        # Always exclude these directories
        self.always_excluded = {".git", ".venv", "__pycache__"}

    def compose(self) -> ComposeResult:
        from textual.widgets import Checkbox

        with Vertical(id="content-search-container"):
            yield Input(placeholder="Search content across files...", id="content-search-input")
            with Horizontal(id="case-sensitive-container"):
                yield Checkbox("Case sensitive", id="case-sensitive-checkbox", value=False)
            yield Vertical(id="content-results")
            yield Label("", id="search-status")

    def on_mount(self) -> None:
        self.query_one("#content-search-input", Input).focus()

    def on_checkbox_changed(self, event) -> None:
        if event.checkbox.id == "case-sensitive-checkbox":
            self.case_sensitive = event.value
            # Re-run search with new case sensitivity
            search_input = self.query_one("#content-search-input", Input)
            if search_input.value:
                self._perform_search(search_input.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "content-search-input":
            if self.results:
                path, line_num, _ = self.results[self.selected_index]
                self.dismiss((path, line_num))
            else:
                self._perform_search(event.value)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "content-search-input":
            self._perform_search(event.value)

    def _perform_search(self, query: str) -> None:
        results_container = self.query_one("#content-results", Vertical)
        status_label = self.query_one("#search-status", Label)
        results_container.remove_children()

        if not query or len(query) < 2:
            self.results = []
            status_label.update("Type at least 2 characters to search")
            return

        status_label.update("Searching...")
        self.results = []

        try:
            # Use vexy_glob to search file contents
            # Use iterator (as_list=False) to avoid loading all results into memory
            matches = vexy_glob.find(
                pattern="*",
                root=self.root_path,
                content=query,
                ignore_git=True,
                case_sensitive=self.case_sensitive,
                as_list=False,
            )

            for match in matches:
                if len(self.results) >= 100:
                    break
                # Each match is a dict with path, line_number, line_text keys
                match_path = Path(match["path"])

                # Skip ignored files unless show_ignored is True
                if not self.show_ignored:
                    # Check always excluded directories
                    if any(part in self.always_excluded for part in match_path.parts):
                        continue
                    # Check gitignore patterns
                    if self.gitignore_filter and self.gitignore_filter.is_ignored(match_path):
                        continue

                self.results.append((
                    match_path,
                    match["line_number"],
                    match["line_text"].strip()[:80]  # Truncate long lines
                ))

        except Exception as e:
            status_label.update(f"Search error: {e}")
            return

        self.selected_index = 0
        if not self.results:
            status_label.update("No matches found")
            return

        if len(self.results) >= 100:
            status_label.update(f"Showing first 100 matches (more available)")
        else:
            status_label.update(f"Found {len(self.results)} matches")

        for i, (path, line_num, line_text) in enumerate(self.results):
            try:
                relative = path.relative_to(self.root_path)
            except ValueError:
                relative = path
            display_text = f"{relative}:{line_num}: {line_text}"
            label = Label(display_text, classes="content-result")
            if i == 0:
                label.add_class("--selected")
            results_container.mount(label)

    def on_key(self, event) -> None:
        if event.key == "down" and self.results:
            self._update_selection(1)
            event.prevent_default()
        elif event.key == "up" and self.results:
            self._update_selection(-1)
            event.prevent_default()
        elif event.key == "enter" and self.results:
            path, line_num, _ = self.results[self.selected_index]
            self.dismiss((path, line_num))
            event.prevent_default()

    def _update_selection(self, delta: int) -> None:
        if not self.results:
            return

        results = self.query(".content-result")
        if results:
            results[self.selected_index].remove_class("--selected")

        self.selected_index = (self.selected_index + delta) % len(self.results)

        if results:
            selected = results[self.selected_index]
            selected.add_class("--selected")
            # Scroll selected item into view
            selected.scroll_visible()

    def on_label_clicked(self, event) -> None:
        """Handle clicking on a search result."""
        if "content-result" in event.label.classes:
            results = list(self.query(".content-result"))
            try:
                index = results.index(event.label)
                if index < len(self.results):
                    path, line_num, _ = self.results[index]
                    self.dismiss((path, line_num))
            except ValueError:
                pass

    def action_cancel(self) -> None:
        self.dismiss(None)


class GoToLineModal(ModalScreen[int | None]):
    """Modal for jumping to a specific line number."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    GoToLineModal {
        align: center middle;
    }

    #goto-container {
        width: 50%;
        max-width: 60;
        height: auto;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }

    #goto-label {
        margin-bottom: 1;
    }

    #goto-input {
        width: 100%;
    }
    """

    def __init__(self, max_line: int) -> None:
        super().__init__()
        self.max_line = max_line

    def compose(self) -> ComposeResult:
        with Vertical(id="goto-container"):
            yield Label(
                f"Type a line number between 1 and {self.max_line}", id="goto-label"
            )
            yield Input(placeholder="Line number...", id="goto-input")

    def on_mount(self) -> None:
        self.query_one("#goto-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        try:
            line_num = int(event.value)
            if 1 <= line_num <= self.max_line:
                self.dismiss(line_num)
            else:
                self.notify(
                    f"Line number must be between 1 and {self.max_line}",
                    severity="warning",
                )
        except ValueError:
            self.notify("Please enter a valid number", severity="warning")

    def action_cancel(self) -> None:
        self.dismiss(None)


class QuitConfirmModal(ModalScreen[bool]):
    """Modal for confirming quit action."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+q", "confirm", "Quit"),
    ]

    CSS = """
    QuitConfirmModal {
        align: center middle;
    }

    #quit-container {
        width: 40%;
        max-width: 50;
        height: auto;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }

    #quit-label {
        text-align: center;
        margin-bottom: 1;
    }

    #quit-buttons {
        align: center middle;
        height: auto;
    }

    .quit-button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        from textual.widgets import Button

        with Vertical(id="quit-container"):
            yield Label("Are you sure you want to quit?", id="quit-label")
            with Horizontal(id="quit-buttons"):
                yield Button(
                    "Yes", id="quit-yes", classes="quit-button", variant="error"
                )
                yield Button("No", id="quit-no", classes="quit-button")
            yield Label(
                "You can use ctrl+q again to quit.", id="quit-label-ctrl-q-again"
            )

    def on_mount(self) -> None:
        self.query_one("#quit-no").focus()

    def on_button_pressed(self, event) -> None:
        if event.button.id == "quit-yes":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)


class FileChangedModal(ModalScreen[bool]):
    """Modal for prompting user when file has changed on disk."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    FileChangedModal {
        align: center middle;
    }

    #file-changed-container {
        width: 50%;
        max-width: 70;
        height: auto;
        background: $surface;
        border: tall $warning;
        padding: 1 2;
    }

    #file-changed-label {
        text-align: center;
        margin-bottom: 1;
    }

    #file-changed-buttons {
        align: center middle;
        height: auto;
    }

    .file-changed-button {
        margin: 0 1;
    }
    """

    def __init__(self, filename: str) -> None:
        super().__init__()
        self.filename = filename

    def compose(self) -> ComposeResult:
        from textual.widgets import Button

        with Vertical(id="file-changed-container"):
            yield Label(
                f"'{self.filename}' has been modified on disk.\nDo you want to reload it?",
                id="file-changed-label",
            )
            with Horizontal(id="file-changed-buttons"):
                yield Button(
                    "Reload",
                    id="reload-yes",
                    classes="file-changed-button",
                    variant="warning",
                )
                yield Button(
                    "Keep Current", id="reload-no", classes="file-changed-button"
                )

    def on_mount(self) -> None:
        self.query_one("#reload-yes").focus()

    def on_button_pressed(self, event) -> None:
        if event.button.id == "reload-yes":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


class FileBrowserModal(ModalScreen[Path | None]):
    """Modal for browsing and selecting files."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+b", "cancel", "Close"),
    ]

    CSS = """
    FileBrowserModal {
        align: center middle;
    }

    #browser-container {
        width: 60%;
        height: 80%;
        background: $surface;
        border: tall $primary;
        padding: 1;
    }

    #browser-tree {
        width: 100%;
        height: 100%;
    }
    """

    def __init__(
        self,
        root_path: Path,
        current_file: Path | None = None,
        gitignore_filter: GitignoreFilter | None = None,
        show_ignored: bool = False,
    ) -> None:
        super().__init__()
        self.root_path = root_path
        self.current_file = current_file
        self.gitignore_filter = gitignore_filter
        self.show_ignored = show_ignored

    def compose(self) -> ComposeResult:
        with Vertical(id="browser-container"):
            yield FilteredDirectoryTree(
                self.root_path,
                gitignore_filter=self.gitignore_filter,
                show_ignored=self.show_ignored,
                id="browser-tree",
            )

    async def on_mount(self) -> None:
        import asyncio

        tree = self.query_one("#browser-tree", FilteredDirectoryTree)
        tree.focus()

        # If we have a current file, expand to it
        if self.current_file and self.current_file.exists():
            try:
                relative = self.current_file.relative_to(self.root_path)
                parts = relative.parts

                # Expand each directory in the path
                current_path = self.root_path
                for part in parts[:-1]:  # All but the last part (the file)
                    current_path = current_path / part
                    node = self._find_node_for_path(tree, current_path)
                    if node:
                        node.expand()
                        await asyncio.sleep(0.05)  # Wait for children to load

                # Find the file node and move cursor to it
                file_node = self._find_node_for_path(tree, self.current_file)
                if file_node and file_node.line >= 0:
                    tree.cursor_line = file_node.line
            except (ValueError, Exception):
                pass  # File is not under root_path or other error

    def _find_node_for_path(self, tree: FilteredDirectoryTree, target_path: Path):
        """Find the tree node for a given path."""

        def search(node):
            if hasattr(node, "data") and node.data and node.data.path == target_path:
                return node
            for child in node.children:
                result = search(child)
                if result:
                    return result
            return None

        return search(tree.root)

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        self.dismiss(event.path)

    def action_cancel(self) -> None:
        self.dismiss(None)


class Editor(TextArea):
    """Code editor with syntax highlighting."""

    CSS = """
    Editor {
        width: 100%;
        height: 100%;
    }
    """

    # Override TextArea's default ctrl+f binding to bubble up to app
    BINDINGS = [
        Binding("ctrl+f", "app_search_text", "Find", priority=True),
    ]

    def action_app_search_text(self) -> None:
        """Bubble up to app's search_text action."""
        self.app.action_search_text()

    # Auto-close pairs: opening -> closing
    AUTO_CLOSE_PAIRS = {
        "(": ")",
        "[": "]",
        "{": "}",
        '"': '"',
        "'": "'",
    }

    def __init__(
        self, text: str = "", *, language: str | None = None, **kwargs
    ) -> None:
        super().__init__(
            text,
            language=language,
            theme="monokai",
            tab_behavior="indent",
            show_line_numbers=True,
            **kwargs,
        )

    def _on_key(self, event) -> None:
        """Handle auto-closing of brackets and quotes."""
        if event.character in self.AUTO_CLOSE_PAIRS:
            closing = self.AUTO_CLOSE_PAIRS[event.character]
            row, col = self.cursor_location

            # Get current line text
            lines = self.text.split("\n")
            if row < len(lines):
                line = lines[row]
                char_after = line[col] if col < len(line) else ""

                # For quotes: if next char is the same quote, just move past it
                if event.character in ('"', "'") and char_after == event.character:
                    self.cursor_location = (row, col + 1)
                    event.prevent_default()
                    return

            # Insert both opening and closing, then move cursor back
            self.insert(event.character + closing)
            self.cursor_location = (row, col + 1)
            event.prevent_default()
            return

        # Handle typing closing bracket when it's already there
        if event.character in (")", "]", "}"):
            row, col = self.cursor_location
            lines = self.text.split("\n")
            if row < len(lines):
                line = lines[row]
                if col < len(line) and line[col] == event.character:
                    # Just move past the closing bracket
                    self.cursor_location = (row, col + 1)
                    event.prevent_default()
                    return

        super()._on_key(event)


class EditorPane(Vertical):
    """Container for the editor with a title bar."""

    CSS = """
    EditorPane {
        width: 100%;
        height: 100%;
    }

    #editor-title {
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
    }

    #no-file {
        width: 100%;
        height: 100%;
        content-align: center middle;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("No file open", id="editor-title")
        yield Static("Press Ctrl+b to search for a file", id="no-file")


class PadApp(App):
    """A command-line code editor."""

    TITLE = "Pad"

    CSS = """
    #main-container {
        width: 100%;
        height: 100%;
    }

    #editor-container {
        width: 1fr;
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("ctrl+b", "toggle_browser", "Browse Files"),
        Binding("ctrl+o", "search_files", "Search Files"),
        Binding("ctrl+f", "search_text", "Find"),
        Binding("ctrl+shift+f", "search_content", "Search Content"),
        Binding("ctrl+g", "goto_line", "Go to Line"),
        Binding("ctrl+s", "save_file", "Save"),
        Binding("ctrl+shift+a", "toggle_autosave", "Toggle Autosave"),
        Binding("ctrl+shift+i", "toggle_show_ignored", "Toggle Ignored"),
        Binding("ctrl+q", "confirm_quit", "Quit"),
        Binding("alt+down", "page_down", "Page Down", show=False),
        Binding("alt+up", "page_up", "Page Up", show=False),
    ]

    def __init__(self, path: Path) -> None:
        super().__init__()
        # Determine if path is a file or directory
        if path.is_file():
            self.initial_file: Path | None = path
            self.root_path = path.parent
        else:
            self.initial_file = None
            self.root_path = path
        self.current_file: Path | None = None
        self.editor: Editor | None = None
        self.file_modified = False
        self.autosave = True
        self.file_mtime: float | None = None  # Track file modification time
        self.checking_file_change = False  # Prevent multiple prompts
        self.show_ignored = False  # Whether to show gitignored files
        self.gitignore_filter = GitignoreFilter(self.root_path)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            with Container(id="editor-container"):
                yield EditorPane(id="editor-pane")
        yield Footer()

    async def on_mount(self) -> None:
        """Open the initial file if one was provided, or README.md if a directory was given."""
        if self.initial_file:
            await self.open_file(self.initial_file)
        else:
            readme_path = self.root_path / "README.md"
            if readme_path.exists():
                await self.open_file(readme_path)

        # Start periodic file change detection (check every 2 seconds)
        self.set_interval(2.0, self._check_file_changed)

    def _save_current_file(self) -> None:
        """Save the current file if modified."""
        if self.current_file and self.editor and self.file_modified:
            try:
                self.current_file.write_text(self.editor.text)
                self.file_modified = False
                # Update mtime after saving
                self.file_mtime = self.current_file.stat().st_mtime
            except Exception as e:
                self.notify(f"Error saving file: {e}", severity="error")

    def _check_file_changed(self) -> None:
        """Check if the current file has been modified on disk."""
        if (
            self.current_file is None
            or self.file_mtime is None
            or self.checking_file_change
            or not self.current_file.exists()
        ):
            return

        try:
            current_mtime = self.current_file.stat().st_mtime
            if current_mtime > self.file_mtime:
                self.checking_file_change = True
                self._prompt_reload()
        except Exception:
            pass  # File might be temporarily unavailable

    def _prompt_reload(self) -> None:
        """Show modal asking user if they want to reload the file."""
        if self.current_file is None:
            return

        async def handle_result(reload: bool) -> None:
            if reload and self.current_file:
                await self._reload_current_file()
            else:
                # User declined reload, update mtime to avoid repeated prompts
                if self.current_file and self.current_file.exists():
                    self.file_mtime = self.current_file.stat().st_mtime
            self.checking_file_change = False
            if self.editor:
                self.editor.focus()

        self.push_screen(FileChangedModal(self.current_file.name), handle_result)

    async def _reload_current_file(self) -> None:
        """Reload the current file from disk."""
        if self.current_file is None or self.editor is None:
            return

        try:
            content = self.current_file.read_text()
            self.file_mtime = self.current_file.stat().st_mtime

            # Preserve cursor position if possible
            cursor_pos = self.editor.cursor_location

            # Update editor content
            self.editor.text = content
            self.file_modified = False

            # Restore cursor position (clamped to valid range)
            line_count = content.count("\n") + 1
            new_row = min(cursor_pos[0], line_count - 1)
            self.editor.cursor_location = (new_row, cursor_pos[1])

            # Update title
            title = self.query_one("#editor-title", Static)
            title.update(f" {self.current_file.name}")

            self.notify(f"Reloaded {self.current_file.name}")
        except Exception as e:
            self.notify(f"Error reloading file: {e}", severity="error")

    async def open_file(self, path: Path) -> None:
        """Open a file in the editor."""
        # Autosave current file before switching
        if self.autosave:
            self._save_current_file()

        try:
            content = path.read_text()
            self.file_mtime = path.stat().st_mtime  # Track modification time
        except Exception as e:
            self.notify(f"Error opening file: {e}", severity="error")
            return

        self.current_file = path
        self.file_modified = False
        self.checking_file_change = False

        # Determine language for syntax highlighting
        language = self._get_language(path)

        # Update the title
        title = self.query_one("#editor-title", Static)
        title.update(f" {path.name}")

        # Check if we already have an editor, update it; otherwise create one
        editor_pane = self.query_one("#editor-pane", EditorPane)

        # Remove the "no file" placeholder if it exists
        no_file = editor_pane.query("#no-file")
        if no_file:
            await no_file.first().remove()

        # Check if editor already exists
        existing_editor = editor_pane.query("#editor")
        if existing_editor:
            # Remove old editor and create new one with correct language
            await existing_editor.first().remove()

        self.editor = Editor(content, language=language, id="editor")
        await editor_pane.mount(self.editor)
        self.editor.focus()

    def _get_language(self, path: Path) -> str | None:
        """Get the language for syntax highlighting based on file extension."""
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".html": "html",
            ".htm": "html",
            ".css": "css",
            ".json": "json",
            ".md": "markdown",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".rs": "rust",
            ".go": "go",
            ".rb": "ruby",
            ".sh": "bash",
            ".bash": "bash",
            ".zsh": "bash",
            ".sql": "sql",
            ".xml": "xml",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
        }
        return extension_map.get(path.suffix.lower())

    def action_toggle_browser(self) -> None:
        """Open the file browser modal."""

        async def handle_result(path: Path | None) -> None:
            if path:
                await self.open_file(path)
            elif self.editor:
                self.editor.focus()

        self.push_screen(
            FileBrowserModal(
                self.root_path,
                self.current_file,
                self.gitignore_filter,
                self.show_ignored,
            ),
            handle_result,
        )

    def action_search_files(self) -> None:
        """Open the file search modal."""

        async def handle_result(path: Path | None) -> None:
            if path:
                await self.open_file(path)

        self.push_screen(
            FileSearchModal(
                self.root_path,
                self.gitignore_filter,
                self.show_ignored,
            ),
            handle_result,
        )

    def action_search_text(self) -> None:
        """Open the text search modal."""
        if self.editor is None:
            self.notify("No file open", severity="warning")
            return

        def navigate_to_match(position: tuple[int, int]) -> None:
            if self.editor:
                row, col = position
                self.editor.cursor_location = (row, col)

                # Center the line in the viewport
                viewport_height = self.editor.size.height
                scroll_y = max(0, row - viewport_height // 2)
                self.editor.scroll_to(0, scroll_y, animate=False)

        self.push_screen(TextSearchModal(self.editor.text, navigate_to_match))

    def action_search_content(self) -> None:
        """Open the content search modal to search across all project files."""

        async def handle_result(result: tuple[Path, int] | None) -> None:
            if result:
                path, line_number = result
                await self.open_file(path)
                # Navigate to the matching line
                if self.editor:
                    # TextArea uses 0-indexed rows
                    target_row = line_number - 1
                    self.editor.cursor_location = (target_row, 0)
                    # Center the line in the viewport
                    viewport_height = self.editor.size.height
                    scroll_y = max(0, target_row - viewport_height // 2)
                    self.editor.scroll_to(0, scroll_y, animate=False)
            elif self.editor:
                self.editor.focus()

        self.push_screen(
            ContentSearchModal(
                self.root_path,
                self.gitignore_filter,
                self.show_ignored,
            ),
            handle_result,
        )

    def action_goto_line(self) -> None:
        """Open the go to line modal."""
        if self.editor is None:
            self.notify("No file open", severity="warning")
            return

        # Count lines in the current file
        line_count = self.editor.text.count("\n") + 1

        def handle_result(line_num: int | None) -> None:
            if line_num is not None and self.editor:
                # TextArea uses 0-indexed rows
                target_row = line_num - 1
                self.editor.cursor_location = (target_row, 0)

                # Center the line in the viewport
                viewport_height = self.editor.size.height
                scroll_y = max(0, target_row - viewport_height // 2)
                self.editor.scroll_to(0, scroll_y, animate=False)

                self.editor.focus()

        self.push_screen(GoToLineModal(line_count), handle_result)

    def action_save_file(self) -> None:
        """Save the current file."""
        if self.current_file is None:
            self.notify("No file open", severity="warning")
            return

        if self.editor is None:
            return

        try:
            content = self.editor.text
            self.current_file.write_text(content)
            self.file_modified = False
            self.file_mtime = self.current_file.stat().st_mtime  # Update mtime
            self.notify(f"Saved {self.current_file.name}")
        except Exception as e:
            self.notify(f"Error saving file: {e}", severity="error")

    def action_toggle_autosave(self) -> None:
        """Toggle autosave on/off."""
        self.autosave = not self.autosave
        status = "ON" if self.autosave else "OFF"
        self.notify(f"Autosave: {status}")

    def action_toggle_show_ignored(self) -> None:
        """Toggle showing gitignored files in browser and search."""
        self.show_ignored = not self.show_ignored
        status = "visible" if self.show_ignored else "hidden"
        self.notify(f"Gitignored files: {status}")

    def action_confirm_quit(self) -> None:
        """Show quit confirmation dialog."""

        def handle_result(confirmed: bool) -> None:
            if confirmed:
                self.exit()
            elif self.editor:
                self.editor.focus()

        self.push_screen(QuitConfirmModal(), handle_result)

    def action_page_down(self) -> None:
        """Move cursor down by one page."""
        if self.editor is None:
            return

        current_row, current_col = self.editor.cursor_location
        viewport_height = self.editor.size.height
        line_count = self.editor.text.count("\n") + 1

        # Move down by viewport height, but don't go past the last line
        new_row = min(current_row + viewport_height, line_count - 1)
        self.editor.cursor_location = (new_row, current_col)

        # Scroll to keep cursor centered
        scroll_y = max(0, new_row - viewport_height // 2)
        self.editor.scroll_to(0, scroll_y, animate=False)

    def action_page_up(self) -> None:
        """Move cursor up by one page."""
        if self.editor is None:
            return

        current_row, current_col = self.editor.cursor_location
        viewport_height = self.editor.size.height

        # Move up by viewport height, but don't go past the first line
        new_row = max(current_row - viewport_height, 0)
        self.editor.cursor_location = (new_row, current_col)

        # Scroll to keep cursor centered
        scroll_y = max(0, new_row - viewport_height // 2)
        self.editor.scroll_to(0, scroll_y, animate=False)

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Track when the file has been modified."""
        if self.current_file and not self.file_modified:
            self.file_modified = True
            title = self.query_one("#editor-title", Static)
            title.update(f" {self.current_file.name} [modified]")


def run(path: Path) -> None:
    """Run the Pad application."""
    app = PadApp(path)
    app.run()

"""Idios - A command-line code editor built with Textual."""

from pathlib import Path

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

    def __init__(self, root_path: Path) -> None:
        super().__init__()
        self.root_path = root_path
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
        try:
            for path in self.root_path.rglob("*"):
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
            yield Label(f"Type a line number between 1 and {self.max_line}", id="goto-label")
            yield Input(placeholder="Line number...", id="goto-input")

    def on_mount(self) -> None:
        self.query_one("#goto-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        try:
            line_num = int(event.value)
            if 1 <= line_num <= self.max_line:
                self.dismiss(line_num)
            else:
                self.notify(f"Line number must be between 1 and {self.max_line}", severity="warning")
        except ValueError:
            self.notify("Please enter a valid number", severity="warning")

    def action_cancel(self) -> None:
        self.dismiss(None)


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

    def __init__(self, root_path: Path) -> None:
        super().__init__()
        self.root_path = root_path

    def compose(self) -> ComposeResult:
        with Vertical(id="browser-container"):
            yield DirectoryTree(self.root_path, id="browser-tree")

    def on_mount(self) -> None:
        self.query_one("#browser-tree", DirectoryTree).focus()

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
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

    def __init__(self, text: str = "", *, language: str | None = None, **kwargs) -> None:
        super().__init__(
            text,
            language=language,
            theme="monokai",
            tab_behavior="indent",
            show_line_numbers=True,
            **kwargs,
        )


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


class IdiosApp(App):
    """A command-line code editor."""

    TITLE = "Idios"

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
        Binding("ctrl+p", "search_files", "Search Files"),
        Binding("ctrl+g", "goto_line", "Go to Line"),
        Binding("ctrl+s", "save_file", "Save"),
        Binding("ctrl+shift+a", "toggle_autosave", "Toggle Autosave"),
        Binding("ctrl+q", "quit", "Quit"),
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

    def _save_current_file(self) -> None:
        """Save the current file if modified."""
        if self.current_file and self.editor and self.file_modified:
            try:
                self.current_file.write_text(self.editor.text)
                self.file_modified = False
            except Exception as e:
                self.notify(f"Error saving file: {e}", severity="error")

    async def open_file(self, path: Path) -> None:
        """Open a file in the editor."""
        # Autosave current file before switching
        if self.autosave:
            self._save_current_file()

        try:
            content = path.read_text()
        except Exception as e:
            self.notify(f"Error opening file: {e}", severity="error")
            return

        self.current_file = path
        self.file_modified = False

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

        self.push_screen(FileBrowserModal(self.root_path), handle_result)

    def action_search_files(self) -> None:
        """Open the file search modal."""
        async def handle_result(path: Path | None) -> None:
            if path:
                await self.open_file(path)

        self.push_screen(FileSearchModal(self.root_path), handle_result)

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
            self.notify(f"Saved {self.current_file.name}")
        except Exception as e:
            self.notify(f"Error saving file: {e}", severity="error")

    def action_toggle_autosave(self) -> None:
        """Toggle autosave on/off."""
        self.autosave = not self.autosave
        status = "ON" if self.autosave else "OFF"
        self.notify(f"Autosave: {status}")

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Track when the file has been modified."""
        if self.current_file and not self.file_modified:
            self.file_modified = True
            title = self.query_one("#editor-title", Static)
            title.update(f" {self.current_file.name} [modified]")


def run(path: Path) -> None:
    """Run the Idios application."""
    app = IdiosApp(path)
    app.run()

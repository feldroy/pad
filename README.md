<p align="center">
<img src="https://feldroy.com/static/pad-logo.png" alt="Pad Logo" width="300"/>
</p>

Pad is an easy to use terminal code editor for those of us who aren't into vim.

## Features

- Runs in the terminal, works great with ghostty
- Responsive, resize the window and it still looks good
- Text editor with code highlighting for the current open file
- If not pointed at a file, opens the current directory, default open file is any README.md that may exist
- Autoclosing of parenthesis, curly braces, brackets, and quotes
- VS Code inspired keyboard shortcuts for fast navigation and editing:
    - `ctrl+c:` copy text
    - `ctrl+v:` paste text
    - `ctrl+z:` undo
    - `ctrl+s:` save current file
    - `ctrl+f:` search in current file
    - `ctrl+g:` go to line
    - `ctrl+b:` file browser
    - `ctrl+o:` file search
    - `ctrl+w:` save current file and exit
    - `ctrl+q:` quit
    - `ctrl+shift+f`: Fast file content search
- Works with some Apple key combinations, depending on your terminal's handling of them. For example, in ghostty, `cmd+s` works as expected to save the current file but `cmd+c` doesn't copy

## Install

```sh
uv tool install pad
```

Currently Pad is untested with any other installation method. If it works for your installation method, let me know and I'll add it to this section.

## Usage

Once installed, point it at a file: 

```sh
pad myproject/README.md
```

Or a directory:

```sh
pad myproject/
```

## Special thanks

Many thanks to [Stan Ovchinnikov](https://github.com/ndtfy) for graciously sharing the "pad" name on PyPI, which was to be a tkinter-based editor. He was kind enough to let me use the name for this project, which is a terminal-based code editor built on textual. If you're interested in how this project might have been built using tkinter, you can check it out [here](https://github.com/ndtfy/pad).

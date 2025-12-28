# idios

Idios (ἴδιος) is an Ancient Greek word that means:

- one’s own
- personal
- distinct / peculiar to an individual
- private, not involved in public affairs, which eventually turned into the word "idiot"

It's also a terminal code editor for those of us who aren't into vim.

## Features

- Powered by Textual TUI
- Runs in the shell
- File browsing that can be opened or closed with cmd-b
- File search can be done by toggling cmd-o
- Files can be saved with cmd-s
- Text editor with code highlighting for the current open file
- Copy (cmd-c) and paste (cmd-v) uses standard IDE keys
- If not pointed at a file, opens the current directory, default open file is any README.md that may exist
- Responsive, resize the window and it still looks good

## Install

```sh
uv tool idios
```

Currently idios is untested with any other installation method. If it works for your installation method, let me know and I'll add it to this section.

## Usage

Once installed, point it at the file you want to view.

```sh
idios myproject/
```
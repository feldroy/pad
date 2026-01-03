<p align="center">
<img src="https://raw.githubusercontent.com/worldimpactlab/pad-app/refs/heads/main/pad-logo.png?token=GHSAT0AAAAAACYGXA6D6UOKJ3T54Y5JNIG62KY673Q" alt="Pad Logo" width="200"/>
</p>


Pad is an easy to use terminal code editor built with Textual for those of us who aren't into vim.

## Features

- Powered by Textual TUI so the accessibility is top notch
- Runs in the shell
- File browsing that can be opened or closed with cmd-b
- File search can be done by toggling cmd-o
- Files can be saved with cmd-s
- Text editor with code highlighting for the current open file
- Copy (cmd-c) and paste (cmd-v) uses standard IDE keys
- Search in a file with ctrl+f
- Go to a line with ctrl+g
- If not pointed at a file, opens the current directory, default open file is any README.md that may exist
- Watches the current file and lets you know if there have been changes
- Responsive, resize the window and it still looks good
- Autoclosing of parenthesis, curly braces, brackets, and quotes

## Install

```sh
uv tool pad-app
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
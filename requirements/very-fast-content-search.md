# Very fast content search

Using vexy_glob (https://pypi.org/project/vexy-glob/) for very fast content search in large codebases.

## Specification

- Use ctrl+shift+f to open the search dialog.
- Type your search query and press enter.
- The search results will be displayed in a new panel.
- Click on a result to open the corresponding file and highlight the search term.
- Use the up and down arrow keys to navigate through the search results.
- Press esc to close the search dialog.
- Uses vexy_glob for fast searching of not just files, but the content inside the files
- Search should only work in the directory of the currently opened project.
- Search is case insensitive by default, with an option to enable case sensitivity.
- Ignore anything specified in .gitignore files.
- If a file has multiple matches, show all matches with line numbers.
- Search panel should show up in the same place as the file explorer panel.
- Panel should close after a result is clicked or when esc is pressed
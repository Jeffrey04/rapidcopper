# Rapid Copper

This is a simple desktop launcher that is heavily inspired by quicksilver. Currently still in prototype form, and am still focusing in getting the CLI interface done properly.

# CLI Usage Example:

## Rebuild index

```
rc rebuild-index
```

## Crude desktop launcher

```
$ rc do firefox
0 app:          /home/jeffrey04/.local/share/applications/userapp-Firefox Developer Edition-EPEGV2.desktop - Custom definition for Firefox Developer Edition
                Firefox Developer Edition
1 app:          /home/jeffrey04/.local/share/applications/firefox-developer.desktop - Firefox Aurora with Developer tools
                Firefox Developer Edition
2 app:          /home/jeffrey04/.local/share/applications/userapp-Firefox Developer Edition-8CCQV2.desktop - Custom definition for Firefox Developer Edition
                Firefox Developer Edition
Enter choice: :
```

## Copying text to clipboard

```
$ rc do echo foo bar '|' clipboard
```

# TUI Usage Example

Start the TUI with

```
rct
```

## Crude desktop launcher

In the input box, type

```
firefox
```

and you should see some candidates below

```
app:          /home/jeffrey04/.local/share/applications/userapp-Firefox Developer Edition-EPEGV2.desktop - Custom definition for Firefox Developer Edition
                Firefox Developer Edition
app:          /home/jeffrey04/.local/share/applications/firefox-developer.desktop - Firefox Aurora with Developer tools
                Firefox Developer Edition
app:          /home/jeffrey04/.local/share/applications/userapp-Firefox Developer Edition-8CCQV2.desktop - Custom definition for Firefox Developer Edition
                Firefox Developer Edition
```

<kbd>TAB</kbd> into the listview, and then use <kbd>UP</kbd> / <kbd>DOWN</kbd> to select, enter to execute

# Writing plugins:

## Actions

- take multiple arguments

  ```
  """a short description of your plugin in the first line"""

  def run (*args: str) -> str | None:
      pass
  ```

- name the file as `action_$name.py` and save it to `$HOME/.config/plugins/`

## Pipes (prolly need better name)

- take just 1 argument

  ```
  """a short description of your plugin in the first line"""

  def run(arg: str) -> str | None:
      pass
  ```

* name the file as `pipe_$name.py` and save it to `$HOME/.config/plugins/`

# Coming Soon

- GUI
- proper code with tests
- allow piping bytes across (e.g. screen capture)
- File searching?
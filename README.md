# Daymark

**A minimal daily scratchpad + task manager for GNOME Linux.**

Write notes. Type `[]` to create a task. That's it.

Daymark lives in your GNOME top panel as a small icon. Click it — a clean popup appears. Click anywhere else — it disappears. No permanent window cluttering your taskbar.

---

## Features

- **Notes-first workflow** — write freely; `[]` at the start of a line becomes a task automatically
- **Task context** — lines below a `[]` task (bullets, numbered steps) attach as collapsible context; hover to expand
- **Carry-forward** — incomplete tasks from past days surface automatically under today's view
- **Date navigation** — 7-day strip + calendar picker; `Alt+Left` / `Alt+Right` to move between days
- **Full-text search** — `Ctrl+F` searches all notes and tasks across all dates
- **Auto-save** — notes save as you type, no buttons
- **Offline / local only** — SQLite, no cloud, no accounts, no telemetry
- **GNOME panel integration** — badge shows pending task count; click to toggle; hides from dock

---

## Install

**Requirements:** GNOME 46+ (Ubuntu 22.04 / 24.04, Fedora 39+), Python 3.11+

```bash
git clone https://github.com/elliotak47/daymark.git
cd daymark
bash install.sh
```

Then **log out and log back in** so GNOME Shell picks up the new extension, then enable it once:

```bash
gnome-extensions enable daymark@daymark.app
```

A pencil icon appears in your top panel. Click it to open Daymark.

---

## How it works

### Notes → Tasks

Type in the notes editor. Any line starting with `[]` becomes a pending task:

```
Meeting prep
[] Send agenda to team
  - Attach last week's notes
  - Confirm attendees

[] Book room 3B
```

Both `[]` lines appear in the Tasks section below. The indented lines become collapsible context — hover over a task to expand it.

Mark done by ticking the checkbox or typing `[x]` in the notes. They stay in sync.

### Quick-add

The **Add a task…** entry at the bottom lets you add tasks without touching the notes editor. Press `Shift+Enter` to add a context line before saving.

### Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+N` | Focus the quick-add entry |
| `Ctrl+F` | Open search |
| `Alt+Left` | Previous day |
| `Alt+Right` | Next day |

---

## Data location

```
~/.local/share/daymark/daymark.db
```

SQLite file. Back it up with any file backup tool. Delete it to start fresh.

---

## Uninstall

```bash
gnome-extensions disable daymark@daymark.app
rm -rf ~/.local/share/gnome-shell/extensions/daymark@daymark.app
rm ~/.local/bin/daymark
rm ~/.config/autostart/daymark.desktop
```

Your database is not touched — delete `~/.local/share/daymark/` manually if you want to remove data too.

---

## Development

```bash
git clone https://github.com/elliotak47/daymark.git
cd daymark
python3 -m venv .venv --system-site-packages
.venv/bin/pip install -e .
PYTHONPATH=src .venv/bin/python -m daymark
```

Run tests:

```bash
.venv/bin/python -m pytest tests/ -v
```

### Project structure

```
daymark/
├── src/daymark/
│   ├── ui/              # GTK4 widgets (main panel, task rows, notes editor, …)
│   ├── core/            # Business logic (tasks, scratchpad, search, rollover, sync)
│   ├── db/              # SQLite database + models
│   └── settings/        # Config persistence
├── gnome-extension/     # GNOME Shell extension (panel icon, badge, D-Bus client)
├── data/                # CSS stylesheet + .desktop file
└── install.sh           # One-step installer
```

---

## Contributing

Issues and pull requests are welcome. Please open an issue first for anything larger than a bug fix so we can discuss direction. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## Tech stack

- **Python 3.11+**
- **GTK4 + libadwaita** via PyGObject
- **SQLite** (stdlib `sqlite3`)
- **GNOME Shell extension** (JS, GJS)
- **D-Bus** for extension ↔ app communication

---

## License

MIT — see [LICENSE](LICENSE)

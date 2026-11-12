# Contributing to Daymark

Thanks for taking the time to contribute.

## Reporting bugs

Open an issue using the **Bug report** template. Include your OS, GNOME version, and steps to reproduce.

## Suggesting features

Open an issue using the **Feature request** template before writing any code, so we can discuss whether it fits the project direction.

## Submitting a pull request

1. Fork the repo and create a branch from `main`
2. Make your change — keep it focused, one thing per PR
3. Run the tests: `.venv/bin/python -m pytest tests/ -v`
4. Open a pull request with a clear description of what and why

## Development setup

```bash
git clone https://github.com/elliotak47/daymark.git
cd daymark
python3 -m venv .venv --system-site-packages
.venv/bin/pip install -e .
PYTHONPATH=src .venv/bin/python -m daymark
```

## Code style

- Python: follow PEP 8, no external formatters required
- Keep functions small and focused
- No new dependencies without discussion — GTK4 + stdlib only

## Project structure

```
src/daymark/
├── ui/       # GTK4 widgets only — no business logic here
├── core/     # Business logic — no GTK imports here
├── db/       # Database layer
└── settings/ # Config persistence
```

The key rule: `ui/` talks to `core/`, never to `db/` directly.

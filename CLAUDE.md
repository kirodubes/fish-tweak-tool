# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

Fish Tweak Tool (FTT) is a standalone GTK4 Python application for configuring the
[fish shell](https://fishshell.com/). Its reason-to-exist is **orchestration** —
installing prompts and plugins that fish's own `fish_config` cannot — plus a
desktop-native theme/preset experience. It is a post-install, per-user tool (no
sudo) and ships in `nemesis_repo`. ATT's Shells → Fish tab will deep-link to it.

- **Language**: Python 3.8+
- **GUI Framework**: GTK4 + PyGObject
- **Entry Point**: `usr/share/fish-tweak-tool/fish-tweak-tool.py`
- **Launcher**: `usr/bin/fish-tweak-tool`
- **Desktop Entry**: `usr/share/applications/fish-tweak-tool.desktop`
- **Runs as normal user** — no sudo, no pkexec; never add root escalation
- **Design study (canonical reference, kept in staging):**
  `~/KIRO-PROJECTS/fish-tweak-tool/fish-tweak-tool.md` and `mining-peer-distro-fish.md`

## Architecture

```
usr/share/fish-tweak-tool/
├── fish-tweak-tool.py   # Entry point: Gtk.Application + Main window
├── ftt_gui.py           # GUI: the four-tab Notebook shell
├── ftt_config.py        # App preferences (window size); NOT the fish config
├── log.py               # Logging: log_section / log_info / log_success / ...
└── ftt.css              # GTK4 stylesheet
```

App modules are prefixed `ftt_` on purpose: `fish_config`, `fish_prompt`, and
`fish_theme` are real fish commands, so a local module named `fish_config.py`
would be a footgun. The entry point keeps the hyphenated `fish-tweak-tool.py`
name because it is executed, never imported.

### Data Locations

| What            | Path                                        |
|-----------------|---------------------------------------------|
| App preferences | `~/.config/fish-tweak-tool/prefs.json`      |
| User fish config| `~/.config/fish/config.fish` (M1+ only)     |

## The config model (read before writing any fish config)

This is the load-order constraint the whole tool is built around — getting it
wrong silently clobbers user settings:

- **Defaults** ship in a *separate* package, `kiro-fish-config`: a payload under
  `/usr/share/…` sourced by a thin `~/.config/fish/config.fish` stub. FTT does
  **not** own those defaults.
- **FTT writes only per-user overrides** — into `~/.config/fish/config.fish`
  **below the `source` line** (the "managed block"). That region loads last, so
  it always wins.
- **Theme & prompt** go through fish's own `fish_config theme save` /
  `prompt save` (universal-var / autoload storage).
- **Never** put FTT's overrides in `~/.config/fish/conf.d/` — fish sources
  `conf.d/*` *before* `config.fish`, so the payload would overwrite them.
- **Never** set the greeting via `set -U` — the payload's `set -g fish_greeting`
  shadows a universal within the session. Set it in the managed block.

## Roadmap (milestones)

- **M0** — Scaffold (done): GTK4 skeleton, launcher, desktop entry.
- **M1** — Prompt & plugin orchestration via `fisher` (the reason-to-exist).
- **M2** — Theme gallery from `fish_config theme`.
- **M3** — Greeting / cursor knobs + backup-restore of `~/.config/fish/`.
- **M4** — Presets (one-click Kiro-default / Minimal / Tide bundles).
- **M5** — nemesis_repo package + ATT deep-link.

Open design decisions still to settle before M1: D8 (preset apply semantics),
D9 (snapshot-before-apply timing), D10 (orchestration failure / offline /
privilege). See the design study.

## Development Patterns

### Logging

All output uses `log.py` (never bare `print()`):

```python
import log

log.log_section("Major Header")    # green section with separators
log.log_info("Informational")      # blue info
log.log_success("Success message") # green success
log.log_warn("Warning")            # yellow warning
log.log_error("Error message")     # red error (stderr)
log.debug_print("Debug only")      # only when log.DEBUG is True
```

### GTK4 Callbacks

Unused GTK signal parameters are named `_widget` (never `widget`).

### Subprocess

Never use `subprocess.call()` from a GUI callback — always `Popen` in a daemon
thread. `fisher` installs are network calls: every one is fallible (show state →
attempt → report), per-user, and must never block the UI thread.

### Markup

Ampersands in `set_markup()` must be escaped as `&amp;` or the label renders empty.

### Dev Mode

`--dev` sets `log.DEV = True`; `--debug` sets `log.DEBUG = True`. Never mention
`--dev` in UI text or logs — hidden means hidden.

### Code Style

- `ruff check` must pass before any Python work is considered done; auto-fix
  without asking.
- Max line length: 120.
- `snake_case` for variables/functions, `PascalCase` for classes.
- One-line docstrings on public functions/methods (PEP 257); private
  (`_`-prefixed) functions don't require them.
- Section dividers (`# ── Name ──────`) only in functions 50+ lines.
- No numbered widget names (`hbox1`, `vbox2`) — use descriptive names.

## Frozen Files

- `usr/bin/fish-tweak-tool` — never edit without an explicit file-specific
  instruction. No refactoring, no template passes, no cleanup.

## Running the Application

```bash
python3 usr/share/fish-tweak-tool/fish-tweak-tool.py        # direct (no sudo)
fish-tweak-tool                                             # via launcher
python3 usr/share/fish-tweak-tool/fish-tweak-tool.py --debug
```

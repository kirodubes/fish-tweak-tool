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
├── ftt_gui.py           # GUI: six-tab Notebook (Presets · Plugins · Prompt · Themes · Abbreviations · Settings)
├── ftt_presets.py       # M4 presets: one-click bundles (prompt + plugins + theme + greeting)
├── ftt_fisher.py        # M1 orchestration: fisher install/remove + snapshot
├── ftt_prompt.py        # M1 prompt selection: one set_prompt_async (default/built-in/framework)
├── ftt_theme.py         # M2 theme gallery: list/parse .theme + theme save
├── ftt_managed.py       # M3/M6 managed block: greeting + abbreviations in config.fish
├── ftt_config.py        # App preferences (window size, current_theme, greeting, abbreviations)
├── log.py               # Logging: log_section / log_info / log_success / ...
└── ftt.css              # GTK4 stylesheet
```

`ftt_fisher.py` is deliberately toolkit-free (no GTK import) so it stays unit-
testable. `fisher` is a fish *function*, so every call shells out via
`fish -c`. Mutating calls run in a daemon thread and hand back a
`Result(ok, message, backup)` — they never raise into the UI. `fisher list`
lowercases plugin names, so install-state matching is case-insensitive.

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
- **The managed block is regenerated whole, from one settings dict.** Multiple
  features share it (greeting, abbreviations). `ftt_managed.render_block` rebuilds
  the entire block each apply, so any tab that applies **must** pass the *complete*
  dict via `ftt_managed.settings_from_prefs(prefs)` — passing a partial dict (just
  `{greeting}`) wipes the other sections. Tabs read-modify-write `prefs.json` from
  disk at apply time (not a startup cache) so concurrent sections don't clobber.

## Roadmap (milestones)

- **M0** — Scaffold (done): GTK4 skeleton, launcher, desktop entry.
- **M1** — Prompt & plugin orchestration via `fisher` (the reason-to-exist).
  Plugins tab **done**; Prompt tab **done** — a mutually-exclusive radio group
  (Built-in / Tide / Hydro / Pure / **Starship**), applying one removes the others
  (fish has a single prompt slot). Starship is not a fisher plugin: it's a pacman
  `extra` binary, installed via the visible-terminal offer and enabled with
  `starship init fish | source` in the managed block (the `starship` flag in
  `settings_from_prefs`/`render_block`); the apply path uses `ftt_prompt.build_command`
  to coordinate the block write with the prompt-switch command. The block below the radios is an interchangeable `Gtk.Stack`:
  **Built-in** → a **card gallery** of fish styles with live colour samples
  rendered from `fish_config prompt show` (ANSI → Pango via `_ansi_to_markup`);
  each framework → its own info panel. No standalone "Default" radio — the
  gallery's `default` card is fish's plain prompt (applied via the `("default",)`
  reset). Starship deferred to presets.
- **M2** — Theme gallery from `fish_config theme`. **Done** (card gallery,
  swatches, apply, current indicator, reset).
- **M3** — Greeting + backup-restore of `~/.config/fish/`. **Done**
  (managed-block greeting, backup/restore panel). Cursor shape was dropped — it's
  the terminal's job (Alacritty), and fish only honours `fish_cursor_*` in vi mode.
  Custom greeting can render as **figlet/toilet/cowsay/botsay ASCII art** (tool +
  font/variant dropdowns; `render_block` emits the tool command with an `echo`
  fallback). If the chosen tool isn't installed, Apply offers to install its pacman
  package via a **visible terminal** (`sudo pacman -S --needed <pkg>` — the user
  authenticates there; the app never escalates silently, consistent with the
  no-root-escalation rule). Settings also has an **"Open Fastfetch Tweak Tool"**
  launch button.
- **M4** — Presets (one-click bundles). **Done** — Presets tab (Kiro / Minimal /
  Full); `ftt_presets.apply_preset_async` runs the whole bundle in one visible
  command, persists components to prefs, and writes the full managed block (never
  a partial dict — that would wipe abbreviations). The tab also carries a read-only
  **Current setup** overview (prompt/theme/plugins/greeting/abbreviations + a
  matches-preset-or-Custom badge), computed live and refreshed on tab show.
- **M5** — nemesis_repo package + ATT deep-link. **Done** — package recipe live
  (alacritty optdepend); ATT Shells → Fish has a Fish-Tweak-Tool subsection
  (install / remove / launch). Both packages need rebuilding.
- **M6** — Abbreviations. **Done** — Abbreviations tab (before Settings): a
  `jhillyerd/plugin-git` fisher toggle for git abbreviations on top, and a custom
  add/edit/delete editor below that writes `abbr -a -- name 'expansion'` to the
  managed block. We orchestrate the git plugin rather than bake in a set (three
  overlapping plugins, conflicting meanings). Editor warns (via `abbr --show`) when
  a name overrides an existing one; never imports. The unique capability fish/`fish_config`
  don't offer. Deferred from here: branded `kiro-fish-themes`, Base16/Bobthefish
  escape hatch, VTE live-preview pane.

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

### No black box — mutations run visibly

Any command that *changes the user's system* (install/remove/apply) must run in a
**visible terminal** (Alacritty) that prints the exact command first — never a
hidden subprocess. This is `ftt_fisher.run_async` → `_run_visibly`; all mutating
paths funnel through it. Read-only queries use `run_fish` and stay silent. When
adding a new mutating action, route it through `run_async`, don't shell out
silently.

### Markup

Ampersands in `set_markup()` must be escaped as `&amp;` or the label renders empty.

### fish_config save is interactive

`fish_config prompt save` and `fish_config theme save` both gate on an
interactive `read "Overwrite? [y/N]"`. Run non-interactively via `fish -c` they
get EOF and abort with "Not overwriting". Always pipe `y`:
`echo y | fish_config theme save <name>`.

### Verifying the GUI

Render-test with a throwaway `NON_UNIQUE` app id, never the real
`com.kiro.fish-tweak-tool` (single-instance: a remote launch won't activate).
**Never `pkill` to clear leftovers — it kills the user's own running instance.**

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

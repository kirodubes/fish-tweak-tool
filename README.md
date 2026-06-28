<p align="center">
  <img src="kiro.jpg" alt="Kiro" width="220" />
</p>

# Fish Tweak Tool

A GTK4 graphical configurator for the [fish shell](https://fishshell.com/).

Fish already ships a theme picker (`fish_config`). What it *can't* do is install
prompts and plugins for you, or give you a GUI for abbreviations. Fish Tweak Tool
fills those gaps: install a modern prompt (Tide, Starship, Hydro, Pure), toggle
the consensus must-have plugins via `fisher`, browse colour themes, manage your
own abbreviations, and tune the greeting — all from one desktop app, no browser,
no sudo.

## Features

The app is organised into six tabs:

- **Presets** — a **Current setup** overview of what's configured right now
  (prompt, theme, plugins, greeting, abbreviations) plus one-click bundles that
  set prompt + plugins + theme + greeting together (Kiro / Minimal / Full).
- **Plugins** — toggle `fisher` plugins: `fzf.fish`, `autopair.fish`, `sponge`,
  `puffer-fish`.
- **Prompt** — pick a zero-dependency fish built-in style from a card gallery with
  live colour samples, or install a framework (Tide, Hydro, Pure); the panel below
  the radios swaps to match the selected option.
- **Themes** — browse and apply colour themes from `fish_config theme`.
- **Abbreviations** — install a curated git-abbreviation set
  (`jhillyerd/plugin-git`) via fisher, and add/edit/delete your own abbreviations
  (the one thing `fish_config` can't do). Warns when a name would override an
  existing one.
- **Settings** — greeting (off / custom / fastfetch; custom text can render as
  figlet/toilet ASCII art), a shortcut to open Fastfetch Tweak Tool, and backup /
  restore of `~/.config/fish/`.

Fish Tweak Tool only ever writes *per-user* overrides (below the `source` line in
`~/.config/fish/config.fish`) and uses fish's own `fish_config theme save` /
`prompt save` for theme and prompt — so a `kiro-fish-config` package can own the
shipped defaults without the two layers ever fighting.

## Roadmap

| Milestone | Scope |
|-----------|-------|
| **M0**    | Scaffold — GTK4 skeleton, launcher, desktop entry. *(done)* |
| **M1**    | Prompt & plugin orchestration (the reason-to-exist). *(done)* |
| **M2**    | Theme gallery. *(done)* |
| **M3**    | Greeting + backup-restore. *(done)* |
| **M4**    | Presets — one-click "Kiro" / "Minimal" / "Full" bundles. *(done)* |
| **M5**    | Package for nemesis_repo; ATT Shells → Fish deep-links here. *(done)* |
| **M6**    | Abbreviations — git-abbr plugin toggle + custom editor. *(done)* |

## Installation

Add the nemesis_repo to `/etc/pacman.conf`:

```ini
[nemesis_repo]
SigLevel = Never
Server = https://erikdubois.github.io/$repo/$arch
```

Then install:

```bash
sudo pacman -S fish-tweak-tool
```

## Requirements

- `fish` (≥ 3.4) — the shell being configured
- `fisher` — plugin / prompt installer (used by the Plugins, Prompt and Abbreviations tabs)
- GTK4 + PyGObject (`python-gobject`)
- `starship` (optional) — offered as a prompt option
- `fastfetch` (optional) — offered as a greeting option

## Running

```bash
# Via launcher (after installation)
fish-tweak-tool

# Directly from the source tree
python3 usr/share/fish-tweak-tool/fish-tweak-tool.py

# With debug output
python3 usr/share/fish-tweak-tool/fish-tweak-tool.py --debug
```

No sudo required — runs as the current user.

## License

GPL-3.0 — see [LICENSE](LICENSE)

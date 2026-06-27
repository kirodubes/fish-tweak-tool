<p align="center">
  <img src="kiro.jpg" alt="Kiro" width="220" />
</p>

# Fish Tweak Tool

A GTK4 graphical configurator for the [fish shell](https://fishshell.com/).

Fish already ships a theme picker (`fish_config`). What it *can't* do is install
prompts and plugins for you. Fish Tweak Tool fills that gap: install a modern
prompt (Tide, Starship, Hydro, Pure), toggle the consensus must-have plugins via
`fisher`, browse colour themes, and tune the greeting and cursor — all from one
desktop app, no browser, no sudo.

> **Status:** M0 scaffold — the app launches an empty tabbed shell. Functionality
> lands milestone by milestone (see [Roadmap](#roadmap)).

## Features

The app is organised into four tabs, each filled by a milestone:

- **Prompt** — install/enable a prompt framework (Tide, Starship, Hydro, Pure) or
  pick a zero-dependency built-in style via `fish_config prompt`.
- **Plugins** — toggle `fisher` plugins: `fzf.fish`, `autopair.fish`, `sponge`,
  `puffer-fish`.
- **Themes** — browse and apply colour themes from `fish_config theme`.
- **Settings** — greeting (off / custom / fastfetch), cursor shape, and
  backup / restore of `~/.config/fish/`.

Fish Tweak Tool only ever writes *per-user* overrides (below the `source` line in
`~/.config/fish/config.fish`) and uses fish's own `fish_config theme save` /
`prompt save` for theme and prompt — so a `kiro-fish-config` package can own the
shipped defaults without the two layers ever fighting.

## Roadmap

| Milestone | Scope |
|-----------|-------|
| **M0**    | Scaffold — GTK4 skeleton, launcher, desktop entry. *(done)* |
| **M1**    | Prompt & plugin orchestration (the reason-to-exist). |
| **M2**    | Theme gallery. |
| **M3**    | Greeting / cursor knobs + backup-restore. |
| **M4**    | Presets — one-click "Kiro default" / "Minimal" / "Tide" bundles. |
| **M5**    | Package for nemesis_repo; ATT Shells → Fish deep-links here. |

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
- `fisher` — plugin / prompt installer (used by the Prompt and Plugins tabs)
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

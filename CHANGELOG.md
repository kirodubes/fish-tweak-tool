# Changelog

All notable changes to Fish Tweak Tool are documented here. Newest first.

## 2026.06.27

### What Changed

- **M0 scaffold.** Stood up the standalone GTK4 / PyGObject application: it
  launches a tabbed shell (Plugins · Prompt · Themes · Settings) ready for the
  M1–M4 milestones to fill in.
- **M1 (plugins half).** The Plugins tab is now live: toggle the consensus
  fisher plugins (`fzf.fish`, `autopair.fish`, `sponge`, `puffer-fish`) on/off.
  This is the tool's reason-to-exist — orchestration `fish_config` can't do.
  Adopted the design study's leanings: snapshot `~/.config/fish/` before the
  first change (D9) and treat every fisher call as fallible and per-user (D10).

### Technical Details

- Mirrors the alacritty-tweak-tool layout: `usr/bin/` launcher, `usr/share/`
  Python, `usr/share/applications/` desktop entry.
- App modules are prefixed `ftt_` to avoid colliding with fish's real
  `fish_config` / `fish_prompt` / `fish_theme` commands. Entry point keeps the
  hyphenated `fish-tweak-tool.py` name (executed, never imported).
- `fish-tweak-tool.py` — `Gtk.Application` (id `com.kiro.fish-tweak-tool`),
  headerbar, CSS load, UTF-8 re-exec guard, window-size persistence.
- `ftt_gui.py` — builds the four-tab `Gtk.Notebook` with "Coming soon"
  placeholder pages.
- `ftt_config.py` — app preferences only (`~/.config/fish-tweak-tool/prefs.json`);
  deliberately does **not** write to `~/.config/fish/` (that arrives with M1+).
- `log.py` — colored console logging (shared pattern across Kiro tools).
- Launcher checks for `python3` and `fish`; drops alacritty's `tomlkit` check
  (fish config is plain fish, not TOML).
- Desktop entry uses `Icon=fish` as a placeholder — final icon is an open
  decision.
- **M1 internals:** new `ftt_fisher.py` wraps fisher (a fish *function*, so all
  calls shell out via `fish -c`). Mutating calls run in a daemon thread and
  report a `Result(ok, message, backup)` — never raising into the UI. Output is
  ANSI-stripped and condensed to the last line for the status display. Plugin
  state matching is case-insensitive because `fisher list` lowercases names
  (`PatrickF1/fzf.fish` → `patrickf1/fzf.fish`). Switches use a `busy` guard so
  programmatic state syncs don't trigger install/remove. Snapshot fires once per
  session, before the first mutation, into `~/.config/fish-tweak-tool/backups/`.

### Files Modified

- `README.md`, `CHANGELOG.md`, `CLAUDE.md` (new)
- `usr/bin/fish-tweak-tool` (new)
- `usr/share/applications/fish-tweak-tool.desktop` (new)
- `usr/share/fish-tweak-tool/fish-tweak-tool.py` (new)
- `usr/share/fish-tweak-tool/ftt_gui.py` (new; Plugins tab added for M1)
- `usr/share/fish-tweak-tool/ftt_fisher.py` (new; M1 orchestration core)
- `usr/share/fish-tweak-tool/ftt_config.py` (new)
- `usr/share/fish-tweak-tool/log.py` (new)
- `usr/share/fish-tweak-tool/ftt.css` (new; plugin row + status styles)
- `.vscode/settings.json` (new)

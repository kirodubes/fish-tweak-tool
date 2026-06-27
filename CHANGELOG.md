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
- **M1 (prompt half).** The Prompt tab is now live: install/remove prompt
  frameworks **Tide / Hydro / Pure** via fisher, plus a picker for fish's ~13
  built-in prompt styles (`fish_config prompt save`). **Starship is deferred** —
  enabling it needs a managed-block line in `config.fish`, which arrives with
  presets (M4); the tab flags this.
- **M2 (theme gallery).** The Themes tab is now live: a card gallery of fish's
  25 bundled colour themes, each with a parsed swatch (background + foreground
  bars), click-to-apply (`fish_config theme save`), a current-theme indicator,
  and a **Reset to default** button.

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
- **M1 prompt internals:** refactored `ftt_fisher.py` to expose shared
  primitives (`run_fish`, `run_async`, `ensure_snapshot`) and made the snapshot
  fire **once per process** (so plugin + prompt actions share one backup). New
  `ftt_prompt.py` wraps `fish_config prompt`. The built-in `save` is
  interactive (`read` "Overwrite? [y/N]"); run via `fish -c` it gets EOF and
  refuses with "Not overwriting", so the apply pipes `y`:
  `echo y | fish_config prompt save <name>`. `ftt_gui.py` gained a `_FisherTab`
  base class shared by the Plugins and Prompt tabs; Tide's install spec
  (`IlanCosman/tide@v6`) differs from its fisher-list key (`ilancosman/tide`),
  handled via a per-tab `_install_spec` override.
- **M2 internals:** new `ftt_theme.py` lists themes, locates each `.theme` file
  (`/usr/share/fish/themes/`, user dir wins), and parses `# preferred_background`
  + `fish_color_*` hex values for the swatch. `theme save` is interactive too, so
  the apply pipes `y`: `echo y | fish_config theme save <name>`. fish doesn't
  track the active theme by name, so FTT records the last theme it applied in
  `prefs.json` (`current_theme`) and marks that card. Swatches are Cairo
  `DrawingArea`s. **Test note:** render verification uses a throwaway
  `NON_UNIQUE` app id — never `pkill` the user's running instance.

### Files Modified

- `README.md`, `CHANGELOG.md`, `CLAUDE.md` (new)
- `usr/bin/fish-tweak-tool` (new)
- `usr/share/applications/fish-tweak-tool.desktop` (new)
- `usr/share/fish-tweak-tool/fish-tweak-tool.py` (new)
- `usr/share/fish-tweak-tool/ftt_gui.py` (new; Plugins + Prompt tabs for M1)
- `usr/share/fish-tweak-tool/ftt_fisher.py` (new; M1 orchestration core)
- `usr/share/fish-tweak-tool/ftt_prompt.py` (new; built-in prompt wrapper)
- `usr/share/fish-tweak-tool/ftt_theme.py` (new; M2 theme gallery backend)
- `usr/share/fish-tweak-tool/ftt_config.py` (new)
- `usr/share/fish-tweak-tool/log.py` (new)
- `usr/share/fish-tweak-tool/ftt.css` (new; plugin row + status styles)
- `.vscode/settings.json` (new)

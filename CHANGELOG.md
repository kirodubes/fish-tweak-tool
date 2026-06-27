# Changelog

All notable changes to Fish Tweak Tool are documented here. Newest first.

## 2026.06.27

### What Changed

- **Header bar with version · ♥ Support · Quit** (matches fastfetch-tweak-tool).
  Moved the title into a content header above the tabs: "Fish Tweak Tool" on the
  left, then a `fish v<version>` label, a pink **♥ Support** button (opens a
  Support-Kiro dialog with the funding channels — GitHub Sponsors / Ko-fi /
  Patreon / YouTube / PayPal), and a **Quit** button. The window titlebar is now a
  plain `Gtk.HeaderBar` showing the window title + controls.

- **M5 — Package + ATT integration.** Added `alacritty` as an optdepend on the
  package (`alacritty: shows the exact command for each change in a terminal`),
  since the visible-command UX runs in Alacritty (graceful fallback otherwise).
  Implemented the **ATT deep-link**: ArchLinux Tweak Tool's Shells → Fish section
  now has a "Fish Tweak Tool" subsection (install / remove / **Launch** + status),
  mirroring its alacritty-tweak-tool integration. Launch runs `fish-tweak-tool`
  as the real user (ATT runs as root). Edits live in the ATT repo
  (`shell.py`, `shell_gui.py`) — **archlinux-tweak-tool-gtk4 must be rebuilt** too.

- **M4 — Presets (one-click shell looks).** New **Presets** tab (now the first
  tab) with three bundles — **Kiro** (Tide · Nord · fzf+autopair+sponge ·
  fastfetch), **Minimal** (Pure · default theme · autopair · no greeting), **Full**
  (Tide · Dracula · all four plugins · fastfetch). Applying one (after a confirm)
  snapshots the config, writes greeting+cursor into the managed block, then runs
  ONE visible command that installs the plugins, sets the prompt (removing any
  other framework first) and applies the theme. New `ftt_presets.py`
  (`PRESETS` + `apply_preset_async`); `ftt_fisher._run_visibly` made public as
  `run_visibly`; `ftt_prompt`'s prompt-file list made public. Preset contents are
  plain data — easy to tune.

- **Prompt tab redesigned as a mutually-exclusive radio group.** fish has a
  single prompt slot, so the Prompt tab is now one "choose your prompt" group:
  **Default** (fish's built-in), the three **frameworks** (Tide/Hydro/Pure), and
  **Built-in style** (dropdown), with an **Apply prompt** button. Applying any
  option runs one visible command that **removes every other installed framework,
  clears the prompt function files, then sets the chosen prompt** — so the
  selection honestly reflects the one active prompt (no more multiple toggles ON
  while only the last is active). The selection is restored from `prefs.json`
  (`current_prompt` / `current_builtin`).
  - This consolidates and replaces the earlier switch-based toggles, the separate
    "Reset to default" button (now the **Default** option), the install-conflict
    pre-flight (now inherent — others are always cleared first), and the
    one-prompt-at-a-time notice (now structural). `ftt_prompt`'s three functions
    collapse into one `set_prompt_async`; `run_async` gained callable-command
    support so the removal list can be built from a live `fisher list`.
  - **Tide tag handling:** Tide installs as `IlanCosman/tide@v6` and fisher lists
    *and removes* it by that exact tagged name, so framework matching compares the
    base (before `@`) but removes the exact installed name.
- **Prompt info panel.** Selecting a prompt option shows a details + first-steps
  panel below (Tide → run `tide configure`; Hydro/Pure → the `hydro_*`/`pure_*`
  variables; Default/Built-in → what they do), filling the previously empty space.

- **No black box — mutating commands run visibly in Alacritty.** Every change to
  the system (fisher install/remove, theme save, prompt save) now opens a
  terminal that prints the exact command before running it and shows live
  output; the user presses enter to close. Read-only queries (listing installed
  plugins/themes) stay silent. Falls back to a silent in-process run only when no
  terminal is found. The UI still gets success/failure via a status file.
- **Status line uses ATT orange (`#ffa500`).** Success/info messages now match
  the ArchLinux Tweak Tool accent; errors stay red. Status text **auto-clears
  after 10 s** (a new message resets the timer). Centralised the four tabs' three
  duplicate `_set_status` methods into one `_StatusMixin` carrying the colour +
  timer.


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
- **M3 (settings + backup/restore).** The Settings tab is now live: greeting
  (keep / off / fastfetch / custom text), cursor shape (block / line /
  underscore), and a backup/restore panel (back up now, restore any snapshot).
  Greeting + cursor are written into FTT's **managed block** in `config.fish`,
  below the `source` line, so they load last and always win the load-order rule.

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
- **M2 fix:** color-theme-aware themes (catppuccin/ayu/solarized/… — those with
  `[dark]`/`[light]` sections) failed with "$fish_terminal_color_theme not yet
  initialized" because `fish -c` can't read the terminal's light/dark. Now
  `apply_async` detects awareness from the `.theme` file and adds
  `--color-theme=dark` only for those (passing it to a non-aware theme errors).
  Also bumped the status-line font (12→14px) for readability. Added a
  **Dark / Light variant selector** to the Themes tab header (persisted as
  `theme_variant`) so aware themes can be applied in either variant. Swatches
  are now **variant-aware**: `parse_theme` reads colours from the matching
  `[light]`/`[dark]` section, and switching the dropdown live-redraws every
  card (aware themes flip palettes, non-aware stay put). Swatch DrawingAreas
  gained an `update(bg, colors)` + `queue_draw` path for the live recolour.
- **M2 hover preview.** Hovering a theme card now shows a `fish_config theme
  show`-style sample — a colored code line + error/autosuggestion line in the
  theme's actual colors — rendered as a custom-widget tooltip via Pango markup
  (no subprocess, no VTE). It honours the dark/light variant and works for any
  `.theme` file, so third-party themes dropped in the theme dirs get it for free.
- **M2 parser hardening (for third-party themes).** `parse_theme` now returns a
  full `{fish_color_key: hex}` dict and resolves **named ANSI colors**
  (`red`, `brblue`, …) via a 16-color map, **drops flag-only values**
  (`--reset`, `--reverse`, `--bold`), and **strips quotes** around values
  (`'888'`). Previously hex-only, so named/quoted themes rendered incompletely.
- **M3 internals:** new `ftt_managed.py` owns the managed block — a marker-
  delimited region (`# >>> fish-tweak-tool managed block >>>` … `<<<`) that is
  fully regenerated from a settings dict and inserted/replaced idempotently
  (one block no matter how many applies). prefs.json holds the UI state
  (`greeting`, `cursor`); the block is the source of truth for fish. Greeting is
  always emitted as a `function fish_greeting` (overrides the payload's, which a
  `set -U` could not); custom text is fish single-quote escaped. `ftt_fisher.py`
  gained `snapshot_now` / `list_backups` / `restore_backup`; restore snapshots
  the current config first. Removed the now-unused `_placeholder` helper (all
  four tabs are real).

### Files Modified

- `README.md`, `CHANGELOG.md`, `CLAUDE.md` (new)
- `usr/bin/fish-tweak-tool` (new)
- `usr/share/applications/fish-tweak-tool.desktop` (new)
- `usr/share/fish-tweak-tool/fish-tweak-tool.py` (new)
- `usr/share/fish-tweak-tool/ftt_gui.py` (new; Plugins + Prompt tabs for M1)
- `usr/share/fish-tweak-tool/ftt_fisher.py` (new; M1 orchestration core)
- `usr/share/fish-tweak-tool/ftt_prompt.py` (new; built-in prompt wrapper)
- `usr/share/fish-tweak-tool/ftt_theme.py` (new; M2 theme gallery backend)
- `usr/share/fish-tweak-tool/ftt_managed.py` (new; M3 managed-block writer)
- `usr/share/fish-tweak-tool/ftt_config.py` (new)
- `usr/share/fish-tweak-tool/log.py` (new)
- `usr/share/fish-tweak-tool/ftt.css` (new; plugin row + status styles)
- `.vscode/settings.json` (new)

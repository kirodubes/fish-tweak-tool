# Changelog

All notable changes to Fish Tweak Tool are documented here. Newest first.

## 2026.06.29

### What Changed

- **New dedicated "Palettes" tab** (between Themes and Abbreviations) reaching 500+
  palettes from [tinted-theming](https://github.com/tinted-theming/tinty) — the maintained
  successor to the now-archived `base16-fish-shell` (archived Apr 2025). The native
  `fish_config theme` gallery on the Themes tab is untouched. It's a full-height searchable
  list (`Gtk.SearchEntry`) with **system** (base16/base24/tinted8) and **variant** (dark/light)
  filters; each row shows a colour swatch strip, the scheme name, and its system·variant.
  Click a scheme to apply it. (Started as a cramped section under the Themes gallery; promoted
  to its own tab so it has room.)
- **Install / sync / remove tinty from the tab.** When tinty isn't installed the tab shows an
  **Install tinty** button (`sudo pacman -S --needed tinty-git` in a visible terminal); when
  it is, a **Remove tinty** button sits in the header. Each action rebuilds the tab when it
  finishes (install ↔ download-palettes ↔ gallery).
- **Handle a fresh tinty (schemes not downloaded yet).** A freshly-installed tinty has no
  schemes cloned, so `tinty list` errors with *"Schemes are missing, run install"* and the tab
  was blank. The tab now detects this and shows a **Download palettes** button that runs
  `tinty install` (clones tinted-shell + the schemes repo) in a visible terminal, then rebuilds
  into the gallery. The **Install tinty** button chains straight into this download, so a fresh
  box goes from nothing to a working gallery in one flow. (The earlier "run as normal user"
  note was misdiagnosed — the real cause is un-synced schemes, not sudo, though sudo also lands
  here via root's empty data dir.)
- **tinted8 swatches fixed (were black).** tinted8 schemes have no `base00`/`base0x` keys —
  they use named keys (`red-normal`, `blue-normal`, …), so the base16 swatch logic found no
  colours. `swatch_colors` now branches: base16/base24 use `base08`–`base0E`, tinted8 uses the
  named accents (and `black-dim` for the background).
- **Presets "Current setup" overview gained a Palette row** showing the live `tinty current`
  (the fish theme and the terminal palette are now both visible there).
- **Selecting an ASCII-art tool now switches the greeting to "Custom text".** Picking a tool
  (figlet/toilet/cowsay/botsay) from the dropdown while the mode was still "Keep current" meant
  Apply ignored the art entirely (`mode \!= custom`) and never checked the tool was installed.
  The dropdown now auto-selects the **Custom text** radio, so the art renders and the
  install-check fires.
- **Bigger, 2-column built-in prompt cards.** The Prompt tab's built-in style gallery went
  from up to 4 cramped columns (preview ellipsized at 28 chars) to **2 wider, taller cards**
  (70px min height, preview up to 44 chars), so much more of each prompt sample is readable.

- **It recolours the terminal's ANSI palette, re-applied in every new shell.** FIT writes
  tinty's `~/.config/tinted-theming/tinty/config.toml` (preserving any existing user items)
  using tinty's **official shell setup** — the POSIX **`scripts`** dir with `hook = ". %f"`.
  Those scripts emit only the terminal's 16-colour ANSI palette + background (OSC escape
  codes), which recolours everything in the terminal (ls, git, vim …). It's a layer that
  sits on top of, and independent of, fish's own `fish_color_*` syntax theme (the native
  gallery) — no shared state, no conflict. Apply runs `tinty install` (idempotent) +
  `tinty apply <id>` in a **visible terminal** (no black box). The section carries a live
  "current" indicator from `tinty current`.

- **Persistence via a safe `tinty init` line in the managed block.** Applying a scheme sets a
  `tinty` flag in prefs (read-modify-write, then the whole block is rewritten — never a partial
  dict that would wipe greeting/abbreviations), which emits `type -q tinty; and tinty init`
  into config.fish so the palette re-applies on each new shell. This is safe **only** with the
  `scripts` hook (`. %f` runs under `sh`). **Hard-won lesson:** an earlier attempt used the
  `fish` themes-dir (`hook = "fish %f"`, which also set `fish_color_*` universals) — but tinty's
  `fish %f` hook spawns a fish that *re-sources config.fish*, so `tinty init` there recurses and
  **deadlocks** on fish's universal-variable lock (`futex_wait`), hanging every new shell and
  Alacritty. Verified in a clean room that the `scripts` setup does not deadlock and that a new
  terminal picks up the palette. Also: the app must run as the normal user — under `sudo` tinty
  reads root's empty data dir, so the list shows an explanatory note instead of 500 palettes.

### Technical Details

- New module `ftt_tinty.py` (toolkit-free, like `ftt_theme.py`): `is_available`,
  `list_schemes` (parses `tinty list --json` once — 520 schemes with full base00–base0F
  palettes — and caches), `swatch_colors`, `current_scheme`, `is_configured`/`ensure_config`
  (merge-safe TOML append), and `setup_and_apply_async` (routes through `ftt_fisher.run_async`).
- `ThemesTab` gained the section + filtering/apply methods, reusing the existing `_rgb`
  swatch-drawing pattern (new compact `_tinty_swatch`) and the shared status line.
- tinty added as an optdepend on the `fish-tweak-tool` package (resolvable from
  nemesis_repo, where `tinty-git` lives).

### Files Modified

- `usr/share/fish-tweak-tool/ftt_tinty.py` (new)
- `usr/share/fish-tweak-tool/ftt_gui.py`
- `usr/share/fish-tweak-tool/ftt_managed.py`
- `CLAUDE.md`
- `../KIRO-PKG-BUILD-APPS/fish-tweak-tool/PKGBUILD` (tinty optdepend)

## 2026.06.28

### What Changed

- **New Abbreviations tab** (placed before Settings, so Settings stays last). Two
  parts. **(1) Git abbreviations** — a one-toggle fisher install of
  `jhillyerd/plugin-git` (the most-used fish git-abbr plugin, 765★ — `gst` →
  `git status`, `gco` → `git checkout`, ~100 more). We orchestrate the plugin
  rather than bake in our own git set: three popular git-abbr plugins exist, they
  overlap on names and even disagree on meaning (`gst` = stash vs status, `gp` =
  push vs pull), so there's no safe single set to copy and no maintenance/licensing
  debt to take on. **(2) A custom abbreviation editor** — add / edit / delete your
  own abbreviations (name + expansion), written to FTT's managed block in
  `config.fish` as `abbr -a -- <name> '<expansion>'`. This is the genuinely-unique
  capability: no GUI (not even `fish_config browse`) lets you manage abbreviations.
  The editor reads `abbr --show` and **warns inline** when a name you add already
  exists elsewhere (e.g. a plugin) and would override it — but never imports or
  re-owns other sources' abbreviations. Names are validated (no spaces, quotes or
  backslashes; no duplicates; both fields required).

- **Fixed a managed-block clobber bug.** `write_block` regenerates the whole block
  from the settings dict it's handed, and each tab cached `prefs` at startup. With
  the new abbreviations sharing the block, a greeting apply that passed only
  `{greeting}` would have wiped every abbreviation (and the stale cache would drop
  them from `prefs.json` too). Both the Settings and Abbreviations tabs now
  **read-modify-write `prefs.json` from disk** at apply time and pass the complete
  block via the new `ftt_managed.settings_from_prefs()`, so the two sections can no
  longer erase each other.

- **Current-setup overview on the Presets tab.** A read-only panel at the top of
  the Presets tab shows what's actually configured right now — prompt, theme,
  installed plugins (live `fisher list`), greeting, and abbreviation count (plus
  whether the git set is on) — with a badge that reads **"✓ matches <preset>"**
  when the live state equals a preset, or **"Custom setup"** otherwise. It reads
  live truth (not a remembered label), so it stays honest even after you change a
  single component, and it refreshes each time the tab is shown. This answers
  "what did I set, again?" a week later at a glance.

- **Presets now persist their state and stop clobbering abbreviations.** Applying
  a preset wrote the managed block from a partial `{greeting}` dict — which, now
  that abbreviations share that block, would have erased them; and presets never
  recorded their prompt/theme in `prefs.json`, so the rest of the app couldn't
  reflect a preset apply. Both fixed: `apply_preset_async` read-modify-writes the
  full block via `settings_from_prefs`, and on success records
  `current_prompt` / `current_builtin` / `current_theme` / `theme_variant` so the
  overview (and other tabs) show reality.

- **Fixed prefs being clobbered on window close (and between tabs).** Each tab and
  the main window cached `prefs.json` at startup and saved that whole snapshot —
  so closing the window wrote the *startup* prefs + window size back over
  everything the tabs had persisted that session (a freshly-applied theme, your
  abbreviations). Symptom: apply the `lava` theme, reopen, and the overview /
  Themes tab still showed `default`. Added `ftt_config.update_prefs(updates)` which
  read-modify-writes from disk, and routed `Main._on_close`, the Themes, Prompt,
  Settings and Abbreviations saves through it. Now applied state actually sticks.

- **Visible border on the current theme card.** `.theme-card` now reserves a 2px
  transparent border so `.theme-current`'s accent border shows clearly (and
  without a layout shift) around the active theme. Previously the card was never
  marked at all because `current_theme` wasn't surviving a restart (see above).

- **Custom greeting can render as ASCII art (figlet / toilet / cowsay / botsay).**
  The Settings → greeting "Custom text" option gained an **ASCII art** row: a tool
  dropdown (None / figlet / toilet / cowsay / botsay) + a font/variant dropdown
  (populated live — figlet `.flf`, toilet `.tlf`, cowsay `.cow` cowfiles; botsay
  has no variant). The managed block renders the text at greeting time via the
  tool's command (`figlet`/`toilet -f <font> -w 1000`, `cowsay -f <cowfile>`,
  `botsay`), falling back to a plain `echo` if the tool isn't installed. A
  **Rainbow colour** switch sits on every tool's row — botsay colours itself
  (`botsay -c`); figlet/toilet/cowsay pipe through **lolcat** (`… | lolcat -f`,
  guarded so it degrades to plain art if lolcat is missing). botsay has no fonts,
  so its row is switch-only,
  (`if type -q <tool>; …; else; echo …; end`). Reuses the font enumeration approach
  from fastfetch-tweak-tool.

- **Custom greeting prefills with "Welcome to KIRO"** on first run (real editable
  text, not just a placeholder), so the field starts with a sensible default.

- **Compose a custom greeting with fastfetch.** A "then show fastfetch below the
  text" checkbox lets a custom (optionally ASCII-art) greeting be followed by
  fastfetch — e.g. a `toilet` banner on top, the fastfetch logo/system info under
  it. `render_block` appends `type -q fastfetch; and fastfetch` after the text part
  (greeting dict gains `with_fastfetch`).

- **Apply offers to install missing greeting packages.** If you apply a custom
  greeting whose tool (figlet/toilet/cowsay/botsay) — or `lolcat`, when Rainbow is
  on for a font tool — isn't installed, a dialog offers to install the missing
  package(s) in one go via `sudo pacman -S --needed <pkgs>` in a **visible
  terminal** (you authenticate there — the app never escalates silently), then
  continues the apply.

- **"Open Fastfetch Tweak Tool" button** on the Settings tab (top-right of the
  greeting header) — launches `fastfetch-tweak-tool` (Popen in a daemon thread);
  disabled with a hint when it isn't installed. Pairs with the fastfetch greeting.

- **Starship prompt support.** Added a fifth Prompt radio — **Starship**. Unlike
  Tide/Hydro/Pure (fisher plugins), Starship is a pacman `extra` binary, so it has
  its own path: Apply offers to install the `starship` package via the visible
  terminal, then enables it with `starship init fish | source` written to the
  **managed block** (a new `starship` flag in `settings_from_prefs`/`render_block`,
  guarded by `type -q starship`). Switching to any other prompt clears that line.
  Its info panel links to <https://github.com/starship/starship> — and the
  Tide/Hydro/Pure panels now carry a github.com link to their repo too (derived
  from each framework's key). The Starship panel also has a **preset gallery** —
  cards each showing a **live colour-rendered preview** of that preset's prompt
  (`STARSHIP_CONFIG=<preset> starship prompt`, ANSI → Pango), click a card to apply.
  Presets are **Kiro default** (the `kiro-starship` package's
  `/usr/share/kiro/starship/starship.toml` payload, when installed) plus Starship's
  own (`starship preset --list`); applying backs up `~/.config/starship.toml` then
  writes the chosen one (`starship preset <name> -o …`, or copies the Kiro default).
  `ftt_prompt`'s command builder was exposed as `build_command` so the apply path
  can coordinate the managed-block write with the prompt-switch command. Removed the
  old "Starship coming" note.

- **ANSI → Pango converter now handles backgrounds + 256-colour.** Extended
  `_ansi_to_markup` (built-in-prompt and starship preview cards) to emit `background`
  spans (`48;2` true-colour, `48;5;N`/`40-47`/`100-107`) and 256-colour foregrounds
  (`38;5;N`), so powerline presets show their segment backgrounds; non-colour
  escapes (cursor/erase) are stripped. Closes the deferred 256-colour/background gap.

- **Prompt tab redesigned around an interchangeable block.** The area below the
  radios now swaps with the selection: **Built-in** shows a **card gallery** of
  fish's bundled styles (each card a **real colour-rendered sample** from
  `fish_config prompt show <name>`, ANSI → Pango, name below); **Tide / Hydro /
  Pure** each show their own dedicated info panel instead. So you only ever see
  the block that matches the chosen option. The separate "Default" radio was
  merged into the gallery — its `default` card *is* fish's plain prompt (applying
  it does a full reset, not a save). Click a card to pick a style (current one gets
  the accent border, only while Built-in is active), then Apply. Samples load off
  the UI thread.

- **Repo links on plugin rows.** Every plugin/toggle row (Plugins tab + the git
  toggle) now shows an italic **link** that opens `github.com/<owner/repo>` in the
  browser, so you can read what a plugin does before enabling it.

- **Git cheat-sheet on the Abbreviations tab.** Below the editor, a read-only
  "Most-used git abbreviations" reference grid lists the 20 everyday ones the
  `plugin-git` toggle installs (`gst` → `git status`, `gco` → `git checkout`, …),
  so you can see what you get without leaving the app.

### Technical Details

- `ftt_config.py`: added `update_prefs(updates)` — the read-modify-write primitive
  that ends the snapshot-clobber bug class.
- `ftt_gui.py`: added an ANSI → Pango converter (`_ansi_to_markup` + helpers) for
  prompt samples; `PromptTab` now builds a `_make_card` gallery and loads samples
  via `fish_config prompt show` in a worker thread.
- `ftt_managed.py`: added `settings_from_prefs(prefs)` (single source for the full
  block dict) and a `_quote()` helper; `render_block` now emits `abbr` lines from
  `settings["abbreviations"]`, reusing the greeting's single-quote escaping, and a
  figlet/toilet custom-greeting branch (greeting dict gains `tool` + `font`).
- `ftt_gui.py`: `SettingsTab` gained `_figlet_fonts`/`_toilet_fonts`/`_greeting_fonts`,
  the ASCII-art tool/font dropdowns (`_refresh_fonts`), and `_open_fastfetch_tool`.
- `ftt_presets.py`: added `preset_prompt_rid()` + `_persist_prefs()`;
  `apply_preset_async` merges the full block and persists components on success.
- `ftt_gui.py`: `PresetsTab` gained the overview panel (`_build_overview` /
  `_refresh_overview` / `_fill_overview`) plus the `_prompt_label`,
  `_consensus_installed`, `_matched_preset` helpers; refreshes on the tab's `map`.
- `ftt_gui.py`: new `_AbbrRow` (name/expansion entries + delete + inline collision
  warning via a secondary entry icon) and `AbbrTab(_FisherTab)` — the git toggle
  reuses `_PluginRow`/`_FisherTab` so install-state detection, snapshot and the
  visible-terminal install path come for free. `abbr --show` is parsed off the UI
  thread; the collision set subtracts FTT's own managed names so applied
  abbreviations don't self-warn. `SettingsTab` apply converted to read-modify-write.
- `prefs.json`: new `abbreviations` key — a list of `{name, expansion}` objects.

### Files Modified

- `usr/share/fish-tweak-tool/fish-tweak-tool.py`
- `usr/share/fish-tweak-tool/ftt_config.py`
- `usr/share/fish-tweak-tool/ftt_managed.py`
- `usr/share/fish-tweak-tool/ftt_gui.py`
- `usr/share/fish-tweak-tool/ftt_presets.py`
- `usr/share/fish-tweak-tool/ftt.css`
- `CLAUDE.md`, `README.md`

## 2026.06.27

### What Changed

- **Removed the Cursor-shape setting** from the Settings tab. Cursor shape is the
  terminal's job (Alacritty's `cursor.style`), not the shell's: fish only honours
  `fish_cursor_*` in **vi mode**, so in the default key bindings the setting did
  nothing (the cursor stayed whatever the terminal was). Dropped the dropdown, the
  `set -g fish_cursor_*` managed-block lines, and `cursor` from the presets. For
  cursor shape, use alacritty-tweak-tool / your terminal config.

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

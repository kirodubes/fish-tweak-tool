"""GTK4 GUI for fish-tweak-tool.

Plugins and Prompt tabs (M1) are live; Themes and Settings remain placeholders
that later milestones fill in. Building the shell up-front means each milestone
drops into a fixed slot with no structural churn.
"""

import os
import threading

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

import ftt_config  # noqa: E402
import ftt_fisher  # noqa: E402
import ftt_managed  # noqa: E402
import ftt_prompt  # noqa: E402
import ftt_theme  # noqa: E402
import log  # noqa: E402

# Cursor shapes offered in the Settings tab.
_CURSOR_SHAPES = ["block", "line", "underscore"]

# The consensus must-have fisher plugins: repo → one-line description.
_PLUGINS = [
    ("PatrickF1/fzf.fish", "Fuzzy search over history, files, git, processes"),
    ("jorgebucaran/autopair.fish", "Auto-closes brackets, quotes and parens"),
    ("meaningful-ooo/sponge", "Drops failed commands from history"),
    ("nickeb96/puffer-fish", "Expands .. and ... as you type"),
]

# Installable prompt frameworks: (display/match key, fisher install spec, description).
# Tide installs from a version tag but fisher lists it as the bare repo, so the
# install spec and the match key differ.
_PROMPT_FRAMEWORKS = [
    ("IlanCosman/tide", "IlanCosman/tide@v6", "Modern async prompt with a setup wizard (tide configure)"),
    ("jorgebucaran/hydro", "jorgebucaran/hydro", "Ultra-minimal async prompt; fast git + duration"),
    ("pure-fish/pure", "pure-fish/pure", "Minimal clean prompt; directory + git branch"),
]


# ── Generic helpers ──────────────────────────────────────────────────────────


def _placeholder(title, description):
    """Return a centered placeholder page for a not-yet-built tab."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    box.set_valign(Gtk.Align.CENTER)
    box.set_halign(Gtk.Align.CENTER)

    heading = Gtk.Label(label=title)
    heading.add_css_class("placeholder-title")

    detail = Gtk.Label(label=description)
    detail.add_css_class("placeholder-detail")
    detail.set_wrap(True)
    detail.set_justify(Gtk.Justification.CENTER)
    detail.set_max_width_chars(48)

    box.append(heading)
    box.append(detail)
    return box


def _notice(title, detail):
    """Return a centered informational page (e.g. a missing dependency)."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    box.set_valign(Gtk.Align.CENTER)
    box.set_halign(Gtk.Align.CENTER)

    heading = Gtk.Label(label=title)
    heading.add_css_class("placeholder-title")

    sub = Gtk.Label(label=detail)
    sub.add_css_class("placeholder-detail")
    sub.set_selectable(True)

    box.append(heading)
    box.append(sub)
    return box


def _section(title):
    """Return a left-aligned section heading label."""
    lbl = Gtk.Label(label=title, xalign=0)
    lbl.add_css_class("section-title")
    return lbl


def _intro(text):
    """Return a left-aligned wrapped intro/description label."""
    lbl = Gtk.Label(label=text, xalign=0)
    lbl.add_css_class("plugin-desc")
    lbl.set_wrap(True)
    return lbl


class _PluginRow:
    """One install target: name, description, busy spinner, install/remove switch."""

    def __init__(self, plugin, description, on_toggle):
        self.plugin = plugin
        self.busy = False
        self._on_toggle = on_toggle

        self.widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.widget.set_margin_top(8)
        self.widget.set_margin_bottom(8)
        self.widget.set_margin_start(6)
        self.widget.set_margin_end(6)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text.set_hexpand(True)
        name = Gtk.Label(label=plugin, xalign=0)
        name.add_css_class("plugin-name")
        desc = Gtk.Label(label=description, xalign=0)
        desc.add_css_class("plugin-desc")
        desc.set_wrap(True)
        text.append(name)
        text.append(desc)

        self.spinner = Gtk.Spinner()
        self.spinner.set_valign(Gtk.Align.CENTER)
        self.spinner.set_visible(False)

        self.switch = Gtk.Switch()
        self.switch.set_valign(Gtk.Align.CENTER)
        self.switch.connect("notify::active", self._switched)

        self.widget.append(text)
        self.widget.append(self.spinner)
        self.widget.append(self.switch)

    def _switched(self, _switch, _param):
        # Programmatic state syncs set self.busy so they don't trigger a toggle.
        if self.busy:
            return
        self._on_toggle(self, self.switch.get_active())

    def set_installed(self, installed):
        """Reflect install state on the switch without firing the toggle handler."""
        self.busy = True
        self.switch.set_active(installed)
        self.busy = False

    def set_loading(self, loading):
        """Show the spinner and lock the switch while an operation runs."""
        self.switch.set_sensitive(not loading)
        self.spinner.set_visible(loading)
        if loading:
            self.spinner.start()
        else:
            self.spinner.stop()


# ── Shared fisher-tab behaviour ──────────────────────────────────────────────


class _FisherTab:
    """Common state/toggle logic for a tab whose rows install/remove via fisher."""

    def __init__(self):
        self._rows = {}
        self._status = None

    def _refresh_states(self):
        def worker():
            installed = ftt_fisher.list_installed()
            GLib.idle_add(self._apply_states, installed)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_states(self, installed):
        installed_lower = {p.lower() for p in installed}
        for key, row in self._rows.items():
            row.set_installed(key.lower() in installed_lower)
        return False

    def _install_spec(self, key):
        """The fisher install argument for a row key (overridden where they differ)."""
        return key

    def _on_toggle(self, row, want_on):
        row.set_loading(True)
        self._set_status("")

        def on_done(result):
            GLib.idle_add(self._toggle_finished, row, want_on, result)

        if want_on:
            ftt_fisher.install_async(self._install_spec(row.plugin), on_done, snapshot=True)
        else:
            ftt_fisher.remove_async(row.plugin, on_done, snapshot=True)

    def _toggle_finished(self, row, want_on, result):
        row.set_loading(False)
        if result.ok:
            row.set_installed(want_on)
            verb = "installed" if want_on else "removed"
            self._set_status(f"{row.plugin} {verb}.")
        else:
            row.set_installed(not want_on)
            detail = result.message or "see terminal for details"
            self._set_status(f"{row.plugin} failed: {detail}", error=True)
        return False

    def _set_status(self, text, error=False):
        self._status.set_text(text)
        if error:
            self._status.add_css_class("status-error")
        else:
            self._status.remove_css_class("status-error")


# ── Plugins tab ──────────────────────────────────────────────────────────────


class PluginsTab(_FisherTab):
    """Plugins tab — toggle the consensus fisher plugins (M1)."""

    def __init__(self):
        super().__init__()
        self.widget = self._build()

    def _build(self):
        if not ftt_fisher.is_fisher_available():
            return _notice("fisher is not available", "Install it with:  sudo pacman -S fisher")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(16)

        box.append(
            _intro(
                "Toggle a plugin to install or remove it with fisher. "
                "Your fish config is backed up before the first change."
            )
        )

        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        listbox.add_css_class("plugin-list")
        for plugin, description in _PLUGINS:
            row = _PluginRow(plugin, description, self._on_toggle)
            self._rows[plugin] = row
            listbox.append(row.widget)
        box.append(listbox)

        self._status = Gtk.Label(label="", xalign=0)
        self._status.add_css_class("status-line")
        self._status.set_wrap(True)
        box.append(self._status)

        self._refresh_states()
        return box


# ── Prompt tab ───────────────────────────────────────────────────────────────


class PromptTab(_FisherTab):
    """Prompt tab — install a prompt framework (fisher) or pick a built-in (M1)."""

    def __init__(self):
        super().__init__()
        self._specs = {}
        self._dropdown = None
        self._apply_btn = None
        self.widget = self._build()

    def _install_spec(self, key):
        return self._specs.get(key, key)

    def _build(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(16)

        self._status = Gtk.Label(label="", xalign=0)
        self._status.add_css_class("status-line")
        self._status.set_wrap(True)

        if ftt_fisher.is_fisher_available():
            box.append(_section("Prompt frameworks"))
            box.append(
                _intro(
                    "Installing a framework activates it. Turn it off to remove it "
                    "and return to your previous prompt."
                )
            )
            listbox = Gtk.ListBox()
            listbox.set_selection_mode(Gtk.SelectionMode.NONE)
            listbox.add_css_class("plugin-list")
            for key, spec, description in _PROMPT_FRAMEWORKS:
                row = _PluginRow(key, description, self._on_toggle)
                self._rows[key] = row
                self._specs[key] = spec
                listbox.append(row.widget)
            box.append(listbox)
        else:
            box.append(_intro("fisher is not available — install it (sudo pacman -S fisher) to add prompt frameworks."))

        box.append(_section("Built-in prompts"))
        box.append(_intro("Zero-dependency prompt styles that ship with fish."))
        box.append(self._build_builtin_picker())

        starship_note = _intro("Starship support is coming with presets.")
        starship_note.add_css_class("muted")
        box.append(starship_note)

        box.append(self._status)

        if self._rows:
            self._refresh_states()

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(box)
        return scroller

    def _build_builtin_picker(self):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        names = ftt_prompt.list_builtin()
        self._apply_btn = Gtk.Button(label="Apply")
        if names:
            self._dropdown = Gtk.DropDown.new_from_strings(names)
            self._dropdown.set_hexpand(True)
            self._apply_btn.connect("clicked", self._apply_builtin)
            row.append(self._dropdown)
            row.append(self._apply_btn)
        else:
            self._apply_btn.set_sensitive(False)
            row.append(_intro("Could not read fish_config prompt list."))
        return row

    def _apply_builtin(self, _btn):
        idx = self._dropdown.get_selected()
        name = self._dropdown.get_model().get_string(idx)
        self._apply_btn.set_sensitive(False)
        self._set_status(f"Applying {name}…")

        def on_done(result):
            GLib.idle_add(self._builtin_finished, name, result)

        ftt_prompt.apply_builtin_async(name, on_done, snapshot=True)

    def _builtin_finished(self, name, result):
        self._apply_btn.set_sensitive(True)
        if result.ok:
            self._set_status(f"Built-in prompt '{name}' applied. Open a new shell to see it.")
        else:
            detail = result.message or "see terminal for details"
            self._set_status(f"Could not apply {name}: {detail}", error=True)
        return False


# ── Themes tab ───────────────────────────────────────────────────────────────


def _rgb(hex_color):
    """Convert '#rrggbb' (or '#rgb') to a (r, g, b) float tuple in 0..1."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))


def _swatch(background, foregrounds, width=190, height=72):
    """Return a DrawingArea previewing a theme: background fill + foreground bars."""
    area = Gtk.DrawingArea()
    area.set_size_request(width, height)

    def draw(_area, cr, w, h, _data=None):
        bg = _rgb(background) if background else (0.12, 0.12, 0.12)
        cr.set_source_rgb(*bg)
        cr.rectangle(0, 0, w, h)
        cr.fill()
        if foregrounds:
            pad = 12
            count = len(foregrounds)
            bar_w = (w - 2 * pad) / count
            for i, color in enumerate(foregrounds):
                cr.set_source_rgb(*_rgb(color))
                cr.rectangle(pad + i * bar_w + 2, h * 0.45, bar_w - 4, h * 0.35)
                cr.fill()

    area.set_draw_func(draw)
    return area


class ThemesTab:
    """Themes tab — gallery of fish_config colour themes with apply (M2)."""

    def __init__(self):
        self._prefs = ftt_config.load_prefs()
        self._current = self._prefs.get("current_theme")
        self._cards = {}
        self._status = None
        self._busy = False
        self.widget = self._build()

    def _build(self):
        themes = ftt_theme.list_themes()
        if not themes:
            return _notice("No themes found", "fish_config theme list returned nothing.")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(16)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.append(_intro("Click a theme to apply it. Open a new shell to see the colours."))
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header.append(spacer)
        reset = Gtk.Button(label="Reset to default")
        reset.connect("clicked", lambda _b: self._apply("default"))
        header.append(reset)
        box.append(header)

        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(4)
        flow.set_column_spacing(10)
        flow.set_row_spacing(10)
        flow.set_homogeneous(True)
        for name in themes:
            card = self._make_card(name)
            self._cards[name] = card
            flow.append(card)
        box.append(flow)

        self._status = Gtk.Label(label="", xalign=0)
        self._status.add_css_class("status-line")
        self._status.set_wrap(True)
        box.append(self._status)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_child(box)
        return scroller

    def _make_card(self, name):
        background, foregrounds = ftt_theme.parse_theme(name)
        button = Gtk.Button()
        button.add_css_class("theme-card")
        if name == self._current:
            button.add_css_class("theme-current")

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        content.append(_swatch(background, foregrounds))
        label = Gtk.Label(label=name)
        label.add_css_class("plugin-name")
        label.set_ellipsize(3)  # Pango.EllipsizeMode.END
        content.append(label)
        button.set_child(content)
        button.connect("clicked", lambda _b, n=name: self._apply(n))
        return button

    def _apply(self, name):
        if self._busy:
            return
        self._busy = True
        self._set_status(f"Applying {name}…")

        def on_done(result):
            GLib.idle_add(self._apply_finished, name, result)

        ftt_theme.apply_async(name, on_done, snapshot=True)

    def _apply_finished(self, name, result):
        self._busy = False
        if result.ok:
            if self._current in self._cards:
                self._cards[self._current].remove_css_class("theme-current")
            if name in self._cards:
                self._cards[name].add_css_class("theme-current")
            self._current = name
            self._prefs["current_theme"] = name
            ftt_config.save_prefs(self._prefs)
            self._set_status(f"Theme '{name}' applied. Open a new shell to see it.")
        else:
            detail = result.message or "see terminal for details"
            self._set_status(f"Could not apply {name}: {detail}", error=True)
        return False

    def _set_status(self, text, error=False):
        self._status.set_text(text)
        if error:
            self._status.add_css_class("status-error")
        else:
            self._status.remove_css_class("status-error")


# ── Settings tab ─────────────────────────────────────────────────────────────


class SettingsTab:
    """Settings tab — greeting, cursor shape, and backup / restore (M3)."""

    def __init__(self):
        self._prefs = ftt_config.load_prefs()
        self._busy = False
        self._status = None
        self._custom_entry = None
        self._cursor_dropdown = None
        self._backup_dropdown = None
        self._greeting_radios = {}
        self.widget = self._build()

    def _build(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(16)

        box.append(_section("Greeting"))
        box.append(self._build_greeting())
        box.append(_section("Cursor"))
        box.append(self._build_cursor())

        apply_btn = Gtk.Button(label="Apply settings")
        apply_btn.add_css_class("suggested-action")
        apply_btn.set_halign(Gtk.Align.START)
        apply_btn.connect("clicked", self._apply_settings)
        box.append(apply_btn)

        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        box.append(_section("Backup & restore"))
        box.append(self._build_backup())

        self._status = Gtk.Label(label="", xalign=0)
        self._status.add_css_class("status-line")
        self._status.set_wrap(True)
        box.append(self._status)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_child(box)
        return scroller

    def _build_greeting(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        saved = self._prefs.get("greeting", {})
        mode = saved.get("mode", "keep")

        first = None
        for key, label in (
            ("keep", "Keep current"),
            ("off", "No greeting"),
            ("fastfetch", "Show fastfetch on launch"),
            ("custom", "Custom text"),
        ):
            radio = Gtk.CheckButton(label=label)
            if first is None:
                first = radio
            else:
                radio.set_group(first)
            radio.set_active(mode == key)
            self._greeting_radios[key] = radio
            box.append(radio)

        self._custom_entry = Gtk.Entry()
        self._custom_entry.set_placeholder_text("Your greeting text")
        self._custom_entry.set_text(saved.get("text", ""))
        box.append(self._custom_entry)
        return box

    def _build_cursor(self):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.append(_intro("Shape:"))
        self._cursor_dropdown = Gtk.DropDown.new_from_strings(_CURSOR_SHAPES)
        saved = self._prefs.get("cursor")
        if saved in _CURSOR_SHAPES:
            self._cursor_dropdown.set_selected(_CURSOR_SHAPES.index(saved))
        row.append(self._cursor_dropdown)
        return row

    def _build_backup(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        backup_now = Gtk.Button(label="Back up now")
        backup_now.set_halign(Gtk.Align.START)
        backup_now.connect("clicked", self._backup_now)
        box.append(backup_now)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._backup_dropdown = Gtk.DropDown.new_from_strings(self._backup_names())
        self._backup_dropdown.set_hexpand(True)
        row.append(self._backup_dropdown)
        restore = Gtk.Button(label="Restore selected")
        restore.connect("clicked", self._restore_selected)
        row.append(restore)
        box.append(row)
        return box

    def _backup_names(self):
        self._backups = ftt_fisher.list_backups()
        return [os.path.basename(p) for p in self._backups] or ["(no backups yet)"]

    # ── actions ───────────────────────────────────────────────────────────
    def _collect_settings(self):
        mode = next((k for k, r in self._greeting_radios.items() if r.get_active()), "keep")
        cursor = _CURSOR_SHAPES[self._cursor_dropdown.get_selected()]
        return {
            "greeting": {"mode": mode, "text": self._custom_entry.get_text()},
            "cursor": cursor,
        }

    def _apply_settings(self, _btn):
        if self._busy:
            return
        self._busy = True
        settings = self._collect_settings()
        self._set_status("Applying settings…")

        def on_done(result):
            GLib.idle_add(self._apply_finished, settings, result)

        ftt_managed.apply_async(settings, on_done)

    def _apply_finished(self, settings, result):
        self._busy = False
        if result.ok:
            self._prefs["greeting"] = settings["greeting"]
            self._prefs["cursor"] = settings["cursor"]
            ftt_config.save_prefs(self._prefs)
            self._refresh_backups()
            self._set_status("Settings applied. Open a new shell to see them.")
        else:
            self._set_status(f"Could not apply settings: {result.message}", error=True)
        return False

    def _backup_now(self, _btn):
        def worker():
            path = ftt_fisher.snapshot_now()
            GLib.idle_add(self._backup_done, path)

        threading.Thread(target=worker, daemon=True).start()

    def _backup_done(self, path):
        self._refresh_backups()
        if path:
            self._set_status(f"Backed up to {os.path.basename(path)}.")
        else:
            self._set_status("Nothing to back up (no fish config found).", error=True)
        return False

    def _restore_selected(self, _btn):
        if not self._backups:
            self._set_status("No backup to restore.", error=True)
            return
        path = self._backups[self._backup_dropdown.get_selected()]
        self._set_status(f"Restoring {os.path.basename(path)}…")

        def worker():
            ftt_fisher.snapshot_now()
            try:
                ftt_fisher.restore_backup(path)
                GLib.idle_add(self._set_status, f"Restored {os.path.basename(path)}. Open a new shell.")
            except OSError as exc:
                GLib.idle_add(self._set_status, f"Restore failed: {exc}", True)

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_backups(self):
        names = self._backup_names()
        self._backup_dropdown.set_model(Gtk.StringList.new(names))

    def _set_status(self, text, error=False):
        self._status.set_text(text)
        if error:
            self._status.add_css_class("status-error")
        else:
            self._status.remove_css_class("status-error")
        return False


# ── Entry point ──────────────────────────────────────────────────────────────


def build(window, fish_version):
    """Populate the window with the tabbed shell."""
    notebook = Gtk.Notebook()
    notebook.set_scrollable(True)

    notebook.append_page(PluginsTab().widget, Gtk.Label(label="Plugins"))
    notebook.append_page(PromptTab().widget, Gtk.Label(label="Prompt"))
    notebook.append_page(ThemesTab().widget, Gtk.Label(label="Themes"))
    notebook.append_page(SettingsTab().widget, Gtk.Label(label="Settings"))

    window.set_child(notebook)
    log.debug_print(f"GUI built (fish {fish_version})")

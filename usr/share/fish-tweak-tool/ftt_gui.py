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

# Light/dark variant for colour-theme-aware themes (Themes tab).
_VARIANTS = ["dark", "light"]

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

# Per-framework detail + first steps, shown in the info panel when a row is selected.
_FRAMEWORK_INFO = {
    "IlanCosman/tide": (
        "<b>Tide</b> — the most configurable modern fish prompt. Async, so it "
        "renders instantly and fills in git status in the background.\n\n"
        "<b>First steps:</b> after installing, run <tt>tide configure</tt> in a "
        "terminal to launch the interactive wizard (style, icons, colours). "
        "Re-run it any time to change the look."
    ),
    "jorgebucaran/hydro": (
        "<b>Hydro</b> — an ultra-minimal async prompt; the fastest of the bunch. "
        "Shows the directory, git branch/status and command duration.\n\n"
        "<b>First steps:</b> zero config needed. Tweak it by setting variables in "
        "your config, e.g. <tt>set hydro_symbol_prompt ❯</tt> or the "
        "<tt>hydro_color_*</tt> colours."
    ),
    "pure-fish/pure": (
        "<b>Pure</b> — a clean, minimal prompt ported from zsh Pure. Shows the "
        "directory and git branch; the <tt>❯</tt> symbol turns red when the last "
        "command failed.\n\n"
        "<b>First steps:</b> works out of the box. Customise via <tt>pure_*</tt> "
        "variables, e.g. <tt>set pure_symbol_prompt ❯</tt>."
    ),
}

_FRAMEWORK_INFO_DEFAULT = "Select a prompt framework above to see details and first steps."


# ── Generic helpers ──────────────────────────────────────────────────────────


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


class _StatusMixin:
    """A status label in ATT-orange that auto-clears 10s after the last message."""

    def _init_status(self):
        self._status = Gtk.Label(label="", xalign=0)
        self._status.add_css_class("status-line")
        self._status.set_wrap(True)
        self._status_timeout = 0
        return self._status

    def _set_status(self, text, error=False):
        self._status.set_text(text)
        if error:
            self._status.add_css_class("status-error")
        else:
            self._status.remove_css_class("status-error")
        if self._status_timeout:
            GLib.source_remove(self._status_timeout)
            self._status_timeout = 0
        if text:
            self._status_timeout = GLib.timeout_add_seconds(10, self._clear_status)
        return False

    def _clear_status(self):
        self._status.set_text("")
        self._status.remove_css_class("status-error")
        self._status_timeout = 0
        return False


class _FisherTab(_StatusMixin):
    """Common state/toggle logic for a tab whose rows install/remove via fisher."""

    def __init__(self):
        self._rows = {}
        self._status = None
        self._status_timeout = 0

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

        box.append(self._init_status())

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
        self._framework_order = []
        self._info_label = None
        self.widget = self._build()

    def _install_spec(self, key):
        return self._specs.get(key, key)

    def _on_toggle(self, row, want_on):
        # Removing is conflict-free; installing replaces the one prompt slot, so confirm.
        if not want_on:
            super()._on_toggle(row, want_on)
            return

        dialog = Gtk.AlertDialog()
        dialog.set_modal(True)
        dialog.set_message(f"Set your prompt to {row.plugin}?")
        dialog.set_detail(
            "A prompt framework replaces your current fish prompt. Your fish "
            "config is backed up first — restore it from Settings → Backup & restore."
        )
        dialog.set_buttons(["Cancel", "Replace"])
        dialog.set_cancel_button(0)
        dialog.set_default_button(1)
        dialog.choose(self.widget.get_root(), None, lambda dlg, res: self._confirm_install(dlg, res, row))

    def _confirm_install(self, dialog, result, row):
        try:
            chosen = dialog.choose_finish(result)
        except GLib.Error:
            chosen = 0
        if chosen != 1:
            row.set_installed(False)  # revert the switch the user flipped on
            return
        row.set_loading(True)
        self._set_status("")

        def on_done(result):
            GLib.idle_add(self._framework_installed, row, result)

        ftt_prompt.install_framework_async(self._install_spec(row.plugin), on_done, snapshot=True)

    def _framework_installed(self, row, result):
        row.set_loading(False)
        if result.ok:
            row.set_installed(True)
            self._set_status(
                f"{row.plugin} is now your prompt. Only one prompt framework is active "
                "at a time — installing another replaces it."
            )
        else:
            row.set_installed(False)
            detail = result.message or "see terminal for details"
            self._set_status(f"{row.plugin} failed: {detail}", error=True)
        return False

    def _on_framework_selected(self, _listbox, listrow):
        if listrow is None:
            self._info_label.set_markup(_FRAMEWORK_INFO_DEFAULT)
            return
        key = self._framework_order[listrow.get_index()]
        self._info_label.set_markup(_FRAMEWORK_INFO.get(key, _FRAMEWORK_INFO_DEFAULT))

    def _build(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(16)

        self._init_status()

        if ftt_fisher.is_fisher_available():
            box.append(_section("Prompt frameworks"))
            box.append(
                _intro(
                    "Installing a framework activates it. Turn it off to remove it "
                    "and return to your previous prompt. Click one for details below."
                )
            )
            listbox = Gtk.ListBox()
            listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
            listbox.add_css_class("plugin-list")
            for key, spec, description in _PROMPT_FRAMEWORKS:
                row = _PluginRow(key, description, self._on_toggle)
                self._rows[key] = row
                self._specs[key] = spec
                self._framework_order.append(key)
                listbox.append(row.widget)
            listbox.connect("row-selected", self._on_framework_selected)
            listbox.unselect_all()
            box.append(listbox)
        else:
            box.append(_intro("fisher is not available — install it (sudo pacman -S fisher) to add prompt frameworks."))

        box.append(_section("Built-in prompts"))
        box.append(_intro("Zero-dependency prompt styles that ship with fish."))
        box.append(self._build_builtin_picker())

        reset_btn = Gtk.Button(label="Reset to default prompt")
        reset_btn.set_halign(Gtk.Align.START)
        reset_btn.set_tooltip_text("Remove any framework and custom prompt; back to fish's default")
        reset_btn.connect("clicked", self._reset_prompt)
        box.append(reset_btn)

        starship_note = _intro("Starship support is coming with presets.")
        starship_note.add_css_class("muted")
        box.append(starship_note)

        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        self._info_label = Gtk.Label(xalign=0, yalign=0)
        self._info_label.add_css_class("info-panel")
        self._info_label.set_wrap(True)
        self._info_label.set_vexpand(True)
        self._info_label.set_markup(_FRAMEWORK_INFO_DEFAULT)
        box.append(self._info_label)

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

    def _reset_prompt(self, _btn):
        installed = [key for key, row in self._rows.items() if row.switch.get_active()]
        self._set_status("Resetting prompt…")

        def on_done(result):
            GLib.idle_add(self._reset_finished, result)

        ftt_prompt.reset_default_async(installed, on_done, snapshot=True)

    def _reset_finished(self, result):
        if result.ok:
            for row in self._rows.values():
                row.set_installed(False)
            self._set_status("Prompt reset to fish's default. Open a new shell to see it.")
        else:
            detail = result.message or "see terminal for details"
            self._set_status(f"Reset failed: {detail}", error=True)
        return False


# ── Themes tab ───────────────────────────────────────────────────────────────


def _rgb(hex_color):
    """Convert '#rrggbb' (or '#rgb') to a (r, g, b) float tuple in 0..1."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))


# fish_color keys shown as foreground bars in a swatch, in display order.
_SWATCH_BAR_KEYS = [
    "fish_color_command",
    "fish_color_param",
    "fish_color_quote",
    "fish_color_redirection",
    "fish_color_error",
    "fish_color_comment",
]

# Hover-preview sample line: (text, fish_color key or None to use 'normal').
_PREVIEW_TOKENS = [
    ("~/project", "fish_color_cwd"),
    (" ", None),
    ("ls", "fish_color_command"),
    (" ", None),
    ("-la", "fish_color_param"),
    (" ", None),
    ("|", "fish_color_redirection"),
    (" ", None),
    ("grep", "fish_color_command"),
    (" ", None),
    ('"foo"', "fish_color_quote"),
    ("   ", None),
    ("# note", "fish_color_comment"),
]


def _bar_colors(colors):
    """Pick the swatch foreground bar colours from a parsed colour dict."""
    normal = colors.get("fish_color_normal")
    out = []
    for key in _SWATCH_BAR_KEYS:
        color = colors.get(key) or normal
        if color:
            out.append(color)
    return out


def _preview_markup(background, colors):
    """Build Pango markup of a fish_config-show-style sample in a theme's colours."""
    bg = background or "#1d1f21"
    normal = colors.get("fish_color_normal", "#d3d7cf")

    def col(key):
        return colors.get(key, normal) if key else normal

    line1 = "".join(
        f"<span foreground='{col(key)}'>{GLib.markup_escape_text(text)}</span>"
        for text, key in _PREVIEW_TOKENS
    )
    line2 = (
        f"<span foreground='{col('fish_color_error')}'>error:</span> "
        f"<span foreground='{col('fish_color_autosuggestion')}'>"
        f"{GLib.markup_escape_text('press → to accept')}</span>"
    )
    return (
        f"<tt><span background='{bg}'>  {line1}  </span>\n"
        f"<span background='{bg}'>  {line2}  </span></tt>"
    )


def _swatch(background, colors, width=190, height=72):
    """Return (DrawingArea, update_fn); update_fn(bg, colors) recolours and redraws."""
    area = Gtk.DrawingArea()
    area.set_size_request(width, height)
    state = {"bg": background, "fgs": _bar_colors(colors)}

    def draw(_area, cr, w, h, _data=None):
        bg = _rgb(state["bg"]) if state["bg"] else (0.12, 0.12, 0.12)
        cr.set_source_rgb(*bg)
        cr.rectangle(0, 0, w, h)
        cr.fill()
        if state["fgs"]:
            pad = 12
            count = len(state["fgs"])
            bar_w = (w - 2 * pad) / count
            for i, color in enumerate(state["fgs"]):
                cr.set_source_rgb(*_rgb(color))
                cr.rectangle(pad + i * bar_w + 2, h * 0.45, bar_w - 4, h * 0.35)
                cr.fill()

    def update(bg, cols):
        state["bg"] = bg
        state["fgs"] = _bar_colors(cols)
        area.queue_draw()

    area.set_draw_func(draw)
    return area, update


class ThemesTab(_StatusMixin):
    """Themes tab — gallery of fish_config colour themes with apply (M2)."""

    def __init__(self):
        self._prefs = ftt_config.load_prefs()
        self._current = self._prefs.get("current_theme")
        self._variant = self._prefs.get("theme_variant", "dark")
        self._cards = {}
        self._swatch_updaters = {}
        self._card_colors = {}
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

        variant_label = Gtk.Label(label="Variant:")
        variant_label.set_tooltip_text("Light or dark for themes that ship both (catppuccin, ayu, …)")
        header.append(variant_label)
        self._variant_dropdown = Gtk.DropDown.new_from_strings(_VARIANTS)
        self._variant_dropdown.set_selected(_VARIANTS.index(self._variant) if self._variant in _VARIANTS else 0)
        self._variant_dropdown.connect("notify::selected", self._on_variant_changed)
        header.append(self._variant_dropdown)

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

        box.append(self._init_status())

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_child(box)
        return scroller

    def _make_card(self, name):
        background, colors = ftt_theme.parse_theme(name, self._variant)
        self._card_colors[name] = (background, colors)
        button = Gtk.Button()
        button.add_css_class("theme-card")
        if name == self._current:
            button.add_css_class("theme-current")

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        swatch, update = _swatch(background, colors)
        self._swatch_updaters[name] = update
        content.append(swatch)
        label = Gtk.Label(label=name)
        label.add_css_class("plugin-name")
        label.set_ellipsize(3)  # Pango.EllipsizeMode.END
        content.append(label)
        button.set_child(content)
        button.set_has_tooltip(True)
        button.connect("query-tooltip", self._on_card_tooltip, name)
        button.connect("clicked", lambda _b, n=name: self._apply(n))
        return button

    def _on_card_tooltip(self, _widget, _x, _y, _keyboard, tooltip, name):
        background, colors = self._card_colors.get(name, (None, {}))
        label = Gtk.Label()
        label.add_css_class("theme-preview")
        label.set_markup(_preview_markup(background, colors))
        for side in ("top", "bottom", "start", "end"):
            getattr(label, f"set_margin_{side}")(8)
        tooltip.set_custom(label)
        return True

    def _on_variant_changed(self, dropdown, _param):
        self._variant = _VARIANTS[dropdown.get_selected()]
        self._prefs["theme_variant"] = self._variant
        ftt_config.save_prefs(self._prefs)
        for name, update in self._swatch_updaters.items():
            background, colors = ftt_theme.parse_theme(name, self._variant)
            self._card_colors[name] = (background, colors)
            update(background, colors)

    def _apply(self, name):
        if self._busy:
            return
        self._busy = True
        self._set_status(f"Applying {name}…")

        def on_done(result):
            GLib.idle_add(self._apply_finished, name, result)

        ftt_theme.apply_async(name, on_done, snapshot=True, color_theme=self._variant)

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


# ── Settings tab ─────────────────────────────────────────────────────────────


class SettingsTab(_StatusMixin):
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

        box.append(self._init_status())

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

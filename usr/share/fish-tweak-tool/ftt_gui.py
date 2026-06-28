"""GTK4 GUI for fish-tweak-tool.

Plugins and Prompt tabs (M1) are live; Themes and Settings remain placeholders
that later milestones fill in. Building the shell up-front means each milestone
drops into a fixed slot with no structural churn.
"""

import os
import re
import shutil
import subprocess
import threading

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

import ftt_config  # noqa: E402
import ftt_fisher  # noqa: E402
import ftt_managed  # noqa: E402
import ftt_presets  # noqa: E402
import ftt_prompt  # noqa: E402
import ftt_theme  # noqa: E402
import log  # noqa: E402

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


def _open_link(label, uri):
    """activate-link handler — open uri in the default browser."""
    Gtk.UriLauncher.new(uri).launch(label.get_root(), None, None)
    return True


class _PluginRow:
    """One install target: name, description, repo link, busy spinner, install/remove switch."""

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

        link = Gtk.Label()
        link.set_markup(f"<a href='https://github.com/{plugin}'><i>link</i></a>")
        link.set_tooltip_text(f"Open github.com/{plugin}")
        link.set_valign(Gtk.Align.CENTER)
        link.connect("activate-link", _open_link)

        self.spinner = Gtk.Spinner()
        self.spinner.set_valign(Gtk.Align.CENTER)
        self.spinner.set_visible(False)

        self.switch = Gtk.Switch()
        self.switch.set_valign(Gtk.Align.CENTER)
        self.switch.connect("notify::active", self._switched)

        self.widget.append(text)
        self.widget.append(link)
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


# ── ANSI → Pango (prompt samples) ────────────────────────────────────────────


_ANSI_BASIC = {
    30: "#000000", 31: "#cc0000", 32: "#4e9a06", 33: "#c4a000",
    34: "#3465a4", 35: "#75507b", 36: "#06989a", 37: "#d3d7cf",
    90: "#555753", 91: "#ef2929", 92: "#8ae234", 93: "#fce94f",
    94: "#729fcf", 95: "#ad7fa8", 96: "#34e2e2", 97: "#eeeeec",
}
_ANSI_RE = re.compile(r"\x1b\[([0-9;]*)m")


def _ansi_span(text, state):
    esc = GLib.markup_escape_text(text)
    attrs = []
    if state["fg"]:
        attrs.append(f"foreground='{state['fg']}'")
    if state["bold"]:
        attrs.append("font_weight='bold'")
    return f"<span {' '.join(attrs)}>{esc}</span>" if attrs else esc


def _ansi_apply(codes, state):
    parts = [int(c) for c in codes.split(";") if c != ""] or [0]
    i = 0
    while i < len(parts):
        code = parts[i]
        if code == 0:
            state.update(fg=None, bold=False)
        elif code == 1:
            state["bold"] = True
        elif code == 22:
            state["bold"] = False
        elif code == 39:
            state["fg"] = None
        elif code == 38 and parts[i + 1 : i + 2] == [2] and i + 4 < len(parts):
            state["fg"] = "#{:02x}{:02x}{:02x}".format(parts[i + 2], parts[i + 3], parts[i + 4])
            i += 4
        elif code in _ANSI_BASIC:
            state["fg"] = _ANSI_BASIC[code]
        i += 1


def _ansi_to_markup(text):
    """Convert ANSI-coloured terminal text to Pango markup (foreground + bold)."""
    state = {"fg": None, "bold": False}
    out = []
    pos = 0
    for match in _ANSI_RE.finditer(text):
        chunk = text[pos : match.start()]
        if chunk:
            out.append(_ansi_span(chunk, state))
        _ansi_apply(match.group(1), state)
        pos = match.end()
    if text[pos:]:
        out.append(_ansi_span(text[pos:], state))
    return "".join(out)


def _prompt_sample_markup(raw):
    """Markup for a `fish_config prompt show` sample (the line after the name header)."""
    lines = raw.splitlines()
    sample = lines[1] if len(lines) > 1 else (lines[0] if lines else "")
    return f"<tt><span background='#1d1f21'> {_ansi_to_markup(sample)} </span></tt>"


# ── Prompt tab ───────────────────────────────────────────────────────────────


class PromptTab(_StatusMixin):
    """Prompt tab — choose one prompt: default, a built-in style, or a framework (M1).

    fish has a single prompt slot, so the options are a mutually-exclusive radio
    group. Applying one removes any other framework and sets the chosen prompt,
    so the selection honestly reflects the one active prompt.
    """

    def __init__(self):
        self._prefs = ftt_config.load_prefs()
        self._specs = {key: spec for key, spec, _ in _PROMPT_FRAMEWORKS}
        self._radios = {}
        self._group_first = None
        self._builtin_names = []
        self._cards = {}
        self._sample_labels = {}
        self._selected_builtin = None
        self._stack = None
        self._apply_btn = None
        self._status = None
        self._status_timeout = 0
        self.widget = self._build()

    def _add_radio(self, container, rid, label, sensitive=True):
        radio = Gtk.CheckButton(label=label)
        radio.set_margin_top(4)
        radio.set_margin_bottom(4)
        radio.set_margin_start(8)
        radio.set_margin_end(8)
        if self._group_first is None:
            self._group_first = radio
        else:
            radio.set_group(self._group_first)
        radio.set_sensitive(sensitive)
        radio.connect("toggled", self._on_radio_toggled, rid)
        self._radios[rid] = radio
        if container is not None:
            container.append(radio)
        return radio

    def _on_radio_toggled(self, button, rid):
        if not button.get_active():
            return
        if self._stack is not None:
            self._stack.set_visible_child_name(rid)
        self._refresh_card_highlight()

    def _refresh_card_highlight(self):
        # A card is only marked current when "Built-in" is the active choice, so a
        # built-in card never looks selected while a framework is.
        active = self._radios["builtin"].get_active()
        for name, card in self._cards.items():
            if active and name == self._selected_builtin:
                card.add_css_class("theme-current")
            else:
                card.remove_css_class("theme-current")

    def _build(self):
        fisher = ftt_fisher.is_fisher_available()
        self._builtin_names = ftt_prompt.list_builtin()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(16)

        self._init_status()
        box.append(_section("Prompt"))
        box.append(
            _intro(
                "Choose one prompt. fish has a single prompt slot, so applying one "
                "removes any other framework and makes this your prompt."
            )
        )

        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        group.add_css_class("plugin-list")
        self._add_radio(group, "builtin", "Built-in — fish's bundled styles", sensitive=bool(self._builtin_names))
        for key, _spec, desc in _PROMPT_FRAMEWORKS:
            name = key.rsplit("/", 1)[-1].capitalize()
            self._add_radio(group, f"framework:{key}", f"{name} — {desc}", sensitive=fisher)
        box.append(group)

        self._apply_btn = Gtk.Button(label="Apply prompt")
        self._apply_btn.add_css_class("suggested-action")
        self._apply_btn.set_halign(Gtk.Align.START)
        self._apply_btn.connect("clicked", self._apply_prompt)
        box.append(self._apply_btn)

        if not fisher:
            note = _intro("fisher is not available — install it (sudo pacman -S fisher) to use prompt frameworks.")
            note.add_css_class("muted")
            box.append(note)

        starship_note = _intro("Starship support is coming with presets.")
        starship_note.add_css_class("muted")
        box.append(starship_note)

        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        box.append(self._build_stack())

        box.append(self._status)
        self._restore_selection()
        self._load_samples()

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_child(box)
        return scroller

    def _build_stack(self):
        # One interchangeable block: the built-in gallery, or a framework's info.
        self._stack = Gtk.Stack()
        self._stack.set_hhomogeneous(False)
        self._stack.set_vhomogeneous(False)
        self._stack.add_named(self._build_gallery_page(), "builtin")
        for key, _spec, _desc in _PROMPT_FRAMEWORKS:
            info = Gtk.Label(xalign=0, yalign=0)
            info.add_css_class("info-panel")
            info.set_wrap(True)
            info.set_markup(_FRAMEWORK_INFO.get(key, _FRAMEWORK_INFO_DEFAULT))
            self._stack.add_named(info, f"framework:{key}")
        return self._stack

    def _build_gallery_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        page.append(
            _intro(
                "Built-in styles ship with fish — zero dependencies. Click a card, then "
                "Apply. The 'default' card is fish's plain prompt."
            )
        )
        if not self._builtin_names:
            note = _intro("No built-in prompts found.")
            note.add_css_class("muted")
            page.append(note)
            return page
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(4)
        flow.set_column_spacing(10)
        flow.set_row_spacing(10)
        flow.set_homogeneous(True)
        for name in self._builtin_names:
            card = self._make_card(name)
            self._cards[name] = card
            flow.append(card)
        page.append(flow)
        return page

    def _make_card(self, name):
        button = Gtk.Button()
        button.add_css_class("theme-card")
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        sample = Gtk.Label(xalign=0)
        sample.add_css_class("theme-preview")
        sample.set_ellipsize(3)  # Pango.EllipsizeMode.END
        sample.set_max_width_chars(28)
        sample.set_markup(f"<tt><span background='#1d1f21'> {GLib.markup_escape_text(name)} … </span></tt>")
        self._sample_labels[name] = sample
        content.append(sample)
        label = Gtk.Label(label=name, xalign=0)
        label.add_css_class("plugin-name")
        label.set_ellipsize(3)
        content.append(label)
        button.set_child(content)
        button.connect("clicked", lambda _b, n=name: self._select_builtin(n))
        return button

    def _select_builtin(self, name):
        self._selected_builtin = name
        self._radios["builtin"].set_active(True)
        self._refresh_card_highlight()

    def _load_samples(self):
        def worker():
            for name in self._builtin_names:
                _rc, out, _err = ftt_fisher.run_fish(f"fish_config prompt show {name}")
                GLib.idle_add(self._set_sample, name, out)

        threading.Thread(target=worker, daemon=True).start()

    def _set_sample(self, name, raw):
        label = self._sample_labels.get(name)
        if label is not None and raw.strip():
            label.set_markup(_prompt_sample_markup(raw))
        return False

    def _restore_selection(self):
        # Which built-in card is selected (used whenever Built-in is active).
        card = self._prefs.get("current_builtin")
        if self._prefs.get("current_prompt") == "default":
            card = "default"
        if card not in self._builtin_names:
            card = "default" if "default" in self._builtin_names else (
                self._builtin_names[0] if self._builtin_names else None
            )
        self._selected_builtin = card

        # A framework prompt selects its radio; anything else falls back to Built-in.
        saved = self._prefs.get("current_prompt", "builtin")
        radio = self._radios.get(saved)
        if radio is None or not radio.get_sensitive():
            radio = self._radios["builtin"]
        radio.set_active(True)
        rid = next((r for r, b in self._radios.items() if b.get_active()), "builtin")
        self._stack.set_visible_child_name(rid)
        self._refresh_card_highlight()

    def _apply_prompt(self, _btn):
        rid = next((r for r, b in self._radios.items() if b.get_active()), "builtin")
        builtin_name = None
        if rid.startswith("framework:"):
            choice = ("framework", self._specs[rid.split(":", 1)[1]])
            prompt_key = rid
        else:
            if not self._selected_builtin:
                self._set_status("Pick a built-in style first.", error=True)
                return
            builtin_name = self._selected_builtin
            # The 'default' card is fish's plain prompt — a full reset, not a save.
            choice = ("default",) if builtin_name == "default" else ("builtin", builtin_name)
            prompt_key = "default" if builtin_name == "default" else "builtin"

        self._apply_btn.set_sensitive(False)
        self._set_status("Applying prompt…")
        frameworks = [(key, spec) for key, spec, _ in _PROMPT_FRAMEWORKS]

        def on_done(result):
            GLib.idle_add(self._prompt_applied, prompt_key, builtin_name, result)

        ftt_prompt.set_prompt_async(choice, frameworks, on_done, snapshot=True)

    def _prompt_applied(self, prompt_key, builtin_name, result):
        self._apply_btn.set_sensitive(True)
        if result.ok:
            updates = {"current_prompt": prompt_key}
            if builtin_name is not None:
                updates["current_builtin"] = builtin_name
            self._prefs = ftt_config.update_prefs(updates)
            self._set_status("Prompt applied. Open a new shell to see it.")
        else:
            detail = result.message or "see terminal for details"
            self._set_status(f"Could not apply prompt: {detail}", error=True)
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
        self._prefs = ftt_config.update_prefs({"theme_variant": self._variant})
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
            self._prefs = ftt_config.update_prefs({"current_theme": name})
            self._set_status(f"Theme '{name}' applied. Open a new shell to see it.")
        else:
            detail = result.message or "see terminal for details"
            self._set_status(f"Could not apply {name}: {detail}", error=True)
        return False


# ── Settings tab ─────────────────────────────────────────────────────────────


# Default custom-greeting text, prefilled on first run.
_DEFAULT_GREETING = "Welcome to KIRO"

# ASCII-art tools for the custom greeting. "none" = plain echo. Each maps to a
# pacman package of the same name; botsay has no font/variant.
_GREETING_TOOLS = ["None", "figlet", "toilet", "cowsay", "botsay"]
_GREETING_TOOL_BY_INDEX = {0: "none", 1: "figlet", 2: "toilet", 3: "cowsay", 4: "botsay"}
_GREETING_INDEX_BY_TOOL = {"figlet": 1, "toilet": 2, "cowsay": 3, "botsay": 4}
_FIGLET_FONT_DIR = "/usr/share/figlet/fonts"
_TOILET_FONT_DIR = "/usr/share/figlet"  # toilet's own .tlf fonts live here
_COWFILE_DIR = "/usr/share/cowsay/cows"
_FIGLET_FONT_SKIP = {"mini", "mnemonic", "ivrit"}


def _figlet_fonts():
    """Installed figlet font names, 'standard' first."""
    try:
        names = sorted(
            f[:-4] for f in os.listdir(_FIGLET_FONT_DIR)
            if f.endswith(".flf") and f[:-4] not in _FIGLET_FONT_SKIP
        )
    except OSError:
        return ["standard"]
    if "standard" in names:
        names.remove("standard")
        names.insert(0, "standard")
    return names or ["standard"]


def _toilet_fonts():
    """toilet's own .tlf font names, a nice one first."""
    try:
        names = sorted(f[:-4] for f in os.listdir(_TOILET_FONT_DIR) if f.endswith(".tlf"))
    except OSError:
        return ["future"]
    for pref in ("future", "pagga", "emboss", "bigmono9"):
        if pref in names:
            names.remove(pref)
            names.insert(0, pref)
            break
    return names or ["future"]


def _cowfiles():
    """Installed cowsay cowfile names, 'default' first."""
    try:
        names = sorted(f[:-4] for f in os.listdir(_COWFILE_DIR) if f.endswith(".cow"))
    except OSError:
        return ["default"]
    if "default" in names:
        names.remove("default")
        names.insert(0, "default")
    return names or ["default"]


def _greeting_fonts(tool):
    """Font/variant list for a greeting tool, or [] for 'none'/'botsay'."""
    if tool == "figlet":
        return _figlet_fonts()
    if tool == "toilet":
        return _toilet_fonts()
    if tool == "cowsay":
        return _cowfiles()
    return []


class SettingsTab(_StatusMixin):
    """Settings tab — greeting and backup / restore (M3)."""

    def __init__(self):
        self._prefs = ftt_config.load_prefs()
        self._busy = False
        self._status = None
        self._custom_entry = None
        self._backup_dropdown = None
        self._greeting_radios = {}
        self._gen_tool = None
        self._gen_font = None
        self._gen_font_names = []
        self._gen_color = None
        self._gen_color_box = None
        self._with_fastfetch = None
        self.widget = self._build()

    def _build(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(16)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.append(_section("Greeting"))
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header.append(spacer)
        ff_btn = Gtk.Button(label="Open Fastfetch Tweak Tool")
        ff_btn.set_valign(Gtk.Align.CENTER)
        if shutil.which("fastfetch-tweak-tool"):
            ff_btn.set_tooltip_text("Customise what fastfetch shows on launch")
            ff_btn.connect("clicked", self._open_fastfetch_tool)
        else:
            ff_btn.set_sensitive(False)
            ff_btn.set_tooltip_text("fastfetch-tweak-tool is not installed")
        header.append(ff_btn)
        box.append(header)
        box.append(self._build_greeting())

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
        self._custom_entry.set_text(saved.get("text", _DEFAULT_GREETING))
        box.append(self._custom_entry)

        art_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        art_label = Gtk.Label(label="ASCII art:")
        art_label.set_valign(Gtk.Align.CENTER)
        art_row.append(art_label)
        self._gen_tool = Gtk.DropDown.new_from_strings(_GREETING_TOOLS)
        self._gen_tool.set_selected(_GREETING_INDEX_BY_TOOL.get(saved.get("tool", "none"), 0))
        self._gen_tool.connect("notify::selected", lambda *_a: self._refresh_fonts())
        art_row.append(self._gen_tool)
        self._gen_font = Gtk.DropDown.new_from_strings(["(none)"])
        self._gen_font.set_hexpand(True)
        art_row.append(self._gen_font)

        # Rainbow switch for every tool: botsay uses -c, the others pipe through lolcat.
        self._gen_color_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._gen_color = Gtk.Switch()
        self._gen_color.set_valign(Gtk.Align.CENTER)
        color_label = Gtk.Label(label="Rainbow colour")
        color_label.set_valign(Gtk.Align.CENTER)
        self._gen_color_box.append(self._gen_color)
        self._gen_color_box.append(color_label)
        art_row.append(self._gen_color_box)
        box.append(art_row)

        hint = _intro("Renders the custom text as ASCII art. If the tool isn't installed, Apply offers to install it.")
        hint.add_css_class("muted")
        box.append(hint)

        self._with_fastfetch = Gtk.CheckButton(label="then show fastfetch below the text")
        self._with_fastfetch.set_active(bool(saved.get("with_fastfetch")))
        box.append(self._with_fastfetch)

        self._refresh_fonts()
        return box

    def _current_tool(self):
        return _GREETING_TOOL_BY_INDEX.get(self._gen_tool.get_selected(), "none")

    def _refresh_fonts(self):
        tool = self._current_tool()
        saved = self._prefs.get("greeting", {})
        # Rainbow switch for any real tool; font dropdown only for tools that have fonts.
        self._gen_color_box.set_visible(tool != "none")
        if tool != "none":
            self._gen_color.set_active(bool(saved.get("color")))
        fonts = _greeting_fonts(tool)
        self._gen_font_names = fonts
        self._gen_font.set_visible(bool(fonts))
        if fonts:
            self._gen_font.set_model(Gtk.StringList.new(fonts))
            self._gen_font.set_sensitive(True)
            if saved.get("font", "") in fonts:
                self._gen_font.set_selected(fonts.index(saved["font"]))

    def _open_fastfetch_tool(self, _btn):
        def worker():
            try:
                subprocess.Popen(["fastfetch-tweak-tool"])
            except OSError as exc:
                GLib.idle_add(self._set_status, f"Could not open Fastfetch Tweak Tool: {exc}", True)

        threading.Thread(target=worker, daemon=True).start()

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
        tool = self._current_tool()
        font = self._gen_font_names[self._gen_font.get_selected()] if tool != "none" and self._gen_font_names else ""
        return {"greeting": {
            "mode": mode,
            "text": self._custom_entry.get_text(),
            "tool": tool,
            "font": font,
            "color": tool != "none" and self._gen_color.get_active(),
            "with_fastfetch": self._with_fastfetch.get_active(),
        }}

    def _missing_packages(self, greeting):
        """Packages a custom greeting needs but that aren't installed (tool + lolcat)."""
        if greeting["mode"] != "custom":
            return []
        tool = greeting.get("tool", "none")
        pkgs = []
        if tool != "none":
            pkgs.append(tool)
        # lolcat colours figlet/toilet/cowsay; botsay colours itself with -c.
        if greeting.get("color") and tool in ("figlet", "toilet", "cowsay"):
            pkgs.append("lolcat")
        return [p for p in pkgs if not shutil.which(p)]

    def _apply_settings(self, _btn):
        if self._busy:
            return
        greeting = self._collect_settings()["greeting"]
        missing = self._missing_packages(greeting)
        if missing:
            self._busy = True
            self._offer_install(missing, greeting)
            return
        self._do_apply(greeting)

    def _offer_install(self, packages, greeting):
        names = " and ".join(packages)
        verb = "is" if len(packages) == 1 else "are"
        dialog = Gtk.AlertDialog()
        dialog.set_modal(True)
        dialog.set_message(f"Install {names}?")
        dialog.set_detail(
            f"{names} {verb} not installed, so the greeting can't render fully. Install with "
            "pacman? (You'll be asked for your password in a terminal.)"
        )
        dialog.set_buttons(["Cancel", "Install"])
        dialog.set_cancel_button(0)
        dialog.set_default_button(1)
        dialog.choose(self.widget.get_root(), None, lambda dlg, res: self._install_choice(dlg, res, packages, greeting))

    def _install_choice(self, dialog, result, packages, greeting):
        try:
            chosen = dialog.choose_finish(result)
        except GLib.Error:
            chosen = 0
        if chosen != 1:
            self._busy = False
            self._set_status("Greeting not applied — install the package(s) or change the tool.")
            return
        self._set_status(f"Installing {' '.join(packages)}…")

        def on_done(res):
            GLib.idle_add(self._install_done, packages, greeting, res)

        ftt_fisher.run_async(f"sudo pacman -S --needed {' '.join(packages)}", on_done, snapshot=False)

    def _install_done(self, packages, greeting, result):
        self._busy = False
        still = [p for p in packages if not shutil.which(p)]
        if result.ok and not still:
            self._do_apply(greeting)
        elif result.ok:
            self._set_status(f"Still not found: {', '.join(still)}.", error=True)
        else:
            self._set_status(f"Could not install: {result.message or 'see terminal'}", error=True)
        return False

    def _do_apply(self, greeting):
        self._busy = True
        # Read-modify-write from disk so a greeting apply never wipes the
        # abbreviations the Abbreviations tab wrote to the same managed block.
        prefs = ftt_config.load_prefs()
        prefs["greeting"] = greeting
        self._set_status("Applying settings…")

        def on_done(result):
            GLib.idle_add(self._apply_finished, greeting, result)

        ftt_managed.apply_async(ftt_managed.settings_from_prefs(prefs), on_done)

    def _apply_finished(self, greeting, result):
        self._busy = False
        if result.ok:
            self._prefs = ftt_config.update_prefs({"greeting": greeting})
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


# ── Presets tab ──────────────────────────────────────────────────────────────


_GIT_ABBR_PLUGIN = "jhillyerd/plugin-git"

# Greeting mode → overview label.
_GREETING_LABELS = {"keep": "unchanged", "off": "none", "fastfetch": "fastfetch", "custom": "custom"}

# Current-setup overview rows: (prefs/derived key, caption).
_OVERVIEW_ROWS = [
    ("prompt", "Prompt"),
    ("theme", "Theme"),
    ("plugins", "Plugins"),
    ("greeting", "Greeting"),
    ("abbr", "Abbreviations"),
]


def _prompt_label(prefs):
    """Human label for the current prompt recorded in prefs."""
    rid = prefs.get("current_prompt", "default")
    if rid == "builtin":
        return f"Built-in: {prefs.get('current_builtin', '?')}"
    if rid.startswith("framework:"):
        return rid.rsplit("/", 1)[-1].capitalize()
    return "Default"


def _consensus_installed(installed):
    """Short names of the consensus plugins that are installed."""
    installed_lower = {p.lower() for p in installed}
    return [repo.rsplit("/", 1)[-1] for repo, _ in _PLUGINS if repo.lower() in installed_lower]


def _matched_preset(prefs, installed):
    """Name of the preset whose components match the current state, or None."""
    installed_lower = {p.lower() for p in installed}
    cur_prompt = prefs.get("current_prompt", "default")
    cur_theme = prefs.get("current_theme") or "default"
    cur_mode = prefs.get("greeting", {}).get("mode", "keep")
    for preset in ftt_presets.PRESETS:
        if cur_prompt != ftt_presets.preset_prompt_rid(preset):
            continue
        if cur_theme != preset.get("theme", "default"):
            continue
        if cur_mode != preset.get("greeting", {}).get("mode", "keep"):
            continue
        if all(pl.lower() in installed_lower for pl in preset.get("plugins", [])):
            return preset["name"]
    return None


class PresetsTab(_StatusMixin):
    """Presets tab — one-click shell looks that bundle prompt + plugins + theme (M4)."""

    def __init__(self):
        self._status = None
        self._status_timeout = 0
        self._apply_btns = []
        self._ov_labels = {}
        self._ov_badge = None
        self.widget = self._build()

    def _build(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(16)

        box.append(self._build_overview())
        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        box.append(_section("Presets"))
        box.append(
            _intro(
                "One click sets a whole look — prompt, plugins, theme and greeting "
                "together. Your fish config is backed up first."
            )
        )

        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        listbox.add_css_class("plugin-list")
        for preset in ftt_presets.PRESETS:
            listbox.append(self._make_row(preset))
        box.append(listbox)

        box.append(self._init_status())

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_child(box)
        # Refresh the overview each time the tab is shown — picks up changes
        # made on the other tabs since it was last visible.
        scroller.connect("map", self._refresh_overview)
        return scroller

    # ── current-setup overview ────────────────────────────────────────────
    def _build_overview(self):
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        panel.add_css_class("info-panel")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.append(_section("Current setup"))
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header.append(spacer)
        self._ov_badge = Gtk.Label(label="…", xalign=1)
        self._ov_badge.set_valign(Gtk.Align.CENTER)
        header.append(self._ov_badge)
        panel.append(header)

        grid = Gtk.Grid()
        grid.set_row_spacing(2)
        grid.set_column_spacing(12)
        for row, (key, caption) in enumerate(_OVERVIEW_ROWS):
            cap = Gtk.Label(label=caption, xalign=0)
            cap.add_css_class("info-label")
            value = Gtk.Label(label="…", xalign=0)
            value.add_css_class("plugin-desc")
            value.set_wrap(True)
            value.set_hexpand(True)
            grid.attach(cap, 0, row, 1, 1)
            grid.attach(value, 1, row, 1, 1)
            self._ov_labels[key] = value
        panel.append(grid)
        return panel

    def _refresh_overview(self, *_args):
        def worker():
            installed = ftt_fisher.list_installed()
            GLib.idle_add(self._fill_overview, installed)

        threading.Thread(target=worker, daemon=True).start()

    def _fill_overview(self, installed):
        prefs = ftt_config.load_prefs()
        consensus = _consensus_installed(installed)
        git_on = _GIT_ABBR_PLUGIN.lower() in {p.lower() for p in installed}
        count = len(prefs.get("abbreviations", []))
        self._ov_labels["prompt"].set_text(_prompt_label(prefs))
        self._ov_labels["theme"].set_text(prefs.get("current_theme") or "default")
        self._ov_labels["plugins"].set_text(", ".join(consensus) if consensus else "none")
        self._ov_labels["greeting"].set_text(
            _GREETING_LABELS.get(prefs.get("greeting", {}).get("mode", "keep"), "unchanged")
        )
        self._ov_labels["abbr"].set_text(f"{count} custom" + (" · git set on" if git_on else ""))

        name = _matched_preset(prefs, installed)
        self._ov_badge.set_text(f"✓ matches {name}" if name else "Custom setup")
        self._ov_badge.remove_css_class("status-line" if name is None else "muted")
        self._ov_badge.add_css_class("status-line" if name else "muted")
        return False

    def _make_row(self, preset):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        for side in ("top", "bottom", "start", "end"):
            getattr(row, f"set_margin_{side}")(6)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text.set_hexpand(True)
        name = Gtk.Label(label=preset["name"], xalign=0)
        name.add_css_class("plugin-name")
        summary = Gtk.Label(label=preset["summary"], xalign=0)
        summary.add_css_class("plugin-desc")
        summary.set_wrap(True)
        text.append(name)
        text.append(summary)

        button = Gtk.Button(label="Apply")
        button.set_valign(Gtk.Align.CENTER)
        button.connect("clicked", lambda _b, p=preset: self._apply(p))
        self._apply_btns.append(button)

        row.append(text)
        row.append(button)
        return row

    def _apply(self, preset):
        dialog = Gtk.AlertDialog()
        dialog.set_modal(True)
        dialog.set_message(f"Apply the {preset['name']} preset?")
        dialog.set_detail(
            f"{preset['summary']}.\n\nThis installs plugins and sets your prompt, theme "
            "and greeting — your fish config is backed up first."
        )
        dialog.set_buttons(["Cancel", "Apply"])
        dialog.set_cancel_button(0)
        dialog.set_default_button(1)
        dialog.choose(self.widget.get_root(), None, lambda dlg, res: self._confirm(dlg, res, preset))

    def _confirm(self, dialog, result, preset):
        try:
            chosen = dialog.choose_finish(result)
        except GLib.Error:
            chosen = 0
        if chosen != 1:
            return
        self._set_buttons(False)
        self._set_status(f"Applying the {preset['name']} preset…")
        frameworks = [(key, spec) for key, spec, _ in _PROMPT_FRAMEWORKS]

        def on_done(res):
            GLib.idle_add(self._applied, preset, res)

        ftt_presets.apply_preset_async(preset, frameworks, on_done)

    def _applied(self, preset, result):
        self._set_buttons(True)
        if result.ok:
            self._refresh_overview()
            self._set_status(f"{preset['name']} preset applied. Open a new shell to see it.")
        else:
            detail = result.message or "see terminal for details"
            self._set_status(f"{preset['name']} preset failed: {detail}", error=True)
        return False

    def _set_buttons(self, sensitive):
        for button in self._apply_btns:
            button.set_sensitive(sensitive)


# ── Abbreviations tab ────────────────────────────────────────────────────────


def _parse_abbr_names(output):
    """Parse abbreviation names from `abbr --show` output (`abbr -a -- NAME 'VAL'`)."""
    names = []
    for line in output.splitlines():
        tokens = line.split()
        if "--" in tokens:
            idx = tokens.index("--")
            if idx + 1 < len(tokens):
                names.append(tokens[idx + 1])
    return names


_COLLISION_HINT = "Already defined elsewhere (e.g. a plugin) — your version overrides it in new shells."

# A sample of the most-used git abbreviations plugin-git installs (~100 total).
_GIT_CHEATSHEET = [
    ("g", "git"),
    ("gst", "git status"),
    ("ga", "git add"),
    ("gaa", "git add --all"),
    ("gapa", "git add --patch"),
    ("gc", "git commit -v"),
    ("gcam", "git commit -a -m"),
    ("gcan!", "git commit -v -a --no-edit --amend"),
    ("gco", "git checkout"),
    ("gcb", "git checkout -b"),
    ("gcom", "git checkout <default branch>"),
    ("gcl", "git clone"),
    ("gd", "git diff"),
    ("gf", "git fetch"),
    ("gfa", "git fetch --all --prune"),
    ("gl", "git pull"),
    ("gp", "git push"),
    ("gp!", "git push --force-with-lease"),
    ("gm", "git merge"),
    ("grb", "git rebase"),
    ("glog", "git log --oneline --graph"),
]


class _AbbrRow:
    """One editable abbreviation: name entry, expansion entry, delete button."""

    def __init__(self, name, expansion, on_delete, on_name_changed):
        self._on_delete = on_delete

        self.widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.widget.set_margin_top(4)
        self.widget.set_margin_bottom(4)
        self.widget.set_margin_start(6)
        self.widget.set_margin_end(6)

        self.name_entry = Gtk.Entry()
        self.name_entry.set_placeholder_text("name")
        self.name_entry.set_text(name)
        self.name_entry.set_width_chars(12)
        self.name_entry.connect("changed", lambda _e: on_name_changed())

        self.expansion_entry = Gtk.Entry()
        self.expansion_entry.set_placeholder_text("expands to…")
        self.expansion_entry.set_text(expansion)
        self.expansion_entry.set_hexpand(True)

        delete_btn = Gtk.Button.new_from_icon_name("edit-delete-symbolic")
        delete_btn.set_tooltip_text("Remove")
        delete_btn.set_valign(Gtk.Align.CENTER)
        delete_btn.connect("clicked", lambda _b: self._on_delete(self))

        self.widget.append(self.name_entry)
        self.widget.append(self.expansion_entry)
        self.widget.append(delete_btn)

    def name(self):
        """Return the trimmed abbreviation name."""
        return self.name_entry.get_text().strip()

    def expansion(self):
        """Return the trimmed expansion text."""
        return self.expansion_entry.get_text().strip()

    def set_collision(self, warned):
        """Show or clear the inline 'overrides an existing abbreviation' warning."""
        pos = Gtk.EntryIconPosition.SECONDARY
        if warned:
            self.name_entry.set_icon_from_icon_name(pos, "dialog-warning-symbolic")
            self.name_entry.set_icon_tooltip_text(pos, _COLLISION_HINT)
        else:
            self.name_entry.set_icon_from_icon_name(pos, None)


class AbbrTab(_FisherTab):
    """Abbreviations tab — git-abbr plugin toggle plus a custom abbreviation editor."""

    GIT_PLUGIN = _GIT_ABBR_PLUGIN

    def __init__(self):
        super().__init__()
        self._prefs = ftt_config.load_prefs()
        self._abbr_rows = []
        self._rows_box = None
        self._apply_btn = None
        self._all_defined = set()
        self._managed_names = {a.get("name", "") for a in self._prefs.get("abbreviations", [])}
        self._busy = False
        self.widget = self._build()

    def _build(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(16)

        box.append(_section("Git abbreviations"))
        box.append(
            _intro(
                "Install a curated set of git abbreviations (oh-my-zsh style) — "
                "gst → git status, gco → git checkout, and ~100 more — via fisher."
            )
        )
        if ftt_fisher.is_fisher_available():
            listbox = Gtk.ListBox()
            listbox.set_selection_mode(Gtk.SelectionMode.NONE)
            listbox.add_css_class("plugin-list")
            row = _PluginRow(self.GIT_PLUGIN, "oh-my-zsh-style git abbreviations (gst, gco, gp, …)", self._on_toggle)
            self._rows[self.GIT_PLUGIN] = row
            listbox.append(row.widget)
            box.append(listbox)
        else:
            note = _intro("fisher is not available — install it (sudo pacman -S fisher) to add the git set.")
            note.add_css_class("muted")
            box.append(note)

        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        box.append(_section("Your abbreviations"))
        box.append(
            _intro(
                "Add your own. Abbreviations expand inline as you type — e.g. 'k' → 'kubectl'. "
                "Names cannot contain spaces. Apply, then open a new shell to use them."
            )
        )

        self._rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._rows_box.add_css_class("plugin-list")
        box.append(self._rows_box)
        for abbr in self._prefs.get("abbreviations", []):
            self._add_row(abbr.get("name", ""), abbr.get("expansion", ""))
        if not self._abbr_rows:
            self._add_row()

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        add_btn = Gtk.Button(label="Add abbreviation")
        add_btn.connect("clicked", lambda _b: self._add_row())
        self._apply_btn = Gtk.Button(label="Apply abbreviations")
        self._apply_btn.add_css_class("suggested-action")
        self._apply_btn.connect("clicked", self._apply)
        buttons.append(add_btn)
        buttons.append(self._apply_btn)
        buttons.set_halign(Gtk.Align.START)
        box.append(buttons)

        box.append(self._init_status())

        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        box.append(self._build_cheatsheet())

        self._refresh_states()
        self._load_existing()

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_child(box)
        return scroller

    def _build_cheatsheet(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(_section("Most-used git abbreviations"))
        note = _intro(
            "A sample of what the toggle above installs — plugin-git ships ~100. "
            "They expand inline as you type, just like your own."
        )
        note.add_css_class("muted")
        box.append(note)

        grid = Gtk.Grid()
        grid.set_row_spacing(3)
        grid.set_column_spacing(14)
        grid.add_css_class("info-panel")
        for i, (name, expansion) in enumerate(_GIT_CHEATSHEET):
            col = (i % 2) * 2
            abbr = Gtk.Label(label=name, xalign=0)
            abbr.add_css_class("plugin-name")
            exp = Gtk.Label(label=expansion, xalign=0)
            exp.add_css_class("plugin-desc")
            grid.attach(abbr, col, i // 2, 1, 1)
            grid.attach(exp, col + 1, i // 2, 1, 1)
        box.append(grid)
        return box

    # ── editor rows ───────────────────────────────────────────────────────
    def _add_row(self, name="", expansion=""):
        row = _AbbrRow(name, expansion, self._delete_row, self._refresh_collisions)
        self._abbr_rows.append(row)
        self._rows_box.append(row.widget)
        self._refresh_collisions()

    def _delete_row(self, row):
        self._abbr_rows.remove(row)
        self._rows_box.remove(row.widget)
        self._refresh_collisions()

    # ── collision detection ───────────────────────────────────────────────
    def _load_existing(self):
        def worker():
            _rc, out, _err = ftt_fisher.run_fish("abbr --show")
            GLib.idle_add(self._set_existing, _parse_abbr_names(out))

        threading.Thread(target=worker, daemon=True).start()

    def _set_existing(self, names):
        self._all_defined = set(names)
        self._refresh_collisions()
        return False

    def _refresh_collisions(self):
        external = self._all_defined - self._managed_names
        for row in self._abbr_rows:
            name = row.name()
            row.set_collision(bool(name) and name in external)

    def _toggle_finished(self, row, want_on, result):
        # Installing the git set adds ~100 abbreviations; refresh the warnings.
        super()._toggle_finished(row, want_on, result)
        self._load_existing()
        return False

    # ── apply ─────────────────────────────────────────────────────────────
    def _collect(self):
        """Validate the editor rows; return (rows, error) with error None on success."""
        rows = []
        seen = set()
        for row in self._abbr_rows:
            name, expansion = row.name(), row.expansion()
            if not name and not expansion:
                continue
            if not name or not expansion:
                return None, f"'{name or expansion}': both a name and an expansion are required."
            if any(c.isspace() for c in name):
                return None, f"'{name}': abbreviation names cannot contain spaces."
            if "'" in name or "\\" in name:
                return None, f"'{name}': names cannot contain quotes or backslashes."
            if name in seen:
                return None, f"'{name}' is listed twice — names must be unique."
            seen.add(name)
            rows.append({"name": name, "expansion": expansion})
        return rows, None

    def _apply(self, _btn):
        if self._busy:
            return
        rows, error = self._collect()
        if error:
            self._set_status(error, error=True)
            return
        self._busy = True
        self._apply_btn.set_sensitive(False)
        prefs = ftt_config.load_prefs()
        prefs["abbreviations"] = rows
        self._set_status("Applying abbreviations…")

        def on_done(result):
            GLib.idle_add(self._applied, rows, result)

        ftt_managed.apply_async(ftt_managed.settings_from_prefs(prefs), on_done)

    def _applied(self, rows, result):
        self._busy = False
        self._apply_btn.set_sensitive(True)
        if result.ok:
            self._prefs = ftt_config.update_prefs({"abbreviations": rows})
            self._managed_names = {r["name"] for r in rows}
            self._load_existing()
            count = len(rows)
            plural = "" if count == 1 else "s"
            self._set_status(f"{count} abbreviation{plural} applied. Open a new shell to use them.")
        else:
            detail = result.message or "see terminal for details"
            self._set_status(f"Could not apply: {detail}", error=True)
        return False


# ── Entry point ──────────────────────────────────────────────────────────────


# Funding channels — GitHub Sponsors first (~100% payout). Keep in sync with
# kiro-website .github/FUNDING.yml if those change.
_FUNDING = [
    ("GitHub Sponsors", "https://github.com/sponsors/erikdubois", "best value — almost all goes to the project"),
    ("Ko-fi", "https://ko-fi.com/erikdubois", "buy a coffee — one-off tip"),
    ("Patreon", "https://www.patreon.com/kiroproject", "membership tiers + perks"),
    ("YouTube membership", "https://www.youtube.com/@ErikDubois/join", "join on YouTube"),
    ("PayPal", "https://www.paypal.me/erikdubois", "direct one-off"),
]


def _open_url(parent, url):
    Gtk.UriLauncher.new(url).launch(parent, None, None)


def _show_support_dialog(window):
    dlg = Gtk.Window(title="Support Kiro", transient_for=window, modal=True)
    dlg.set_default_size(440, -1)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    for side in ("start", "end", "top", "bottom"):
        getattr(box, f"set_margin_{side}")(18)

    heading = Gtk.Label(xalign=0)
    heading.set_markup("<b>Support Kiro</b>")
    box.append(heading)

    intro = Gtk.Label(xalign=0)
    intro.add_css_class("info-label")
    intro.set_wrap(True)
    intro.set_max_width_chars(52)
    intro.set_label(
        "Kiro and its tools are built by one person, for the community — and kept free. "
        "If Fish Tweak Tool saves you time, a little support keeps the work going. "
        "Thank you for being here."
    )
    box.append(intro)

    for name, url, note in _FUNDING:
        btn = Gtk.Button()
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        label = Gtk.Label(xalign=0)
        label.set_markup(f"<b>{name}</b>")
        sub = Gtk.Label(label=note, xalign=0)
        sub.add_css_class("info-label")
        content.append(label)
        content.append(sub)
        btn.set_child(content)
        btn.connect("clicked", lambda _w, u=url: _open_url(dlg, u))
        box.append(btn)

    close = Gtk.Button(label="Close")
    close.set_halign(Gtk.Align.END)
    close.connect("clicked", lambda _w: dlg.close())
    box.append(close)

    dlg.set_child(box)
    dlg.present()


def build(window, fish_version):
    """Populate the window with a header bar and the tabbed shell."""
    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

    header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    header.set_margin_start(12)
    header.set_margin_end(12)
    header.set_margin_top(10)
    header.set_margin_bottom(8)
    title = Gtk.Label(label="Fish Tweak Tool", xalign=0)
    title.set_name("title")
    title.set_hexpand(True)
    ver_text = f"fish v{fish_version}" if fish_version[:1].isdigit() else f"fish {fish_version}"
    lbl_version = Gtk.Label(label=ver_text)
    lbl_version.add_css_class("info-label")
    lbl_version.set_valign(Gtk.Align.CENTER)
    btn_support = Gtk.Button(label="♥ Support")
    btn_support.set_tooltip_text("Support Kiro's development")
    btn_support.add_css_class("support-button")
    btn_support.connect("clicked", lambda _w: _show_support_dialog(window))
    btn_quit = Gtk.Button(label="Quit")
    btn_quit.connect("clicked", lambda _w: window.close())
    header.append(title)
    header.append(lbl_version)
    header.append(btn_support)
    header.append(btn_quit)
    root.append(header)
    root.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

    notebook = Gtk.Notebook()
    notebook.set_scrollable(True)
    notebook.set_vexpand(True)
    notebook.append_page(PresetsTab().widget, Gtk.Label(label="Presets"))
    notebook.append_page(PluginsTab().widget, Gtk.Label(label="Plugins"))
    notebook.append_page(PromptTab().widget, Gtk.Label(label="Prompt"))
    notebook.append_page(ThemesTab().widget, Gtk.Label(label="Themes"))
    notebook.append_page(AbbrTab().widget, Gtk.Label(label="Abbreviations"))
    notebook.append_page(SettingsTab().widget, Gtk.Label(label="Settings"))
    root.append(notebook)

    window.set_child(root)
    log.debug_print(f"GUI built (fish {fish_version})")

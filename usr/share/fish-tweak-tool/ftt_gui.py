"""GTK4 GUI for fish-tweak-tool.

The Plugins tab (M1) is live; Prompt, Themes and Settings remain placeholders
that later milestones fill in. Building the shell up-front means each milestone
drops into a fixed slot with no structural churn.
"""

import threading

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

import ftt_fisher  # noqa: E402
import log  # noqa: E402

# Placeholder tabs not yet built: title → one-line description.
_PLACEHOLDERS = [
    ("Prompt", "Install and enable a prompt — Tide, Starship, Hydro, Pure, or a built-in style."),
    ("Themes", "Browse and apply colour themes from fish_config theme."),
    ("Settings", "Greeting, cursor shape, and backup / restore of your fish config."),
]

# The consensus must-have fisher plugins: repo → one-line description.
_PLUGINS = [
    ("PatrickF1/fzf.fish", "Fuzzy search over history, files, git, processes"),
    ("jorgebucaran/autopair.fish", "Auto-closes brackets, quotes and parens"),
    ("meaningful-ooo/sponge", "Drops failed commands from history"),
    ("nickeb96/puffer-fish", "Expands .. and ... as you type"),
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


# ── Plugins tab ──────────────────────────────────────────────────────────────


class _PluginRow:
    """One plugin: name, description, busy spinner, install/remove switch."""

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


class PluginsTab:
    """Plugins tab — toggle the consensus fisher plugins (M1)."""

    def __init__(self):
        self._snapshot_done = False
        self._rows = {}
        self._status = None
        self.widget = self._build()

    # ── construction ──────────────────────────────────────────────────────
    def _build(self):
        if not ftt_fisher.is_fisher_available():
            return _notice("fisher is not available", "Install it with:  sudo pacman -S fisher")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)

        intro = Gtk.Label(
            label="Toggle a plugin to install or remove it with fisher. "
            "Your fish config is backed up before the first change.",
            xalign=0,
        )
        intro.add_css_class("plugin-desc")
        intro.set_wrap(True)
        box.append(intro)

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

    # ── state ─────────────────────────────────────────────────────────────
    def _refresh_states(self):
        def worker():
            installed = ftt_fisher.list_installed()
            GLib.idle_add(self._apply_states, installed)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_states(self, installed):
        installed_lower = {p.lower() for p in installed}
        for plugin, row in self._rows.items():
            row.set_installed(plugin.lower() in installed_lower)
        return False

    # ── toggling ──────────────────────────────────────────────────────────
    def _on_toggle(self, row, want_on):
        row.set_loading(True)
        self._set_status("")
        snapshot = not self._snapshot_done
        self._snapshot_done = True

        def on_done(result):
            GLib.idle_add(self._toggle_finished, row, want_on, result)

        if want_on:
            ftt_fisher.install_async(row.plugin, on_done, snapshot=snapshot)
        else:
            ftt_fisher.remove_async(row.plugin, on_done, snapshot=snapshot)

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


# ── Entry point ──────────────────────────────────────────────────────────────


def build(window, fish_version):
    """Populate the window with the tabbed shell."""
    notebook = Gtk.Notebook()
    notebook.set_scrollable(True)

    notebook.append_page(PluginsTab().widget, Gtk.Label(label="Plugins"))
    for title, description in _PLACEHOLDERS:
        notebook.append_page(_placeholder(title, description), Gtk.Label(label=title))

    window.set_child(notebook)
    log.debug_print(f"GUI built (fish {fish_version})")

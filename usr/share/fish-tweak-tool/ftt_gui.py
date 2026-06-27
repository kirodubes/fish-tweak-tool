"""GTK4 GUI for fish-tweak-tool — tabbed shell (M0 skeleton).

The tabs are placeholders that the later milestones fill in:
Prompt (M1) · Plugins (M1) · Themes (M2) · Settings (M3). Building the shell
now means each milestone drops into a fixed slot with no structural churn.
"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

import log  # noqa: E402

# Tab title → one-line description of what that milestone will hold.
_TABS = [
    ("Prompt", "Install and enable a prompt — Tide, Starship, Hydro, Pure, or a built-in style."),
    ("Plugins", "Toggle fisher plugins — fzf.fish, autopair, sponge, puffer-fish."),
    ("Themes", "Browse and apply colour themes from fish_config theme."),
    ("Settings", "Greeting, cursor shape, and backup / restore of your fish config."),
]


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

    coming = Gtk.Label(label="Coming soon")
    coming.add_css_class("placeholder-badge")

    box.append(heading)
    box.append(detail)
    box.append(coming)
    return box


def build(window, fish_version):
    """Populate the window with the tabbed shell."""
    notebook = Gtk.Notebook()
    notebook.set_scrollable(True)

    for title, description in _TABS:
        notebook.append_page(_placeholder(title, description), Gtk.Label(label=title))

    window.set_child(notebook)
    log.debug_print(f"GUI shell built (fish {fish_version})")

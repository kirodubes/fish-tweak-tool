#!/usr/bin/env python3
"""Fish Tweak Tool — GTK4 configurator for the fish shell."""

# ── Force Python UTF-8 mode on a non-UTF-8 locale ─────────────────────────
# Never crash on a non-UTF-8 system locale (e.g. latin-1 fr_BE). Under such a
# locale Python encodes stdout and subprocess output with latin-1, so any
# non-ASCII glyph raises a Unicode error. UTF-8 mode forces UTF-8 regardless of
# LANG. Re-exec only when the locale's encoding is not UTF-8 — a normal UTF-8
# desktop is left untouched; the guard is loop-safe (the re-exec'd process is
# UTF-8 already).
import codecs
import os
import sys

if codecs.lookup(sys.getfilesystemencoding()).name != "utf-8":
    os.environ["PYTHONUTF8"] = "1"
    os.execv(sys.executable, [sys.executable, "-X", "utf8", *sys.argv])

# Spawned shells inherit our locale; if it is not UTF-8 their output renders as
# mojibake. Keep the user's locale when it is already UTF-8, otherwise fall back
# to C.UTF-8 so child output stays readable.
_cur_locale = os.environ.get("LC_ALL") or os.environ.get("LC_CTYPE") or os.environ.get("LANG") or ""
if "utf-8" not in _cur_locale.lower() and "utf8" not in _cur_locale.lower():
    os.environ["LANG"] = "C.UTF-8"
    os.environ["LC_ALL"] = "C.UTF-8"

import subprocess  # noqa: E402

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import ftt_config  # noqa: E402
import ftt_gui as gui_module  # noqa: E402
import log  # noqa: E402


def _fish_version():
    """Return the installed fish version string, or 'unknown'."""
    try:
        out = subprocess.run(["fish", "--version"], capture_output=True, text=True, timeout=3)
        # output is e.g. "fish, version 4.7.1"
        return out.stdout.strip().split()[-1]
    except Exception:
        return "unknown"


class FishTweakApp(Gtk.Application):
    """GTK4 application entry point for fish-tweak-tool."""

    def __init__(self):
        super().__init__(application_id="com.kiro.fish-tweak-tool")
        self.connect("activate", self.on_activate)

    def on_activate(self, _app):
        window = Main(self)
        window.present()


class Main(Gtk.ApplicationWindow):
    """Main application window."""

    def __init__(self, app):
        super().__init__(application=app, title="Fish Tweak Tool")
        self._prefs = ftt_config.load_prefs()
        w = self._prefs.get("window_width", 900)
        h = self._prefs.get("window_height", 580)
        self.set_default_size(w, h)
        self.connect("close-request", self._on_close)
        self._load_css()
        self._build_headerbar()
        gui_module.build(self, _fish_version())
        log.log_timing("GUI built")

    def _build_headerbar(self):
        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)
        self.set_titlebar(header)

    def _load_css(self):
        css_path = os.path.join(BASE_DIR, "ftt.css")
        if not os.path.isfile(css_path):
            return
        provider = Gtk.CssProvider()
        provider.load_from_path(css_path)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _on_close(self, _window):
        w, h = self.get_default_size()
        self._prefs["window_width"] = w
        self._prefs["window_height"] = h
        ftt_config.save_prefs(self._prefs)
        return False


def main():
    if "--debug" in sys.argv:
        log.DEBUG = True
    if "--dev" in sys.argv:
        log.DEV = True
    log.log_section("Fish Tweak Tool")
    app = FishTweakApp()
    app.run(None)


if __name__ == "__main__":
    main()

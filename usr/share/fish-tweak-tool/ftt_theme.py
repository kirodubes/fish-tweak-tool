"""Colour theme gallery for fish-tweak-tool (fish_config theme).

Lists fish's bundled `.theme` files, parses a few colours from each for a swatch
preview, and applies one with ``fish_config theme save`` (which, like prompt
save, gates on an interactive read — so the apply pipes `y`).
"""

import os
import re

import ftt_fisher

SYSTEM_THEME_DIR = "/usr/share/fish/themes"
USER_THEME_DIR = os.path.expanduser("~/.config/fish/themes")

# fish_color keys sampled for the swatch foreground bars, in display order.
_SWATCH_KEYS = [
    "fish_color_command",
    "fish_color_param",
    "fish_color_quote",
    "fish_color_redirection",
    "fish_color_error",
    "fish_color_comment",
]

_HEX_RE = re.compile(r"^[0-9a-fA-F]{6}$|^[0-9a-fA-F]{3}$")


def list_themes():
    """Return the list of theme names from fish_config theme list."""
    rc, out, _ = ftt_fisher.run_fish("fish_config theme list")
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def theme_file(name):
    """Return the .theme file path for a theme name (user dir wins), or None."""
    for directory in (USER_THEME_DIR, SYSTEM_THEME_DIR):
        path = os.path.join(directory, f"{name}.theme")
        if os.path.isfile(path):
            return path
    return None


def parse_theme(name):
    """Return (background_hex, [foreground_hex, ...]) for the swatch."""
    path = theme_file(name)
    if not path:
        return None, []

    background = None
    colors = {}
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line.startswith("# preferred_background:"):
                background = _to_hex(line.split(":", 1)[1].strip())
            elif line and not line.startswith("#"):
                parts = line.split()
                value = _first_hex(parts[1:])
                if value:
                    colors[parts[0]] = value

    foregrounds = [colors[k] for k in _SWATCH_KEYS if k in colors]
    return background, foregrounds


def apply_async(name, on_done, snapshot=False):
    """Apply and persist a theme off the UI thread; call on_done(Result).

    `fish_config theme save <name>` gates on an interactive "Overwrite? [y/N]"
    read, so piping `y` confirms it non-interactively.
    """
    ftt_fisher.run_async(f"echo y | fish_config theme save {name}", on_done, snapshot)


def _first_hex(tokens):
    for token in tokens:
        if _HEX_RE.match(token):
            return "#" + token
    return None


def _to_hex(token):
    return "#" + token if _HEX_RE.match(token) else None

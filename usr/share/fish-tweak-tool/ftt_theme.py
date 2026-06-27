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
_AWARE_RE = re.compile(r"^\[(dark|light|unknown)\]")


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


def parse_theme(name, variant="dark"):
    """Return (background_hex, [foreground_hex, ...]) for the swatch.

    Colour-theme-aware files split colours into [light]/[dark] sections; the
    requested variant is used, falling back to dark/light/unknown, then to the
    file's top-level colours for non-aware themes.
    """
    path = theme_file(name)
    if not path:
        return None, []

    sections = {None: {"bg": None, "colors": {}}}
    current = None
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            match = _AWARE_RE.match(line)
            if match:
                current = match.group(1)
                sections.setdefault(current, {"bg": None, "colors": {}})
                continue
            section = sections[current]
            if line.startswith("# preferred_background:"):
                section["bg"] = _to_hex(line.split(":", 1)[1].strip())
            elif line and not line.startswith("#"):
                parts = line.split()
                value = _first_hex(parts[1:])
                if value:
                    section["colors"][parts[0]] = value

    chosen = sections[None]
    for key in (variant, "dark", "light", "unknown", None):
        candidate = sections.get(key)
        if candidate and (candidate["colors"] or candidate["bg"]):
            chosen = candidate
            break

    foregrounds = [chosen["colors"][k] for k in _SWATCH_KEYS if k in chosen["colors"]]
    return chosen["bg"], foregrounds


def is_color_theme_aware(name):
    """Return True if the theme has light/dark variant sections (needs --color-theme)."""
    path = theme_file(name)
    if not path:
        return False
    with open(path, encoding="utf-8") as f:
        return any(_AWARE_RE.match(line) for line in f)


def apply_async(name, on_done, snapshot=False, color_theme="dark"):
    """Apply and persist a theme off the UI thread; call on_done(Result).

    `fish_config theme save <name>` gates on an interactive "Overwrite? [y/N]"
    read, so piping `y` confirms it. Color-theme-aware themes (catppuccin, ayu,
    …) also need an explicit light/dark choice — fish normally reads it from the
    terminal, which is unavailable under `fish -c`, so we pass --color-theme.
    Passing that flag to a non-aware theme errors, so it is added only when needed.
    """
    flag = f"--color-theme={color_theme} " if is_color_theme_aware(name) else ""
    ftt_fisher.run_async(f"echo y | fish_config theme save {flag}{name}", on_done, snapshot)


def _first_hex(tokens):
    for token in tokens:
        if _HEX_RE.match(token):
            return "#" + token
    return None


def _to_hex(token):
    return "#" + token if _HEX_RE.match(token) else None

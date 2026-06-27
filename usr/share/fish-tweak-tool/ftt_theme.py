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

_HEX_RE = re.compile(r"^[0-9a-fA-F]{6}$|^[0-9a-fA-F]{3}$")
_AWARE_RE = re.compile(r"^\[(dark|light|unknown)\]")

# Themes may name colours instead of giving hex (e.g. `fish_color_comment red`).
# Map the 16 fish/ANSI names to representative hex so swatches/previews render.
_ANSI_HEX = {
    "black": "#2e3436", "red": "#cc0000", "green": "#4e9a06", "yellow": "#c4a000",
    "blue": "#3465a4", "magenta": "#75507b", "purple": "#75507b", "cyan": "#06989a",
    "white": "#d3d7cf", "brblack": "#555753", "brred": "#ef2929", "brgreen": "#8ae234",
    "bryellow": "#fce94f", "brblue": "#729fcf", "brmagenta": "#ad7fa8", "brpurple": "#ad7fa8",
    "brcyan": "#34e2e2", "brwhite": "#eeeeec",
}


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
    """Return (background_hex, {fish_color_key: hex}) for the chosen variant.

    Colour-theme-aware files split colours into [light]/[dark] sections; the
    requested variant is used, falling back to dark/light/unknown, then to the
    file's top-level colours for non-aware themes. Named ANSI colours are mapped
    to hex; flag-only values (`--reset`, `--reverse`) are dropped.
    """
    path = theme_file(name)
    if not path:
        return None, {}

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
                value = _resolve_color(parts[1:])
                if value:
                    section["colors"][parts[0]] = value

    chosen = sections[None]
    for key in (variant, "dark", "light", "unknown", None):
        candidate = sections.get(key)
        if candidate and (candidate["colors"] or candidate["bg"]):
            chosen = candidate
            break

    return chosen["bg"], chosen["colors"]


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


def _resolve_color(tokens):
    """First usable colour token → '#hex' (hex or named), ignoring flags; None if none."""
    for raw in tokens:
        token = raw.strip("\"'")  # some themes quote their values, e.g. '888'
        if not token or token.startswith("-"):  # --reset, --reverse, --bold, --background=…
            continue
        if _HEX_RE.match(token):
            return "#" + token
        mapped = _ANSI_HEX.get(token.lower())
        if mapped:
            return mapped
    return None


def _to_hex(token):
    token = token.strip("\"'")
    return "#" + token if _HEX_RE.match(token) else None

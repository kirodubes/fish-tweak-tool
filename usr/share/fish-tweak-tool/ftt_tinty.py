"""Tinty orchestration for fish-tweak-tool (extra base16/base24 palettes).

`tinty` (tinted-theming's Rust CLI) themes the terminal across apps. Its
tinted-shell *fish* template sets both the terminal ANSI palette (OSC, per
session) and `fish_color_*` universals (persisted), so applying a scheme
recolours fish syntax highlighting like the native `fish_config theme` gallery,
plus the terminal palette. This module drives `tinty` to add 500+ palettes the
bundled gallery doesn't ship; it stays toolkit-free (no GTK) so it is testable.

The config we manage points tinty at the per-scheme `fish/` scripts:

    [[items]]
    path = "https://github.com/tinted-theming/tinted-shell"
    name = "tinted-shell"
    themes-dir = "fish"
    hook = "fish %f"
"""

import json
import os
import re
import shutil
import subprocess

import ftt_fisher

CONFIG = os.path.expanduser("~/.config/tinted-theming/tinty/config.toml")

_TINTED_SHELL_ITEM = (
    '[[items]]\n'
    'path = "https://github.com/tinted-theming/tinted-shell"\n'
    'name = "tinted-shell"\n'
    'themes-dir = "fish"\n'
    'hook = "fish %f"\n'
)

_HAS_ITEM_RE = re.compile(r'name\s*=\s*"tinted-shell"')

# fish_color bars shown in a card swatch, in display order: red, yellow, green,
# cyan, blue, magenta (the base16 accent colours).
_SWATCH_BASES = ["base08", "base0A", "base0B", "base0C", "base0D", "base0E"]

_schemes_cache = None


def is_available():
    """Return True if the tinty binary is on PATH."""
    return shutil.which("tinty") is not None


def list_schemes():
    """Return tinty's schemes as dicts (id, name, system, variant, palette).

    `palette` maps base00..base0F to '#hex'. Parsed once from `tinty list --json`
    and cached for the process; returns [] if tinty is missing or errors.
    """
    global _schemes_cache
    if _schemes_cache is not None:
        return _schemes_cache
    if not is_available():
        _schemes_cache = []
        return _schemes_cache
    try:
        proc = subprocess.run(
            ["tinty", "list", "--json"], capture_output=True, text=True, timeout=30
        )
        data = json.loads(proc.stdout) if proc.returncode == 0 else []
    except (OSError, ValueError, subprocess.SubprocessError):
        data = []
    _schemes_cache = [
        {
            "id": s["id"],
            "name": s.get("name", s["id"]),
            "system": s.get("system", ""),
            "variant": s.get("variant", ""),
            "palette": {k: v["hex_str"] for k, v in s.get("palette", {}).items()},
        }
        for s in data
        if "id" in s
    ]
    return _schemes_cache


def swatch_colors(palette):
    """Return (background_hex, [bar_hex, ...]) for a scheme's palette dict."""
    background = palette.get("base00")
    bars = [palette[b] for b in _SWATCH_BASES if b in palette]
    return background, bars


def current_scheme():
    """Return the id of the last-applied tinty scheme, or None."""
    if not is_available():
        return None
    try:
        proc = subprocess.run(
            ["tinty", "current"], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    out = proc.stdout.strip()
    return out if proc.returncode == 0 and out else None


def is_configured():
    """Return True if config.toml already has a tinted-shell item."""
    if not os.path.isfile(CONFIG):
        return False
    with open(CONFIG, encoding="utf-8") as f:
        return bool(_HAS_ITEM_RE.search(f.read()))


def ensure_config():
    """Add our tinted-shell item to config.toml if absent (preserving any others)."""
    if is_configured():
        return
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    existing = ""
    if os.path.isfile(CONFIG):
        with open(CONFIG, encoding="utf-8") as f:
            existing = f.read()
    block = (existing.rstrip("\n") + "\n\n" if existing.strip() else "") + _TINTED_SHELL_ITEM
    with open(CONFIG, "w", encoding="utf-8") as f:
        f.write(block)


def setup_and_apply_async(scheme_id, on_done):
    """Ensure config, then install (idempotent) + apply a scheme visibly."""
    ensure_config()
    ftt_fisher.run_async(f"tinty install; and tinty apply {scheme_id}", on_done, snapshot=True)

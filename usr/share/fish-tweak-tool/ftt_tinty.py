"""Tinty orchestration for fish-tweak-tool (extra base16/base24 palettes).

`tinty` (tinted-theming's Rust CLI) themes the terminal across apps. We use it to
recolour the terminal's 16-colour ANSI palette + background (OSC escape codes),
which affects everything in the terminal — a layer on top of, and independent of,
fish's own `fish_color_*` syntax theme (the native gallery). This module drives
`tinty` to add 500+ base16/base24 palettes; it stays toolkit-free (no GTK) so it
is testable. The palette re-applies per shell via `tinty init` in the managed block.

The config we manage uses tinty's official shell setup — the POSIX `scripts`
(`. %f`), which emit only the terminal's ANSI palette (OSC) via `sh`:

    [[items]]
    path = "https://github.com/tinted-theming/tinted-shell"
    name = "tinted-shell"
    themes-dir = "scripts"
    hook = ". %f"

We deliberately do NOT use the `fish` themes-dir (`hook = "fish %f"`): that hook
spawns a fish that re-sources config.fish, so a `tinty init` line there recurses
and deadlocks on fish's universal-variable lock. The `scripts` hook runs under
`sh`, sets no fish universals, and is safe to `tinty init` from config.fish.
"""

import json
import os
import re
import shutil
import subprocess

import ftt_fisher

CONFIG = os.path.expanduser("~/.config/tinted-theming/tinty/config.toml")

# nemesis_repo ships tinty as `tinty-git`.
PACKAGE = "tinty-git"

_TINTED_SHELL_ITEM = (
    '[[items]]\n'
    'path = "https://github.com/tinted-theming/tinted-shell"\n'
    'name = "tinted-shell"\n'
    'themes-dir = "scripts"\n'
    'hook = ". %f"\n'
)

_HAS_ITEM_RE = re.compile(r'name\s*=\s*"tinted-shell"')

# Swatch accent bars (red, yellow, green, cyan, blue, magenta). base16/base24 use
# base08–base0E; tinted8 schemes instead carry named keys (red-normal, …).
_BASE16_BARS = ["base08", "base0A", "base0B", "base0C", "base0D", "base0E"]
_TINTED8_BARS = ["red-normal", "yellow-normal", "green-normal", "cyan-normal", "blue-normal", "magenta-normal"]

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
    if _schemes_cache:  # cache only non-empty results, so a retry after install re-queries
        return _schemes_cache
    if not is_available():
        return []
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
    if "base00" in palette:  # base16 / base24
        background = palette.get("base00")
        bars = [palette[b] for b in _BASE16_BARS if b in palette]
    else:  # tinted8 — named keys, no base00
        background = palette.get("black-dim") or palette.get("black-normal")
        bars = [palette[b] for b in _TINTED8_BARS if b in palette]
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


def install_package_async(on_done):
    """Install the tinty package via pacman in a visible terminal."""
    ftt_fisher.run_async(f"sudo pacman -S --needed {PACKAGE}", on_done, snapshot=False)


def remove_package_async(on_done):
    """Remove the tinty package via pacman in a visible terminal."""
    ftt_fisher.run_async(f"sudo pacman -Rns {PACKAGE}", on_done, snapshot=False)

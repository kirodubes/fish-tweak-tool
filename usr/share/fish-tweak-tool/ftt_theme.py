"""Colour theme gallery for fish-tweak-tool (fish_config theme).

fish 4.x no longer ships its built-in themes as `.theme` files on disk — they
are embedded in the binary, reachable only through the CLI. So swatch colours
are read by loading a theme into a throwaway `fish -c` session
(``fish_config theme choose``) and printing it back with ``fish_config theme
dump`` — never by parsing files. Applying uses ``fish_config theme save`` (which,
like prompt save, gates on an interactive read — so the apply pipes `y`).
"""

import re

import ftt_fisher

_HEX_RE = re.compile(r"^[0-9a-fA-F]{6}$|^[0-9a-fA-F]{3}$")

# Themes may name colours instead of giving hex (e.g. `fish_color_comment red`).
# Map the 16 fish/ANSI names to representative hex so swatches/previews render.
_ANSI_HEX = {
    "black": "#2e3436", "red": "#cc0000", "green": "#4e9a06", "yellow": "#c4a000",
    "blue": "#3465a4", "magenta": "#75507b", "purple": "#75507b", "cyan": "#06989a",
    "white": "#d3d7cf", "brblack": "#555753", "brred": "#ef2929", "brgreen": "#8ae234",
    "bryellow": "#fce94f", "brblue": "#729fcf", "brmagenta": "#ad7fa8", "brpurple": "#ad7fa8",
    "brcyan": "#34e2e2", "brwhite": "#eeeeec",
}

_MARKER = "@@FTT@@"


def list_themes():
    """Return the list of theme names from fish_config theme list."""
    rc, out, _ = ftt_fisher.run_fish("fish_config theme list")
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def parse_all_themes(names, variant="dark"):
    """Return {name: (None, {fish_color_key: hex})} for every theme, in one fish run.

    Each theme is loaded with ``fish_config theme choose`` and read back with
    ``dump``. Colour-theme-aware themes (catppuccin, ayu, …) leave
    ``fish_color_command`` without a hex until a variant is chosen, so those get
    a second ``choose --color-theme=<variant>`` pass. ``dump`` tags every line
    with ``--theme=<name>``; that tag is the provenance guard — a line missing
    the current theme's tag is stale (a failed choose) and is dropped, so one
    theme's colours can never be attributed to another. Background is not in
    ``dump`` output, so the bg is always None (the caller supplies a fallback).
    """
    if not names:
        return {}

    quoted = " ".join(_fish_quote(name) for name in names)
    script = (
        f"set -l variant {variant}\n"
        f"for t in {quoted}\n"
        f"    printf '{_MARKER}%s\\n' $t\n"
        "    fish_config theme choose $t 2>/dev/null\n"
        "    set -l d (fish_config theme dump 2>/dev/null)\n"
        "    if not string match -qr '^fish_color_command +[0-9a-fA-F]' -- $d\n"
        "        fish_config theme choose $t --color-theme=$variant 2>/dev/null\n"
        "        set d (fish_config theme dump 2>/dev/null)\n"
        "    end\n"
        "    printf '%s\\n' $d\n"
        "end\n"
    )
    _, out, _ = ftt_fisher.run_fish(script)

    result = {name: {} for name in names}
    current = None
    for line in out.splitlines():
        if line.startswith(_MARKER):
            current = line[len(_MARKER):]
            continue
        if current is None or f"--theme={current}" not in line:
            continue
        parts = line.split()
        value = _resolve_color(parts[1:])
        if value:
            result[current][parts[0]] = value

    return {name: (None, colors) for name, colors in result.items()}


def parse_theme(name, variant="dark"):
    """Return (None, {fish_color_key: hex}) for one theme (thin wrapper on parse_all_themes)."""
    return parse_all_themes([name], variant).get(name, (None, {}))


def is_color_theme_aware(name):
    """Return True if the theme has light/dark variants (needs --color-theme)."""
    rc, out, _ = ftt_fisher.run_fish(f"fish_config theme show {_fish_quote(name)}")
    if rc != 0:
        return False
    return "(light color theme)" in out or "(dark color theme)" in out


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


def _fish_quote(value):
    """Single-quote a value for safe interpolation into a fish script."""
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _resolve_color(tokens):
    """First usable colour token → '#hex' (hex or named), ignoring flags; None if none."""
    for raw in tokens:
        token = raw.strip("\"'")  # some themes quote their values, e.g. '888'
        if not token or token.startswith("-"):  # --reset, --reverse, --bold, --theme=…
            continue
        if _HEX_RE.match(token):
            return "#" + token
        mapped = _ANSI_HEX.get(token.lower())
        if mapped:
            return mapped
    return None

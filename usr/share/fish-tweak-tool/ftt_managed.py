"""Managed-block writer for ~/.config/fish/config.fish.

FTT's per-user overrides (the greeting) live in a marked block appended to
config.fish — below any `source` line, so they load last and always win (the
load-order rule). The block is fully regenerated from a settings dict each time;
prefs.json is the source of truth for the UI, this is the source of truth for fish.
"""

import os
import threading

import ftt_fisher

START = "# >>> fish-tweak-tool managed block >>>"
END = "# <<< fish-tweak-tool managed block <<<"
CONFIG = os.path.expanduser("~/.config/fish/config.fish")


def settings_from_prefs(prefs):
    """Build the complete managed-block settings dict from a prefs dict."""
    return {
        "greeting": prefs.get("greeting", {}),
        "abbreviations": prefs.get("abbreviations", []),
    }


def _quote(text):
    """Escape text for a single-quoted fish string."""
    return text.replace("\\", "\\\\").replace("'", "\\'")


def render_block(settings):
    """Render the managed block text from a settings dict."""
    lines = [START, "# Managed by Fish Tweak Tool — edits inside this block are overwritten."]

    greeting = settings.get("greeting", {})
    mode = greeting.get("mode", "keep")
    if mode == "off":
        lines.append("function fish_greeting; end")
    elif mode == "fastfetch":
        lines.append("function fish_greeting; type -q fastfetch; and fastfetch; end")
    elif mode == "custom":
        text = _quote(greeting.get("text", ""))
        tool = greeting.get("tool", "none")
        font = greeting.get("font", "")
        if tool in ("figlet", "toilet") and font:
            # Render as ASCII art at greeting time; fall back to plain echo if the tool is missing.
            lines.append(
                f"function fish_greeting; if type -q {tool}; "
                f"{tool} -f '{font}' -w 1000 '{text}'; else; echo '{text}'; end; end"
            )
        else:
            lines.append(f"function fish_greeting; echo '{text}'; end")

    for abbr in settings.get("abbreviations", []):
        name = abbr.get("name", "").strip()
        expansion = abbr.get("expansion", "").strip()
        if name and expansion:
            lines.append(f"abbr -a -- {name} '{_quote(expansion)}'")

    lines.append(END)
    return "\n".join(lines)


def write_block(settings):
    """Insert or replace FTT's managed block in config.fish."""
    content = ""
    if os.path.isfile(CONFIG):
        with open(CONFIG, encoding="utf-8") as f:
            content = f.read()

    block = render_block(settings)
    if START in content and END in content:
        pre = content.split(START)[0].rstrip("\n")
        post = content.split(END, 1)[1].lstrip("\n")
        new = pre + "\n\n" + block + ("\n" + post if post else "\n")
    else:
        new = (content.rstrip("\n") + "\n\n" if content.strip() else "") + block + "\n"

    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    with open(CONFIG, "w", encoding="utf-8") as f:
        f.write(new)


def apply_async(settings, on_done):
    """Snapshot, then write the managed block off the UI thread; call on_done(Result)."""

    def worker():
        backup = ftt_fisher.ensure_snapshot()
        try:
            write_block(settings)
            on_done(ftt_fisher.Result(True, "", backup))
        except OSError as exc:
            on_done(ftt_fisher.Result(False, str(exc), backup))

    threading.Thread(target=worker, daemon=True).start()

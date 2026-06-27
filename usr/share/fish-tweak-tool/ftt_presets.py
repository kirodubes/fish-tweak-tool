"""Presets for fish-tweak-tool (M4) — one-click shell looks.

A preset bundles a prompt, plugins, theme and greeting into a single named
recipe. Applying one snapshots the config, writes the greeting into the managed
block, then runs ONE visible command that installs the plugins,
sets the prompt (removing any other framework first) and applies the theme.
"""

import threading

import ftt_fisher
import ftt_managed
import ftt_prompt
import ftt_theme

# Each preset: name + a one-line summary + the components it sets.
# prompt is ("default",) | ("builtin", name) | ("framework", install-spec).
PRESETS = [
    {
        "name": "Kiro",
        "summary": "Tide prompt · Nord theme · fzf + autopair + sponge · fastfetch greeting",
        "prompt": ("framework", "IlanCosman/tide@v6"),
        "theme": "nord",
        "variant": "dark",
        "plugins": ["PatrickF1/fzf.fish", "jorgebucaran/autopair.fish", "meaningful-ooo/sponge"],
        "greeting": {"mode": "fastfetch", "text": ""},
    },
    {
        "name": "Minimal",
        "summary": "Pure prompt · default theme · autopair only · no greeting",
        "prompt": ("framework", "pure-fish/pure"),
        "theme": "default",
        "variant": "dark",
        "plugins": ["jorgebucaran/autopair.fish"],
        "greeting": {"mode": "off", "text": ""},
    },
    {
        "name": "Full",
        "summary": "Tide prompt · Dracula theme · all four plugins · fastfetch greeting",
        "prompt": ("framework", "IlanCosman/tide@v6"),
        "theme": "dracula",
        "variant": "dark",
        "plugins": [
            "PatrickF1/fzf.fish",
            "jorgebucaran/autopair.fish",
            "meaningful-ooo/sponge",
            "nickeb96/puffer-fish",
        ],
        "greeting": {"mode": "fastfetch", "text": ""},
    },
]


def _build_command(preset, frameworks):
    """Build the single visible shell command for a preset's plugins/prompt/theme."""
    parts = []

    plugins = preset.get("plugins") or []
    if plugins:
        parts.append("fisher install " + " ".join(plugins))

    # Prompt: remove any installed framework (by exact name), clear prompt files, set chosen.
    bases = {key.lower() for key, _ in frameworks}
    for name in ftt_fisher.list_installed():
        if name.split("@")[0].lower() in bases:
            parts.append(f"fisher remove {name}")
    parts.append("rm -f " + " ".join(ftt_prompt.PROMPT_FUNCTION_FILES))
    prompt = preset.get("prompt", ("default",))
    if prompt[0] == "framework":
        parts.append(f"fisher install {prompt[1]}")
    elif prompt[0] == "builtin":
        parts.append(f"echo y | fish_config prompt save {prompt[1]}")

    theme = preset.get("theme")
    if theme:
        flag = ""
        if ftt_theme.is_color_theme_aware(theme):
            flag = f"--color-theme={preset.get('variant', 'dark')} "
        parts.append(f"echo y | fish_config theme save {flag}{theme}")

    return "; ".join(parts)


def apply_preset_async(preset, frameworks, on_done):
    """Apply a preset off the UI thread; call on_done(Result)."""

    def worker():
        backup = ftt_fisher.ensure_snapshot()
        ftt_managed.write_block(
            {"greeting": preset.get("greeting", {"mode": "keep"})}
        )
        ok, message = ftt_fisher.run_visibly(_build_command(preset, frameworks))
        on_done(ftt_fisher.Result(ok, message, backup))

    threading.Thread(target=worker, daemon=True).start()

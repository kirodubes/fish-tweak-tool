"""Built-in prompt selection for fish-tweak-tool.

Wraps ``fish_config prompt`` — fish's own manager for the ~13 sample prompts.
Choosing one writes ``~/.config/fish/functions/fish_prompt.fish`` (via
``fish_config prompt save``), which fish owns. Installable prompt *frameworks*
(Tide, Hydro, Pure) go through :mod:`ftt_fisher` instead.
"""

import ftt_fisher


def list_builtin():
    """Return the list of built-in prompt names (fish_config prompt list)."""
    rc, out, _ = ftt_fisher.run_fish("fish_config prompt list")
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def apply_builtin_async(name, on_done, snapshot=False):
    """Choose and persist a built-in prompt off the UI thread; call on_done(Result)."""
    ftt_fisher.run_async(
        f"fish_config prompt choose {name}; and fish_config prompt save",
        on_done,
        snapshot,
    )

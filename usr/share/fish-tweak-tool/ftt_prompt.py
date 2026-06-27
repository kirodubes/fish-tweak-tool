"""Built-in prompt selection for fish-tweak-tool.

Wraps ``fish_config prompt`` — fish's own manager for the ~13 sample prompts.
Choosing one writes ``~/.config/fish/functions/fish_prompt.fish`` (via
``fish_config prompt save``), which fish owns. Installable prompt *frameworks*
(Tide, Hydro, Pure) go through :mod:`ftt_fisher` instead.
"""

import ftt_fisher

# A prompt framework wants to own these files, but a built-in prompt (or a
# previous framework) may already have written them — fisher then refuses to
# install. We clear them first so switching prompts always works.
_PROMPT_FUNCTION_FILES = [
    "~/.config/fish/functions/fish_prompt.fish",
    "~/.config/fish/functions/fish_right_prompt.fish",
    "~/.config/fish/functions/fish_mode_prompt.fish",
]


def list_builtin():
    """Return the list of built-in prompt names (fish_config prompt list)."""
    rc, out, _ = ftt_fisher.run_fish("fish_config prompt list")
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def apply_builtin_async(name, on_done, snapshot=False):
    """Choose and persist a built-in prompt off the UI thread; call on_done(Result).

    `fish_config prompt save <name>` selects and saves in one step, but gates on
    an interactive "Overwrite? [y/N]" read; piping `y` confirms it non-interactively.
    """
    ftt_fisher.run_async(
        f"echo y | fish_config prompt save {name}",
        on_done,
        snapshot,
    )


def install_framework_async(install_spec, on_done, snapshot=True):
    """Install a prompt framework, clearing any conflicting prompt files first.

    fish has one prompt slot, so a built-in prompt or previous framework leaves a
    `fish_prompt.fish` that blocks `fisher install`. We `rm -f` the prompt files
    (already captured in the pre-install snapshot) then install — all shown in
    the visible terminal.
    """
    files = " ".join(_PROMPT_FUNCTION_FILES)
    ftt_fisher.run_async(f"rm -f {files}; and fisher install {install_spec}", on_done, snapshot)


def reset_default_async(installed_frameworks, on_done, snapshot=True):
    """Revert to fish's built-in default prompt off the UI thread; call on_done(Result).

    Removes any installed prompt framework (so its files and fisher entry go),
    then deletes any leftover prompt function files (from a built-in prompt) so
    fish falls back to its compiled-in default — all shown in the visible terminal.
    """
    parts = [f"fisher remove {key}" for key in installed_frameworks]
    parts.append(f"rm -f {' '.join(_PROMPT_FUNCTION_FILES)}")
    ftt_fisher.run_async("; and ".join(parts), on_done, snapshot)

"""Prompt selection for fish-tweak-tool — one prompt at a time.

fish has a single prompt slot, so choosing a prompt is mutually exclusive:
applying one removes any installed framework and clears the prompt function
files, then sets the chosen prompt. A built-in style goes through
``fish_config prompt save``; a framework through ``fisher install``.
"""

import ftt_fisher

# A prompt framework wants to own these files, but a built-in prompt (or a
# previous framework) may already have written them. Clearing them first makes
# switching prompts always work.
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


def set_prompt_async(choice, frameworks, on_done, snapshot=True):
    """Apply a single prompt exclusively, off the UI thread; call on_done(Result).

    `choice` is one of:
      ("default",)         — fish's built-in default (just clear everything)
      ("builtin", name)    — a fish_config built-in style
      ("framework", spec)  — install a prompt framework

    `frameworks` is the list of (key, spec); any currently-installed one is
    removed first so only the chosen prompt remains. The whole thing runs as one
    visible command, and the final command's status is the reported result.
    """
    files = " ".join(_PROMPT_FUNCTION_FILES)

    framework_bases = {key.lower() for key, _ in frameworks}

    def build():
        # fisher lists (and removes) plugins by their exact name, which may carry a
        # version tag (Tide → "ilancosman/tide@v6"). Match a framework by its base
        # (before "@") but remove using the exact installed name.
        installed = ftt_fisher.list_installed()
        removes = [name for name in installed if name.split("@")[0].lower() in framework_bases]
        parts = [f"fisher remove {name}" for name in removes]
        parts.append(f"rm -f {files}")
        if choice[0] == "builtin":
            parts.append(f"echo y | fish_config prompt save {choice[1]}")
        elif choice[0] == "framework":
            parts.append(f"fisher install {choice[1]}")
        return "; ".join(parts)

    ftt_fisher.run_async(build, on_done, snapshot)

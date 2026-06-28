"""App preferences for fish-tweak-tool (window size, etc.).

This module holds only the tool's *own* settings under
``~/.config/fish-tweak-tool/``. It does NOT touch the user's fish config
(``~/.config/fish/``) — that comes with the M1+ orchestration milestones.
"""

import json
import os

PREFS_PATH = os.path.expanduser("~/.config/fish-tweak-tool/prefs.json")


def load_prefs():
    """Return the saved preferences dict, or an empty dict if none exist."""
    if not os.path.isfile(PREFS_PATH):
        return {}
    try:
        with open(PREFS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_prefs(prefs):
    """Write the preferences dict to disk, creating the config dir if needed."""
    os.makedirs(os.path.dirname(PREFS_PATH), exist_ok=True)
    with open(PREFS_PATH, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=2)


def update_prefs(updates):
    """Merge updates into the on-disk prefs and save; return the merged dict.

    Always reads fresh from disk so one tab's save never clobbers keys another
    tab wrote earlier in the session (each tab caches prefs at startup).
    """
    prefs = load_prefs()
    prefs.update(updates)
    save_prefs(prefs)
    return prefs

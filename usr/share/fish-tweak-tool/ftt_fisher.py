"""Fisher orchestration + shared fish-command primitives for fish-tweak-tool.

`fisher` is a fish *function*, not a binary, so every call shells out through
``fish -c``. Mutating calls run off the UI thread and report a :class:`Result`
instead of raising — fish orchestration needs the network and can fail (offline,
bad plugin) for reasons the UI must surface rather than crash on.

The generic helpers (:func:`run_fish`, :func:`run_async`, :func:`ensure_snapshot`)
are reused by the prompt module too.
"""

import datetime
import os
import re
import shutil
import subprocess
import threading

import log

FISH_CONFIG_DIR = os.path.expanduser("~/.config/fish")
BACKUP_DIR = os.path.expanduser("~/.config/fish-tweak-tool/backups")

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_snapshot_taken = False


class Result:
    """Outcome of a fish orchestration operation."""

    def __init__(self, ok, message="", backup=None):
        self.ok = ok
        self.message = message
        self.backup = backup


def run_fish(command, timeout=180):
    """Run a fish -c command; return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            ["fish", "-c", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "operation timed out"
    except FileNotFoundError:
        return 127, "", "fish not found"


def ensure_snapshot():
    """Back up ~/.config/fish once per process, before the first mutation."""
    global _snapshot_taken
    if _snapshot_taken:
        return None
    path = _snapshot_fish_config()
    _snapshot_taken = True
    return path


def _snapshot_fish_config():
    if not os.path.isdir(FISH_CONFIG_DIR):
        return None
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(BACKUP_DIR, f"fish-{stamp}")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    shutil.copytree(FISH_CONFIG_DIR, dest, dirs_exist_ok=True)
    log.log_info(f"Backed up fish config to {dest}")
    return dest


def run_async(command, on_done, snapshot=False):
    """Run a fish command off the UI thread; call on_done(Result)."""

    def worker():
        backup = ensure_snapshot() if snapshot else None
        rc, out, err = run_fish(command)
        on_done(Result(rc == 0, _clean(err or out), backup))

    threading.Thread(target=worker, daemon=True).start()


def _clean(text):
    """Strip ANSI codes and return the last meaningful line, for UI display."""
    lines = [_ANSI_RE.sub("", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return lines[-1] if lines else ""


# ── fisher-specific ──────────────────────────────────────────────────────────


def is_fisher_available():
    """Return True if the fisher command is available inside fish."""
    rc, _, _ = run_fish("type -q fisher")
    return rc == 0


def list_installed():
    """Return the set of installed fisher plugin names (e.g. 'PatrickF1/fzf.fish')."""
    rc, out, _ = run_fish("fisher list")
    if rc != 0:
        return set()
    return {line.strip() for line in out.splitlines() if line.strip()}


def install_async(plugin, on_done, snapshot=False):
    """Install a plugin via fisher off the UI thread; call on_done(Result)."""
    run_async(f"fisher install {plugin}", on_done, snapshot)


def remove_async(plugin, on_done, snapshot=False):
    """Remove a plugin via fisher off the UI thread; call on_done(Result)."""
    run_async(f"fisher remove {plugin}", on_done, snapshot)

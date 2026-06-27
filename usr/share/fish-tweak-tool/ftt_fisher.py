"""Fisher orchestration for fish-tweak-tool.

Wraps the `fisher` plugin manager. `fisher` is a fish *function*, not a binary,
so every call shells out through ``fish -c``. Mutating calls run off the UI
thread and report a :class:`Result` instead of raising — fisher needs the
network and can fail (offline, bad plugin) for reasons the UI must surface
rather than crash on.
"""

import datetime
import os
import re
import shutil
import subprocess
import threading

import log

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

FISH_CONFIG_DIR = os.path.expanduser("~/.config/fish")
BACKUP_DIR = os.path.expanduser("~/.config/fish-tweak-tool/backups")


class Result:
    """Outcome of a fisher operation."""

    def __init__(self, ok, message="", backup=None):
        self.ok = ok
        self.message = message
        self.backup = backup


def _run_fish(command, timeout=180):
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


def is_fisher_available():
    """Return True if the fisher command is available inside fish."""
    rc, _, _ = _run_fish("type -q fisher")
    return rc == 0


def list_installed():
    """Return the set of installed fisher plugin names (e.g. 'PatrickF1/fzf.fish')."""
    rc, out, _ = _run_fish("fisher list")
    if rc != 0:
        return set()
    return {line.strip() for line in out.splitlines() if line.strip()}


def snapshot_fish_config():
    """Back up ~/.config/fish to a timestamped dir; return its path, or None."""
    if not os.path.isdir(FISH_CONFIG_DIR):
        return None
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(BACKUP_DIR, f"fish-{stamp}")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    shutil.copytree(FISH_CONFIG_DIR, dest, dirs_exist_ok=True)
    log.log_info(f"Backed up fish config to {dest}")
    return dest


def install_async(plugin, on_done, snapshot=False):
    """Install a plugin via fisher off the UI thread; call on_done(Result)."""
    _run_async(f"fisher install {plugin}", on_done, snapshot)


def remove_async(plugin, on_done, snapshot=False):
    """Remove a plugin via fisher off the UI thread; call on_done(Result)."""
    _run_async(f"fisher remove {plugin}", on_done, snapshot)


def _run_async(command, on_done, snapshot):
    def worker():
        backup = snapshot_fish_config() if snapshot else None
        rc, out, err = _run_fish(command)
        on_done(Result(rc == 0, _clean(err or out), backup))

    threading.Thread(target=worker, daemon=True).start()


def _clean(text):
    """Strip ANSI codes and return the last meaningful line, for UI display."""
    lines = [_ANSI_RE.sub("", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return lines[-1] if lines else ""

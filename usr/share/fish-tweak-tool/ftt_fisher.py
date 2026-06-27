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
import tempfile
import threading

import log

FISH_CONFIG_DIR = os.path.expanduser("~/.config/fish")
BACKUP_DIR = os.path.expanduser("~/.config/fish-tweak-tool/backups")

# Terminals (preferred first) used to run mutating commands *visibly*, so the
# user always sees the exact command changing their system — no black box. All
# of these take `-e <cmd>`. Alacritty is the Kiro default.
_TERMINALS = ("alacritty", "xterm")

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


def snapshot_now():
    """Force a backup of ~/.config/fish regardless of the once-per-process guard."""
    return _snapshot_fish_config()


def list_backups():
    """Return existing backup directories, newest first."""
    if not os.path.isdir(BACKUP_DIR):
        return []
    paths = [os.path.join(BACKUP_DIR, name) for name in os.listdir(BACKUP_DIR)]
    return sorted((p for p in paths if os.path.isdir(p)), reverse=True)


def restore_backup(path):
    """Copy a backup directory back over ~/.config/fish."""
    shutil.copytree(path, FISH_CONFIG_DIR, dirs_exist_ok=True)


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
    """Run a *mutating* fish command off the UI thread; call on_done(Result).

    `command` is a string, or a callable returning the command string (built in
    the worker thread — handy when it depends on a query like `fisher list`).
    The command runs in a visible terminal (Alacritty) so the user sees exactly
    what is changing their system — never a black box. Read-only queries use
    run_fish directly and stay silent.
    """

    def worker():
        backup = ensure_snapshot() if snapshot else None
        resolved = command() if callable(command) else command
        ok, message = _run_visibly(resolved)
        on_done(Result(ok, message, backup))

    threading.Thread(target=worker, daemon=True).start()


def _find_terminal():
    """Return the first available terminal emulator, or None."""
    for term in _TERMINALS:
        if shutil.which(term):
            return term
    return None


def _terminal_script(command, status_path):
    """Build the fish script the terminal runs: echo the command, run it, save status."""
    display = command.replace("\\", "\\\\").replace("'", "\\'")
    return (
        "set_color cyan\n"
        'echo "Fish Tweak Tool is running this command on your system:"\n'
        "set_color normal\n"
        "echo\n"
        f"echo '    {display}'\n"
        "echo\n"
        f"{command}\n"
        "set -l _ftt_status $status\n"
        f"echo $_ftt_status > '{status_path}'\n"
        "echo\n"
        "if test $_ftt_status -eq 0\n"
        "    set_color green\n"
        '    echo "Done (success). Press enter to close."\n'
        "else\n"
        "    set_color red\n"
        '    echo "Failed (exit $_ftt_status). Press enter to close."\n'
        "end\n"
        "set_color normal\n"
        "read\n"
    )


def _run_visibly(command):
    """Run a mutating command in a visible terminal; return (ok, message).

    Falls back to a silent in-process run only when no terminal is available.
    """
    log.log_info(f"$ {command}")
    term = _find_terminal()
    if not term:
        rc, out, err = run_fish(command)
        return rc == 0, _clean(err or out)

    script_fd, script_path = tempfile.mkstemp(prefix="ftt-", suffix=".fish")
    status_fd, status_path = tempfile.mkstemp(prefix="ftt-status-")
    os.close(status_fd)
    try:
        with os.fdopen(script_fd, "w", encoding="utf-8") as f:
            f.write(_terminal_script(command, status_path))
        subprocess.run([term, "-e", "fish", script_path], timeout=1800)
        with open(status_path, encoding="utf-8") as f:
            rc = int(f.read().strip() or "1")
        return rc == 0, ""
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    finally:
        for path in (script_path, status_path):
            try:
                os.unlink(path)
            except OSError:
                pass


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

"""A sandboxed Python execution tool, shared by every challenge category.

The model often needs real computation: encoding, hashing, signing a forged token,
brute-forcing a weak secret, breaking a cipher. This runs its code in an isolated
subprocess:

- a fresh temp directory as cwd and HOME (relative file I/O stays contained);
- `python3 -I` so ambient environment and user site-packages are ignored (the venv's
  own packages remain importable);
- no network: on macOS via `sandbox-exec (deny network*)`, on Linux via a private
  network namespace when `unshare -n` is permitted;
- CPU-time and file-size rlimits plus a wall-clock timeout.

The venv interpreter is reused, so libraries installed for a category (pycryptodome,
sympy, ...) are available inside the sandbox.
"""

import platform
import resource
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .agent import Tool

DEFAULT_TIMEOUT = 20
MAX_OUTPUT_CHARS = 20_000
CPU_SECONDS = 15
MAX_FILE_BYTES = 10 * 1024 * 1024


def _set_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE_BYTES, MAX_FILE_BYTES))
    # RLIMIT_AS is skipped on macOS: Python reserves large address space up front and
    # a cap there crashes the interpreter on startup rather than the runaway code.
    if platform.system() == "Linux":
        two_gb = 2 * 1024 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (two_gb, two_gb))


def _wrap_no_network(command: list[str]) -> list[str]:
    system = platform.system()
    if system == "Darwin" and shutil.which("sandbox-exec"):
        # Allow everything the interpreter needs, but deny all networking.
        return ["sandbox-exec", "-p", "(version 1)(allow default)(deny network*)", *command]
    if system == "Linux" and shutil.which("unshare"):
        # Best effort: a private net namespace has no route out. Needs user namespaces;
        # if unprivileged, this fails fast and the caller sees the error.
        return ["unshare", "--net", "--", *command]
    return command


def run_python(code: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    workdir = Path(tempfile.mkdtemp(prefix="ctf-sbx-"))
    script = workdir / "snippet.py"
    script.write_text(code)
    command = _wrap_no_network([sys.executable, "-I", str(script)])
    env = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": str(workdir),
        "TMPDIR": str(workdir),
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }
    try:
        proc = subprocess.run(
            command,
            cwd=workdir,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            preexec_fn=_set_limits,
        )
    except subprocess.TimeoutExpired:
        return f"[timed out after {timeout}s]"
    except Exception as error:  # sandbox wrapper missing/unusable, etc.
        return f"[could not run: {error}]"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    out = proc.stdout
    if proc.stderr:
        out += ("\n" if out else "") + "[stderr]\n" + proc.stderr
    if len(out) > MAX_OUTPUT_CHARS:
        out = out[:MAX_OUTPUT_CHARS] + f"\n[truncated, {len(out)} chars]"
    return f"[exit {proc.returncode}]\n{out}" if out.strip() else f"[exit {proc.returncode}, no output]"


def run_command(argv: list[str], stdin: str = "", timeout: int = DEFAULT_TIMEOUT) -> str:
    """Run an arbitrary command (e.g. a compiled challenge binary) in the same sandbox
    run_python uses: no network, CPU/file rlimits, a wall-clock timeout, and an ephemeral
    temp cwd/HOME. `stdin` is fed to the process; stdout/stderr/exit code come back as text.
    Used by the reverse category to run a crackme binary."""
    workdir = Path(tempfile.mkdtemp(prefix="ctf-sbx-"))
    command = _wrap_no_network([str(a) for a in argv])
    env = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": str(workdir),
        "TMPDIR": str(workdir),
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }
    try:
        proc = subprocess.run(
            command,
            cwd=workdir,
            env=env,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout,
            preexec_fn=_set_limits,
        )
    except subprocess.TimeoutExpired:
        return f"[timed out after {timeout}s]"
    except Exception as error:  # sandbox wrapper missing/unusable, etc.
        return f"[could not run: {error}]"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    out = proc.stdout
    if proc.stderr:
        out += ("\n" if out else "") + "[stderr]\n" + proc.stderr
    if len(out) > MAX_OUTPUT_CHARS:
        out = out[:MAX_OUTPUT_CHARS] + f"\n[truncated, {len(out)} chars]"
    return f"[exit {proc.returncode}]\n{out}" if out.strip() else f"[exit {proc.returncode}, no output]"


def python_tool() -> Tool:
    return Tool(
        name="run_python",
        description=(
            "Run Python 3 code in an isolated subprocess (no network, time-limited, "
            "ephemeral temp dir) and return its stdout/stderr. Use it for anything that "
            "needs real computation: base64/hex, hashing and HMAC, signing or forging "
            "tokens, brute-forcing a weak secret, or breaking a cipher. Print your results."
        ),
        parameters={
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Python 3 source to run"}},
            "required": ["code"],
        },
        handler=lambda args: run_python(args.get("code", "")),
    )

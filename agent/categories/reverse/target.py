"""Reverse category plumbing: the compiled crackme the agent attacks."""

from dataclasses import dataclass
import shutil
from pathlib import Path


@dataclass
class ReverseTarget:
    """A compiled crackme binary in its own temp directory. `binary` is the path the
    agent's tools (disassemble, run_binary) are bound to; the agent never sees it directly.
    cleanup() removes the temp directory."""

    binary: Path
    workdir: Path

    def cleanup(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)

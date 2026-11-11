"""A persistent sandbox directory for large artifacts. The challenge writes files here; the
agent's run_python uses it as cwd, so it reads the files across calls — no base64 blob in the
prompt. The harness cleans it up after the solve."""

import shutil
import tempfile
from pathlib import Path


class Workspace:
    def __init__(self, files: dict[str, bytes] | None = None):
        self.dir = Path(tempfile.mkdtemp(prefix="ctf-ws-"))
        for name, data in (files or {}).items():
            (self.dir / name).write_bytes(data)

    def cleanup(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)

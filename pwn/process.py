"""The pwn category's simulated target process (the HARNESS). Each challenge subclasses
Process to model a vulnerable program in virtual memory. The agent pokes it through the
`send_input` tool (see tools/process.py) — it never imports this module.

Split, as everywhere:
  - Process (+ subclasses in challenges/)  = HARNESS. Holds the flag and virtual memory.
  - tools/process.py: process_tool(proc)   = the agent capability bound to one target.
"""


class Process:
    """A simulated target. send(data) feeds one payload to the program and returns whatever
    it prints. Single-shot by default; stateful subclasses may override as needed."""

    def send(self, data: bytes) -> str:
        raise NotImplementedError

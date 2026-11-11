"""Use-after-free on a toy heap. Free a chunk, allocate a new chunk that reuses its memory,
then write through the dangling pointer to overwrite a function pointer with win()."""

from pwn.process import Process

WIN_ADDR = 0x401176

DESCRIPTION = f"""A toy heap with a menu (send one command per line):

    alloc <i>          allocate chunk i (its first 8 bytes hold a function pointer)
    free <i>           free chunk i — the pointer stays usable (use-after-free)
    write <i> <hex>    write bytes to chunk i, even if it's freed
    trigger <i>        call the function pointer at the start of chunk i

The allocator reuses freed memory: after you free chunk 0, the next alloc reuses its slot.
win() is at {hex(WIN_ADDR)}. Overwrite a function pointer with win() (pack little-endian with
struct.pack('<Q', ...)) and trigger it."""


class _HeapProcess(Process):
    def __init__(self, flag: str) -> None:
        self.flag = flag
        self.slot = bytearray(16)
        self.slot[0:8] = (0x402000).to_bytes(8, "little")  # fn ptr -> some safe function
        self.chunks: dict[int, bytearray] = {}

    def send(self, data: bytes) -> str:
        parts = data.decode("latin1").strip().split()
        if not parts:
            return "?\n"
        op = parts[0]
        if op == "alloc":
            idx = int(parts[1])
            self.chunks[idx] = self.slot  # toy allocator: all chunks alias the one slot
            return f"allocated chunk {idx}\n"
        if op == "free":
            idx = int(parts[1])
            return f"freed chunk {idx} (dangling pointer)\n"
        if op == "write":
            idx = int(parts[1])
            data = bytes.fromhex(parts[2])
            self.chunks.get(idx, self.slot)[0 : len(data)] = data
            return f"wrote {len(data)} bytes to chunk {idx}\n"
        if op == "trigger":
            idx = int(parts[1])
            fp = int.from_bytes(self.chunks.get(idx, self.slot)[0:8], "little")
            if fp == WIN_ADDR:
                return f"You win!\n{self.flag}\n"
            return f"called {hex(fp)}\n"
        return "?\n"


def make(flag: str) -> Process:
    return _HeapProcess(flag)

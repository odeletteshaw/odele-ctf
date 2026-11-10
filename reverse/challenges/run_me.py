"""Floor: the binary just XOR-decodes the flag and prints it when run. This validates the
whole reverse pipeline (compile -> sandbox-run -> flag extraction) before any real reversing.
The flag is XOR'd so it is not a plaintext string in the binary — the point is to run it."""

from reverse.challenges._common import compile_c, decode_loop, xor_c_array

_K = 0xAA

DESCRIPTION = "Run the binary and read what it prints."


def make(flag: str):
    enc = bytes(b ^ _K for b in flag.encode())
    src = (
        "#include <stdio.h>\n"
        f"static const unsigned char enc[] = {{{xor_c_array(enc)}}};\n"
        "int main(void) {\n"
        + decode_loop(_K)
        + "    return 0;\n"
        "}\n"
    )
    return compile_c(src)

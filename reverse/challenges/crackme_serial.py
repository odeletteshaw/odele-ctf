"""Keygen: the flag is XOR-obfuscated and only printed after a serial passes a weighted
checksum. The check's formula (sum of serial[i] * (i+1)) and its target value are both visible
in the disassembly — a `for` loop accumulating `buf[i] * (i + 1)` and a compare against a
constant. Any serial with the right sum unlocks the flag, so reverse the formula, build a valid
serial in run_python, and run it."""

from reverse.challenges._common import compile_c, decode_loop, xor_c_array

_K = 0xAA
_SERIAL = "KEYGEN-2024"
_TARGET = sum(ord(c) * (i + 1) for i, c in enumerate(_SERIAL))

DESCRIPTION = (
    "A keygen: the program reads a serial number and only prints the flag when the serial is "
    "valid. Reverse the validation check to produce a working serial."
)


def make(flag: str):
    enc = bytes(b ^ _K for b in flag.encode())
    src = (
        "#include <stdio.h>\n"
        "#include <string.h>\n"
        f"static const unsigned char enc[] = {{{xor_c_array(enc)}}};\n"
        "int main(void) {\n"
        "    char buf[64];\n"
        "    if (!fgets(buf, sizeof buf, stdin)) return 1;\n"
        '    buf[strcspn(buf, "\\n")] = 0;\n'
        "    int acc = 0;\n"
        "    for (int i = 0; buf[i]; i++) acc += buf[i] * (i + 1);\n"
        f'    if (acc != {_TARGET}) {{ puts("denied"); return 1; }}\n'
        + decode_loop(_K)
        + "    return 0;\n"
        "}\n"
    )
    return compile_c(src)

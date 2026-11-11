"""Symbolic solving: the flag is the unique 30-byte input whose 3-round mixed output equals
an embedded target. The mix is a bijection — per-byte `*7+13`, then a cyclic coupling
`x[i] + 2*x[i+1]` — so brute force (2^240) is hopeless and manual inversion means solving a
30x30 system mod 256. The intended path is to read the mix + target from the disassembly and
recover the flag with z3 (available in run_python)."""

from reverse.challenges._common import compile_c, xor_c_array

_N = 30


def _mix(data: bytes) -> bytes:
    x = list(data)
    for _ in range(3):
        x = [(b * 7 + 13) & 0xFF for b in x]
        x = [(x[i] + 2 * x[(i + 1) % _N]) & 0xFF for i in range(_N)]
    return bytes(x)


DESCRIPTION = (
    "A checker reads a 30-byte input, runs it through a mixing function three times, and "
    "prints 'Correct!' only when the result matches an embedded target. The input is the "
    "flag. The mix couples all 30 bytes, so brute force is out — solve for the input."
)


def make(flag: str):
    target = _mix(flag.encode())
    src = (
        "#include <stdio.h>\n"
        "#include <string.h>\n"
        f"static const unsigned char target[{_N}] = {{{xor_c_array(target)}}};\n"
        "static void mix(unsigned char *x) {\n"
        "    unsigned char t[30];\n"
        "    for (int r = 0; r < 3; r++) {\n"
        "        for (int i = 0; i < 30; i++) x[i] = (x[i] * 7 + 13) & 0xFF;\n"
        "        for (int i = 0; i < 30; i++) t[i] = (x[i] + 2 * x[(i + 1) % 30]) & 0xFF;\n"
        "        for (int i = 0; i < 30; i++) x[i] = t[i];\n"
        "    }\n"
        "}\n"
        "int main(void) {\n"
        "    char buf[64];\n"
        "    unsigned char x[30];\n"
        "    if (!fgets(buf, sizeof buf, stdin)) return 1;\n"
        '    buf[strcspn(buf, "\\n")] = 0;\n'
        '    if (strlen(buf) != 30) { puts("wrong"); return 1; }\n'
        "    for (int i = 0; i < 30; i++) x[i] = (unsigned char)buf[i];\n"
        "    mix(x);\n"
        '    for (int i = 0; i < 30; i++) if (x[i] != target[i]) { puts("wrong"); return 1; }\n'
        '    puts("Correct!");\n'
        "    return 0;\n"
        "}\n"
    )
    return compile_c(src)

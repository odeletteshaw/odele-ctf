"""A tiny bytecode VM checks the flag. Each input byte is transformed by a program of VM
operations (mul/add/xor, read from a bytecode array), then compared to an embedded target.
Reverse the interpreter + program to recover the flag."""

from reverse.challenges._common import compile_c, xor_c_array

DESCRIPTION = (
    "The checker interprets a small bytecode program: each input byte runs through a fixed "
    "sequence of VM ops (mul/add/xor) then is compared to a target. Reverse the program."
)


def make(flag: str):
    # x = ((x * 7 + 13) ^ 0x5a) & 0xff
    target = bytes(((b * 7 + 13) ^ 0x5A) & 0xFF for b in flag.encode())
    src = (
        "#include <stdio.h>\n"
        "#include <string.h>\n"
        "/* VM program: op,operand pairs. 0x01=mul 0x02=add 0x03=xor */\n"
        "static const unsigned char prog[] = {0x01,0x07, 0x02,0x0d, 0x03,0x5a};\n"
        f"static const unsigned char target[30] = {{{xor_c_array(target)}}};\n"
        "int main(void) {\n"
        "    char buf[64];\n"
        "    if (!fgets(buf, sizeof buf, stdin)) return 1;\n"
        '    buf[strcspn(buf, "\\n")] = 0;\n'
        '    if (strlen(buf) != 30) { puts("wrong"); return 1; }\n'
        "    for (int i = 0; i < 30; i++) {\n"
        "        unsigned char x = buf[i];\n"
        "        for (int p = 0; p < (int)sizeof(prog); p += 2) {\n"
        "            switch (prog[p]) {\n"
        "                case 0x01: x = (x * prog[p+1]) & 0xff; break;\n"
        "                case 0x02: x = (x + prog[p+1]) & 0xff; break;\n"
        "                case 0x03: x = (x ^ prog[p+1]) & 0xff; break;\n"
        "            }\n"
        "        }\n"
        '        if (x != target[i]) { puts("wrong"); return 1; }\n'
        "    }\n"
        '    puts("Correct!");\n'
        "    return 0;\n"
        "}\n"
    )
    return compile_c(src)

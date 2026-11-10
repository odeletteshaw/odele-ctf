# Pwn — TODO

⚠ **先建工具**:`tools/process.py` —— 在沙箱里运行目标 ELF 并 send/recv 其 stdin/stdout;
venv 里装 `pwntools`。然后照 web/crypto 实现 `pwn/agent.py: solve_pwn()`。

hermetic 方案:附一个有漏洞的二进制,agent 本地沙箱里利用,读 flag 文件 / 拿 shell。

## 工具清单
- [ ] `tools/process.py`(run + send/recv,超时,隔离)
- [ ] 安装 pwntools
- [ ] `pwn/agent.py` 的 solve_pwn + `pwn/evaluate.py`

## 子方向(靶题)
- [ ] 栈溢出 ret2win(覆盖返回地址跳到 win 函数)
- [ ] 格式化字符串(泄露 + 任意写)
- [ ] canary 绕过 / ret2libc / ROP 链
- [ ] 堆:UAF / double-free / tcache
- [ ] shellcode 注入 / ret2shellcode

> 起步建议:ret2win(最简单、最经典),先把 process 工具跑通。

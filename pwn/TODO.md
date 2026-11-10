# Pwn / 二进制利用 — TODO

✅ **已就绪**。做法(hermetic,同 web 模拟漏洞):不跑真实二进制/shell,而是**模拟一个有漏洞
的目标进程**——虚拟栈/内存、玩具 printf。agent 用新工具 `send_input` 发 payload(hex 或 text)、
拿回程序输出,用 `run_python` 算偏移、打包地址、解码泄露。

## 已完成
- [x] `pwn/process.py`:`Process` 基类(harness,持有 flag + 虚拟内存)+ `process_tool`
      (agent 能力 `send_input`,接受 hex/text)
- [x] `pwn/agent.py`:`pwn_tools`(send_input + run_python)、`solve_pwn`、SYSTEM_PROMPT
- [x] `pwn/evaluate.py`
- [x] 三道题(源码可见、确定性,脚本验证可解 + 负向控制):
  - **overflow_auth** — 32 字节 buffer 溢出到相邻 `authorized`(地板)
  - **ret2win** — 溢出 64+8 覆盖返回地址为 win() 地址(64-bit 小端打包)
  - **format_leak** — 格式化字符串 `%p`/`%N$p` 泄露栈上的 flag,run_python 重组
- [x] 接入 `core/catalog.py`(ready)与 `gui/builder.py`(pwn 分支)

## 接口
`DESCRIPTION: str`(通常含源码片段 + 给定地址)+ `make(flag) -> Process`。
`Process.send(data: bytes) -> str` 模拟一次 payload 投喂。

## 以后可加
- [ ] 栈 canary 泄露 → 绕过;PIE/ASLR + 地址泄露再利用
- [ ] ret2libc / 简单 ROP 链(需模拟几个 gadget 与一个 system/execve 效果)
- [ ] 堆:use-after-free / tcache(模拟一个玩具分配器)
- [ ] 交互式多轮目标(菜单驱动),让 `Process` 有状态
- [ ] 整数溢出 / off-by-one

> 注:这些是**模拟**漏洞,不接触真实系统。要做「真·跑二进制」得另起一套受控沙箱
> (qemu/ptrace),成本和风险都高,暂不在 hermetic benchmark 范围内。

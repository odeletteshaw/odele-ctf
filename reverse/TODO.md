# Reverse / 逆向 — TODO

✅ **已就绪**。做法(hermetic,同 pwn 模拟漏洞):不反汇编第三方/恶意二进制,而是把**自己写的小 C
crackme 在 `make(flag)` 时用 clang 编译**,flag XOR 混淆编译进去。agent 用三个工具:
`disassemble`(`objdump -d -s`,反汇编 + 段数据)、`run_binary`(沙箱跑二进制、读输出)、
`run_python`(解码/求逆/构造输入)。

## 已完成
- [x] `reverse/target.py`:`ReverseTarget`(编译出的二进制 + 临时目录清理)
- [x] `reverse/challenges/_common.py`:出题侧 helper(`compile_c` 用 clang -O0 编译、
      `xor_c_array`、`decode_loop`);agent 永远碰不到
- [x] `reverse/agent.py`:`disassemble_tool` / `run_binary_tool` / `reverse_tools` /
      `solve_reverse` + SYSTEM_PROMPT(含 arm64 objdump 语法说明:立即数是十进制、`eor`=XOR、
      常量数据在 `__const`/`__cstring`)
- [x] `reverse/evaluate.py` + `reverse/test_offline.py`
- [x] `core/sandbox.py`:新增 `run_command(argv, stdin)`,与 run_python 同沙箱跑任意二进制
- [x] 四道题(脚本验证可解 + DeepSeek 全解):
  - **run_me** — 地板:二进制直接 XOR 解码打印 flag,验证「编译→沙箱跑→提取 flag」管线
  - **crackme_xor** — flag XOR 混淆 + strcmp 密码门;key 和 XOR 键都能从反汇编恢复
  - **crackme_serial** — keygen:加权和校验 `sum(s[i]*(i+1)) == TARGET`,构造合法 serial
  - **crackme_z3** — 符号求解:30 字节耦合变换(`*7+13` + 循环 `x[i]+2*x[i+1]`,3 轮),agent
    反汇编后用 z3 解出输入 = flag(3 次调用)
- [x] 接入 `core/catalog.py`(ready)、`gui/builder.py`(reverse 分支)、`gui/launch.py`

## 接口
`DESCRIPTION: str` + `make(flag) -> ReverseTarget`(一个编译好的二进制)。工具绑定到
`target.binary`,agent 看不到路径本身。

## 以后可加
- [ ] **真·angr 符号执行**:angr 9.x 装得上(`z3<5` + `pycparser 3.11`,不能装 3.12)但**在 arm64
      macOS 上跑不动 Mach-O 符号执行**(argv/stdin 全返回未约束值);要 x86_64 Linux ELF + lld
      交叉编译才行(lld 已 brew 装好)。当前用 **z3 直接符号求解**替代(见 crackme_z3),是 angr
      底层同款求解器。真 angr 留待 ELF 工具链。
- [ ] crackme:多步变换、位运算混合(现 `crackme_xor` 是单步 XOR)
- [ ] 自定义 VM / 字节码还原(玩具 VM)
- [ ] 加壳(UPX)脱壳 + 反调试绕过
- [ ] .pyc / Java / Go 二进制(需对应工具链)

> 注:二进制是我们自己在 make 时编译的小 crackme,跑在 run_python 同款沙箱(禁网 + rlimit)。
> 不反汇编第三方/恶意二进制,不碰真实系统。

# Reverse — TODO

⚠ **先建工具**:反汇编/反编译(objdump / radare2 / Ghidra headless)+ 可选**符号执行 angr**
(自动求"输入→flag")+ 沙箱跑二进制。然后实现 `reverse/agent.py: solve_reverse()`。

## 工具清单
- [ ] `tools/disasm.py`(objdump / r2 封装)
- [ ] 可选:`tools/symbolic.py`(angr)
- [ ] 复用沙箱跑二进制(已有 run_python,可扩 process 工具)
- [ ] solve_reverse + reverse/evaluate.py

## 子方向(靶题)
- [ ] crackme:静态分析校验逻辑,反推正确输入
- [ ] keygen:根据算法生成有效序列号
- [ ] 自定义 VM / 字节码还原
- [ ] 加壳(UPX)脱壳 + 反调试绕过
- [ ] .pyc / Java / Go 二进制

> 起步建议:简单 crackme(比较一个变换后的输入),angr 能直接秒。

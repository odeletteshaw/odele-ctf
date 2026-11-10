# odele-ctf 路线图

CTF 各大类(方向)与其下的具体子方向,标注**现状**和**所需工具**。设计原则见
[CLAUDE.md](CLAUDE.md):靶题 hermetic(虚拟化,不碰真实系统),工具是"能力"不是"解法"。

图例:✅ 已做 · ☐ 待做 · ⚠ 需新工具

**规划主线**:web/crypto 能持续扩充是因为工具齐备(`http_request` + `run_python`)。
pwn/reverse/forensics 卡在工具上——开这些大类前,得先给 agent 建对应的新工具。

---

## 1. Web  — 工具:http_request + run_python(齐)

| 方向 | 具体 | 状态 |
|------|------|------|
| 注入 | SQLi ✅ · 命令注入 ✅ · NoSQLi ✅ · SSTI ✅ · XXE ✅ · LFI ✅ · LDAP ✅ · CRLF ☐ | |
| 访问控制 | IDOR ✅ · 认证绕过 ✅ · mass assignment ✅ · 越权 ☐ | |
| 认证/会话 | JWT alg:none ✅ · JWT 弱密钥 ✅ · JWT kid/jku ☐ · OAuth ☐ · session fixation ☐ | |
| SSRF | 基础 ✅ · 云元数据/gopher/DNS rebinding ☐ | |
| 文件 | 路径遍历 ✅ · LFI(php://filter) ✅ · 任意上传 ☐ | |
| API | GraphQL 内省 ✅ · 批量/限流绕过 ☐ | |
| web 密码学 | CBC 翻转 ✅ · ECB 剪贴 ✅ · padding oracle ☐ · 哈希长度扩展 ☐ | |
| 客户端 ⚠ | XSS(反射/存储/DOM) · CSRF · CORS · 原型链污染 | ⚠ 需无头浏览器工具 |
| 逻辑 | 竞态 · 业务逻辑 · 价格篡改 | ☐ 难做确定性 hermetic |
| 现代 | 反序列化(pickle/Java) · 请求走私 · 缓存投毒 | ☐ |

## 2. Crypto  — 工具:run_python + pycryptodome + sympy(齐)

| 方向 | 具体 | 状态 |
|------|------|------|
| 古典 | 单字节 XOR ✅ · 重复 XOR ✅ · 编码层 ✅ · 维吉尼亚/替换/仿射 ☐ | |
| RSA | 立方根 ✅ · Fermat ✅ · Wiener ✅ · 共模 ✅ · Håstad ✅ · 共因子 ✅ · LSB oracle ☐ · Coppersmith ⚠ | |
| 对称 | CTR 复用 ✅ · CBC/padding oracle ☐ · ECB byte-at-a-time ☐ · GCM nonce 复用 ☐ | |
| 离散对数/ECC | Pohlig-Hellman ✅ · ECDSA nonce 复用 ✅ · 小子群/无效曲线 ☐ · 偏置 nonce(HNP) ⚠ | |
| 哈希/PRNG | 弱哈希爆破 ✅ · LCG 预测 ✅ · 梅森旋转预测 ☐ · 长度扩展 ☐ · MD5 碰撞 ☐ | |
| 格 ⚠ | LWE · NTRU · HNP+LLL · Coppersmith | ⚠ 需 fpylll(Python 3.14 暂难装) |

> 注:需交互式 oracle 的攻击(padding oracle、RSA LSB oracle、ECB byte-at-a-time)不适合
> 当前"模型逐轮发请求 + 沙箱禁网"的结构——agent 没法在一次 run_python 里循环查询我们的 oracle。
> 要做得加一个"可被 agent 反复查询的本地 oracle 工具"。

## 3. Pwn / 二进制利用  ⚠ 需新工具

**所需工具**:沙箱里跑目标 ELF + stdin/stdout 交互(`process_tool`)、pwntools、可能 gdb。
hermetic:附一个有漏洞的二进制,agent 在本地沙箱里打,拿 shell / 读 flag 文件。

| 方向 | 具体 |
|------|------|
| 栈 | 缓冲区溢出(ret2win) · canary 绕过 · ret2libc · ROP 链 · 格式化字符串 |
| 堆 | UAF · double-free · tcache/fastbin · house-of-* |
| shellcode | 注入 · ret2shellcode · ret2dlresolve |
| 整数 | 整数溢出 · off-by-one |

## 4. Reverse / 逆向  ⚠ 需新工具

**所需工具**:反汇编/反编译(objdump / radare2 / Ghidra headless)、**符号执行 angr**
(自动求"输入→flag")、沙箱跑二进制。

| 方向 | 具体 |
|------|------|
| 静态 | 读汇编/反编译 · 理解算法 |
| crackme/keygen | 找通过校验的输入 |
| 保护 | 混淆 · 加壳(UPX) · 反调试 |
| VM/字节码 | 自定义 VM · .pyc · Java/.NET · Go/Rust · WASM |

## 5. Forensics / 取证  ⚠ 需新工具

**所需工具**:文件只读 + 分析库(PIL / scapy)+ 命令工具(binwalk / exiftool / strings / tshark)。

| 方向 | 具体 |
|------|------|
| 文件 | 文件雕刻/恢复 · 元数据 · magic bytes |
| 隐写 | 图像 LSB · 音频频谱 · steghide/zsteg |
| 流量 | pcap 分析 · 提取文件/凭据 · 协议还原 |
| 内存 | volatility 内存取证 |
| 文档 | PDF · Office 宏 |

## 6. Misc / 杂项  — 工具:run_python(部分需交互工具)

| 方向 | 具体 |
|------|------|
| jail 逃逸 | pyjail · 受限 bash · 沙箱逃逸 |
| 编码/esoteric | 编码谜题 · QR/条码 · 冷门语言 |
| 编程题 | 限时算法 · 多轮交互脚本 |
| 逻辑/游戏 | 谜题 · 博弈 |

## 7. 现代 / 可选大类

- **AI/ML 安全** — 提示注入 / 越狱 / prompt 泄露。工具 `send_message`(靶子是带防御的 LLM)。已出设计,见对话记录。
- **Blockchain** — 智能合约重入等,需本地 EVM。
- **OSINT** — 需真实联网,非 hermetic,暂不纳入。
- Mobile(APK 逆向,属 reverse 子集)、Hardware/RF(物理,跳过)。

---

## 扩展方式

- 加 web/crypto 子方向:在 `web/challenges/` 或 `crypto/challenges/` 加一文件(接口见 CLAUDE.md),
  注册进 `evaluate.py`,先脚本验证可解再跑模型。
- 开新大类:先建该方向的 agent 工具(放未来的 `tools/`),再照 web/crypto 的模式建 `<大类>/agent.py`
  + `challenges/` + `evaluate.py`。

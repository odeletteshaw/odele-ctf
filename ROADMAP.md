# odele-ctf 路线图

CTF 各大类(方向)与其下的具体子方向,标注**现状**和**所需工具**。设计原则见
[CLAUDE.md](CLAUDE.md):靶题 hermetic(虚拟化,不碰真实系统),工具是"能力"不是"解法"。

图例:✅ 已做 · ☐ 待做 · ⚠ 需新工具

**规划主线**:web/crypto/misc/forensics/ai 已就绪——它们的工具齐备(`http_request`、
`run_python`、`send_message`;forensics 把文件 base64 嵌进题面,也走 run_python)。
pwn/reverse 还卡在工具上——开这两类前,得先给 agent 建对应的新工具(交互式进程 / 反汇编)。

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

## 5. Forensics / 取证  — 工具:run_python(齐)

做法:把文件 **base64 嵌进题面**,agent 用 run_python 解析/雕刻——无需新工具,全程 hermetic。
注意**内嵌附件要小**(run_python 无状态,大附件会被反复粘贴耗光回合)。

| 方向 | 具体 | 状态 |
|------|------|------|
| 文件雕刻 | IEND 后追加 ✅ · magic bytes ☐ · polyglot ☐ | |
| 归档 | 嵌套 zip + comment ✅ · gzip/tar 套娃 ☐ | |
| 流量 | pcap + TCP 乱序重组 ✅ · 协议还原/提取文件 ☐ | |
| 音频隐写 | WAV LSB ⚠(能力边界) · 频谱 ☐ | ⚠ |
| 图像隐写 ⚠ | 图像 LSB · 元数据/EXIF | ⚠ 需 Pillow |
| 大件 ⚠ | 磁盘镜像 · volatility 内存 · steghide/zsteg | ⚠ 需 files_tool + 外部库 |
| 文档 | PDF · Office 宏 | ☐ |

## 6. Misc / 杂项  — 工具:run_python(齐,部分子方向需交互工具)

| 方向 | 具体 | 状态 |
|------|------|------|
| 编码/esoteric | 多层压缩 ✅ · brainfuck ✅ · 编码谜题 ☐ · QR/条码 ☐ | |
| 编程题 | keystream XOR ✅ · 限时算法 ☐ · 多轮交互脚本 ☐ | |
| jail 逃逸 ⚠ | pyjail · 受限 bash · 沙箱逃逸 | ⚠ 需交互式进程工具 |
| 逻辑/游戏 | 谜题 · 博弈 | ☐ |

## 7. AI / 提示安全  — 工具:send_message + run_python(齐)

靶子是一个带防御的聊天机器人(Defender,复用 DeepSeek,flag 藏在其 system prompt),agent 用
`send_message` 红队、`run_python` 解码。五关阶梯:

| 关 | 考点 | 状态 |
|----|------|------|
| naive | 直接问就给(地板,验证管线) | ✅ 可解 |
| output_filter | 输出过滤只拦原文 → 变形绕过 | ✅ 可解 |
| input_filter | 输入过滤禁词 → 绕词套取 | ✅ 可解 |
| firm | 无过滤,模型硬拒 → 纯越狱 | ⚠ 能力边界 |
| both_filters | 双过滤 + 模型拒答 → 天花板 | ⚠ 能力边界(原理可解) |

以后可加:间接提示注入(读被投毒的外部文本)、带工具的靶子、语义级输出过滤。详见 `ai/TODO.md`。

## 8. 现代 / 可选大类
- **Blockchain** — 智能合约重入等,需本地 EVM。
- **OSINT** — 需真实联网,非 hermetic,暂不纳入。
- Mobile(APK 逆向,属 reverse 子集)、Hardware/RF(物理,跳过)。

---

## 扩展方式

- 加 web/crypto 子方向:在 `web/challenges/` 或 `crypto/challenges/` 加一文件(接口见 CLAUDE.md),
  注册进 `evaluate.py`,先脚本验证可解再跑模型。
- 开新大类:先建该方向的 agent 工具(放未来的 `tools/`),再照 web/crypto 的模式建 `<大类>/agent.py`
  + `challenges/` + `evaluate.py`。

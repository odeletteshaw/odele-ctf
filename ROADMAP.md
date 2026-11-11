# odele-ctf 路线图

CTF 各大类(方向)与其下的具体子方向,标注**现状**和**所需工具**。设计原则见
[CLAUDE.md](CLAUDE.md):靶题 hermetic(虚拟化,不碰真实系统),工具是"能力"不是"解法"。

图例:✅ 已做 · ☐ 待做 · ⚠ 需新工具

**规划主线**:web/crypto/misc/forensics/ai/pwn/reverse 七类已就绪。做法都是「给对的工具 + hermetic
模拟漏洞」:web 用 `http_request`;crypto/misc/forensics 用 `run_python`(forensics 把文件 base64
嵌进题面);ai 用 `send_message` 打模拟的带防御聊天机器人;pwn 用 `send_input` 打模拟的有漏洞
进程;reverse 用 `disassemble`(objdump)+ `run_binary` 打自己编译的小 C crackme,符号求解用
z3(angr 在 arm64 macOS 跑不动 Mach-O,真 angr 留待 x86_64 ELF)。

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
| 古典 | 单字节 XOR ✅ · 重复 XOR ✅ · 编码层 ✅ · 维吉尼亚 ✅ · 仿射 ✅ · 替换 ✅ | |
| RSA | 立方根 ✅ · Fermat ✅ · Wiener ✅ · 共模 ✅ · Håstad ✅ · 共因子 ✅ · LSB oracle ☐ · Coppersmith ⚠ | |
| 对称 | CTR 复用 ✅ · CBC/padding oracle ☐ · ECB byte-at-a-time ☐ · GCM nonce 复用 ✅ | |
| 离散对数/ECC | Pohlig-Hellman ✅ · ECDSA nonce 复用 ✅ · 小子群/无效曲线 ☐ · 偏置 nonce(HNP) ⚠ | |
| 哈希/PRNG | 弱哈希爆破 ✅ · LCG 预测 ✅ · 梅森旋转预测 ✅ · 长度扩展 ☐ · MD5 碰撞 ☐ | |
| 格 ⚠ | LWE · NTRU · HNP+LLL · Coppersmith | ⚠ 需 fpylll(Python 3.14 暂难装) |

> 注:需交互式 oracle 的攻击(padding oracle、RSA LSB oracle、ECB byte-at-a-time)不适合
> 当前"模型逐轮发请求 + 沙箱禁网"的结构——agent 没法在一次 run_python 里循环查询我们的 oracle。
> 要做得加一个"可被 agent 反复查询的本地 oracle 工具"。

## 3. Pwn / 二进制利用  — 工具:send_input + run_python(齐)

做法(hermetic,同 web 模拟漏洞):不跑真实 ELF/shell,而是**模拟有漏洞的进程**(虚拟栈/内存、
玩具 printf)。agent 用 `send_input` 发 payload(hex/text)、run_python 算偏移打地址。

| 方向 | 具体 | 状态 |
|------|------|------|
| 栈 | 溢出相邻变量 ✅ · ret2win ✅ · 格式化字符串泄露 ✅ · canary 绕过 ☐ · ret2libc/ROP ☐ | |
| 堆 ⚠ | UAF · double-free · tcache/fastbin · house-of-* | ⚠ 需模拟玩具分配器 |
| shellcode ⚠ | 注入 · ret2shellcode | ⚠ 需模拟可执行内存/CPU |
| 整数 | 整数溢出 · off-by-one | ☐ |

> 真·跑二进制(拿真实 shell)不在 hermetic 范围;要做得另起受控沙箱(qemu/ptrace),成本高。

## 4. Reverse / 逆向  — 工具:disassemble + run_binary + run_python(齐)

做法(hermetic,同 pwn 模拟漏洞):**自己写的小 C crackme 在 `make(flag)` 时用 clang 编译**,
flag XOR 混淆编译进去。agent 用 `objdump -d -s` 反汇编、沙箱跑二进制、run_python 解码/求逆。

| 方向 | 具体 | 状态 |
|------|------|------|
| 静态 | 读汇编/反编译 · 理解算法 | ✅ 4 题(run_me / crackme_xor / crackme_serial / crackme_z3) |
| crackme/keygen | 找通过校验的输入 | ✅(crackme_xor / crackme_serial) |
| 符号执行 | z3 符号求解(angr 底层同款) | ✅ crackme_z3(30 字节耦合变换) |
| 保护 | 混淆 · 加壳(UPX) · 反调试 | ☐ |
| VM/字节码 | 自定义 VM · .pyc · Java/.NET · Go/Rust · WASM | ☐ |

## 5. Forensics / 取证  — 工具:run_python(齐)

做法:把文件 **base64 嵌进题面**,agent 用 run_python 解析/雕刻——无需新工具,全程 hermetic。
注意**内嵌附件要小**(run_python 无状态,大附件会被反复粘贴耗光回合)。

| 方向 | 具体 | 状态 |
|------|------|------|
| 文件雕刻 | IEND 后追加 ✅ · magic bytes ☐ · polyglot ☐ | |
| 归档 | 嵌套 zip + comment ✅ · gzip/tar 套娃 ☐ | |
| 流量 | pcap + TCP 乱序重组 ✅ · 协议还原/提取文件 ☐ | |
| 音频隐写 | WAV LSB ✅ · 频谱 ☐ | |
| 图像隐写 ⚠ | 图像 LSB · 元数据/EXIF | ⚠ 需 Pillow |
| 大件 | 磁盘镜像 · volatility 内存 · steghide/zsteg | ✅ 有可持久化工作区(large_blob);外部库待加 |
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
- 开新大类:先建该方向的 agent 工具(放 `tools/`),再照 web/crypto 的模式建 `<大类>/agent.py`
  + `challenges/` + `evaluate.py`。

# odele-ctf

一个用来打安全 CTF 的 **agent**，配一套**本地 hermetic 靶题**来衡量它。默认模型 **DeepSeek**
（`deepseek-chat`，OpenAI 兼容接口，调试积分便宜）。

核心思想：**工具是「能力」，不是「解法」**。agent 拿到的是「发 HTTP 请求 / 跑代码 / 反汇编二进制 /
戳一个进程 / 跟聊天机器人对话」这类动词，而不是现成的 `fermat_factor`、`wiener` 之类的解题库——
它得自己写出解题代码。靶题全部 **hermetic**：用虚拟状态模拟漏洞（假 shell、虚拟文件系统、模拟
内网、内存里的密码学、自己编译的小 crackme），模型的输入**绝不**接触真实系统、文件或网络。

## 现状

7 个大类共 **77 道题**，DeepSeek 几乎全解（能力边界只剩 AI 红队的 firm/both_filters，以及 crypto
的 padding oracle / ECB byte-at-a-time）。

| 大类 | 题数 | agent 工具 | 说明 |
|------|------|-----------|------|
| web | 21 | `http_request` + `run_python` | SQLi / 命令注入 / SSRF / XXE / SSTI / JWT / 反序列化 / 分组密码… |
| crypto | 24 | `run_python`（+ `query_oracle`） | 古典 / RSA / 对称 / ECC / 哈希 / PRNG / 格(SVP/HNP) / oracle 攻击 |
| misc | 5 | `run_python`（+ `send_code`） | brainfuck / 压缩层 / XOR / Morse / pyjail |
| forensics | 10 | `run_python`（+ 持久化工作区） | 文件雕刻 / 归档套娃 / pcap / 隐写 / HTTP 协议还原 |
| pwn | 7 | `send_input` + `run_python` | 溢出 / ret2win / 格式化串 / canary / shellcode / heap UAF |
| reverse | 5 | `disassemble` + `run_binary` + `run_python` | 反汇编 / keygen / z3 符号求解 / 字节码 VM |
| ai | 5 | `send_message` + `run_python` | 提示注入红队打带防御的聊天机器人 |

## 快速开始

```bash
# 1. 依赖（Python 3.14）
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. 密钥：.env 里放 DEEPSEEK_API_KEY（gitignored，core/config.py 自动加载）
echo 'DEEPSEEK_API_KEY=sk-...' > .env

# 3. 跑评测（随机 flag，答案无法靠猜）
python web/evaluate.py sqli_login        # 跑单题
python crypto/evaluate.py                # 跑全部 crypto 题
```

离线循环测试**不需要 API key**（脚本化假模型驱动真实工具）：

```bash
python web/test_offline.py
python crypto/test_offline.py
python reverse/test_offline.py
```

图形监督控制台（实时看 agent 解题、可中途给指导）：

```bash
python -m gui.launch               # 空控制台，按 ＋ 加会话
python -m gui.launch web sqli_login  # 打开即带一个正在跑的会话
```

切换模型/厂商：环境变量 `CTF_API_BASE` / `CTF_MODEL` / `CTF_API_KEY`（真实环境变量优先于 `.env`）。

## 目录结构

```
core/       跨题型通用底座：config（模型配置）、agent（Tool + run_loop + solve）、
            sandbox（run_python / run_command 沙箱）、evaluate（benchmark 循环）、offline
tools/      agent 工具（「能力」），各题型从同一个菜单组装：
            sandbox.py python_tool · http.py http_tool · process.py process_tool
            chat.py message_tool · bin.py disassemble_tool / run_binary_tool
            oracle.py query_oracle（批量查询交互式 oracle）
<大类>/     每个题型同构：agent.py（prompt + 工具组装）+ challenges/（一题一文件）+ evaluate.py
gui/        监督控制台（CustomTkinter，每题一个子进程会话）
```

## 设计原则

- **工具是能力不是解法**：agent 在 `run_python` 里自己写解题代码；不存在共享解题库。
- **hermetic 且安全**：靶题用虚拟状态模拟漏洞，模型输入不接触真实 shell / 文件系统 / 网络。
- **每次随机 flag**（`flag{token_hex(12)}`），答案无法靠猜或记忆。
- **三类代码严格分开**：agent 工具（`tools/`）、出题 helper（各题型 `challenges/_common.py`，agent
  永远碰不到）、评测框架（`core/`）。

## 沙箱

`core/sandbox.py` 在隔离子进程里跑模型给的代码/二进制：临时目录作 cwd/HOME、`python3 -I`、
**禁网**（macOS `sandbox-exec (deny network*)`，Linux 私有网络命名空间）、CPU/文件 rlimit + 墙钟
超时。复用项目 venv，所以装好的库（pycryptodome、sympy、z3-solver）在沙箱里都能 import。

## 加题

每个题型同构，加一题 = 写一个 `challenges/<name>.py`（暴露 `DESCRIPTION` + `make(flag)` / `start(flag)`），
注册进该题型的 `evaluate.py`，然后：

1. **先脚本验证**：写个短脚本跑一遍**预期**攻击，确认能拿到 flag、没有意外捷径/真实信息泄露。
2. 只对这道题跑模型评测。
3. 即使模型解不出也保留——「脚本验证可解、模型当前打不穿」的题是有价值的能力边界靶标。

详细的题型接口、血的教训见 [CLAUDE.md](CLAUDE.md)，子方向路线图见 [ROADMAP.md](ROADMAP.md)。

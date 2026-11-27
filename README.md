# odele-ctf

一个用来打安全 CTF 的 **agent**，配一套**本地 hermetic 靶题**来衡量它。默认模型 **DeepSeek**
（`deepseek-chat`，OpenAI 兼容接口，调试积分便宜）。

核心思想：**工具是「能力」，不是「解法」**。agent 拿到的是「发 HTTP 请求 / 跑代码 / 反汇编二进制 /
戳一个进程 / 跟聊天机器人对话」这类动词，而不是现成的 `fermat_factor`、`wiener` 之类的解题库——
它得自己写出解题代码。靶题全部 **hermetic**：用虚拟状态模拟漏洞（假 shell、虚拟文件系统、模拟
内网、内存里的密码学、自己编译的小 crackme），模型的输入**绝不**接触真实系统、文件或网络。

## 现状

7 个大类共 **78 道题**，DeepSeek 几乎全解（能力边界只剩 AI 红队的 firm/both_filters，以及 crypto
的 padding oracle / ECB byte-at-a-time）。

| 大类 | 题数 | agent 工具 | 说明 |
|------|------|-----------|------|
| web | 21 | `http_request` + `run_python` | SQLi / 命令注入 / SSRF / XXE / SSTI / JWT / 反序列化 / 分组密码… |
| crypto | 24 | `run_python`（+ `query_oracle`） | 古典 / RSA / 对称 / ECC / 哈希 / PRNG / 格(SVP/HNP) / oracle 攻击 |
| misc | 5 | `run_python`（+ `send_code`） | brainfuck / 压缩层 / XOR / Morse / pyjail |
| forensics | 10 | `run_python`（+ 持久化工作区） | 文件雕刻 / 归档套娃 / pcap / 隐写 / HTTP 协议还原 |
| pwn | 8 | `send_input` + `run_python` | 溢出 / ret2win / 格式化串 / canary / shellcode / heap UAF |
| reverse | 5 | `disassemble` + `run_binary` + `run_python` | 反汇编 / keygen / z3 符号求解 / 字节码 VM |
| ai | 5 | `send_message` + `run_python` | 提示注入红队打带防御的聊天机器人 |

## 快速开始

```bash
# 1. 依赖（Python 3.14）
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. 密钥：首次可在 .env 里放 DEEPSEEK_API_KEY（gitignored，agent/config.py 自动加载），
#    启动控制台后也可以直接在「配置管理」页里改（存本地数据库）
echo 'DEEPSEEK_API_KEY=sk-...' > .env

# 3. 跑评测（随机 flag，答案无法靠猜）
python agent/categories/web/evaluate.py sqli_login        # 跑单题
python agent/categories/crypto/evaluate.py                # 跑全部 crypto 题
```

离线循环测试**不需要 API key**（脚本化假模型驱动真实工具）：

```bash
python agent/categories/web/test_offline.py
python agent/categories/crypto/test_offline.py
python agent/categories/reverse/test_offline.py
```

Web 控制台（前后端分离）：

```bash
# 1. 后端（FastAPI，REST + WebSocket，端口 8765）
./restart_server.sh

# 2. 前端（React + Material-UI，Vite dev server，端口 5173）
cd frontend && npm install && npm run dev
# 浏览器打开 http://localhost:5173（dev server 自动把 /api 代理到 8765）
```

控制台里「配置管理」页可直接改模型 / API Base / API Key / 平台 token，「团队」页改方向分工；
这些配置存本地数据库 `~/.odele-ctf/sessions.db`（权限 0600），保存后对新任务生效。
环境变量 `CTF_API_BASE` / `CTF_MODEL` / `CTF_API_KEY` 与 `.env` 只作首次回退。

## 目录结构

三层：**frontend 管页面，backend 管数据库与 API，agent 管解题（知识 / 工具 / 题型）**。

```
frontend/   控制台前端：React + Material-UI（Vite）；src/pages/ 一页一文件
backend/    控制台后端（数据库 + API，纯服务层）：
  app.py       FastAPI REST + WebSocket
  db.py        SQLite：sessions / transcript / memories / settings
  settings.py  配置存取（tokens / 团队 / 模型），API 只返回打码值
  manager.py   session 生命周期 · controller.py autosolve / retry 编排
  worker.py    解题子进程入口 · platform.py CTF2 REST 客户端
  autosolve.py 平台题 → spec · team.py 角色团队配置（团队长/侦察/专家/报告）
  slots.py     打题 Token 槽位（方向 → 第几个 token）
agent/      解题能力层（纯库，不依赖 frontend/backend）：
  loop.py      Tool + run_loop + solve + flag 提取
  team.py      角色团队编排：团队长出计划 → 侦察 → 方向专家 → 报告员复盘
  skills.py    角色技能包加载：索引 / 检索 / 工具化（search_role_skill）
  team_skills/ 每角色技能包（SKILL.md + references/），见下方「角色技能包」
  config.py    模型/厂商配置（.env 回退） · sandbox.py run_python / run_command 沙箱
  evaluate.py  benchmark 循环 · offline.py 离线测试 helper
  taskbuilder.py  spec → 一次解题任务（工具 + prompt）
  tools/       agent 工具（「能力」）：sandbox / http / process / chat / bin / oracle /
               knowledge / phar
  knowledge/   技巧卡（按类别，供 search_knowledge 检索）
  categories/  七个题型，每个同构：agent.py（prompt + 工具组装）+ challenges/ +
               evaluate.py；generic/ 是扩展方向（云/链/工控/IoT/应急/渗透）的通用工具集
scripts/import_skills.py  把本地资料导入角色技能包
```

## 团队协作

控制台的「团队」是**角色团队**，不是打题 token 分配：

- **团队长**：读题、拆任务、出计划并分派
- **信息收集员**：用该题型的工具摸清目标（接口、参数、技术栈、泄露线索），输出带证据的事实清单；pwn / ai 这类有状态目标跳过侦察，避免破坏现场
- **攻防专家**：按方向匹配，每个方向一个：web / crypto / misc / forensics / pwn / reverse / ai，
  以及扩展方向 cloud / blockchain / ics / iot / ir / pentest（扩展方向用手动解题的通用工具集），
  带着计划与侦察结果解题
- **报告收集员**：写中文题解 + 团队复盘（分工、关键发现、利用链、成败原因）

手动解题与平台自动打题都会走这套流程；session 详情页新增「团队复盘」标签，可看角色时间线。
方向 → token 的分配拆到「Token 槽位」页（`backend/slots.py`），与团队角色是两套概念。

团队页支持**自由新建角色**：填写名字、职责定义、勾选技能包（也可新建以角色命名的技能包）。
自定义角色的 id 会写进团队长计划，团队长按需调用（最多 3 个），它们的发现会交给方向专家。
每个角色还能单独勾选/取消技能包；MCP 字段已在数据模型中预留，本轮暂未接入真实 MCP。

### 角色技能包

每个角色可以有自己的方法与资料包：

```
agent/team_skills/
  _shared/                 所有角色共享（Hello-CTF 方向路由、分类总表）
  lead/ recon/ reporter/   各角色 SKILL.md + references/
  experts/_common/         所有专家共享的方法
  experts/<direction>/     方向专家专属资料（web/crypto/misc/forensics/pwn/reverse/ai +
                           cloud/blockchain/ics/iot/ir/pentest）
  roles/<role-id>/         新建自定义角色时自动生成的技能包
```

- 系统 prompt 只放**紧凑索引**；角色通过 `search_role_skill(query)` 按需读取全文
- 控制台「技能包」页可按角色浏览、搜索并阅读全文（Markdown 渲染）；团队页的技能计数可点击进入
- 团队长/报告员不能调工具，技能包会以「索引 + SKILL.md 正文」注入
- 侦察员只用只读工具白名单（http_request/batch、download_file、run_python、
  search_knowledge、triage/strings/disassemble），专家用完整工具集
- 导入本地资料：
  `python scripts/import_skills.py --role expert-web --source ~/sec-notes/web`
  （支持 md/txt/代码/PDF；`--list` 查看现有包，`--dry-run` 预览）
- 已导入 [Hello-CTF](https://github.com/ProbiusOfficial/Hello-CTF) 的 `docs/hc-skill`
  资料（CC BY-SA 4.0），来源与许可见 `agent/team_skills/NOTICE.md`

## 设计原则

- **工具是能力不是解法**：agent 在 `run_python` 里自己写解题代码；不存在共享解题库。
- **hermetic 且安全**：靶题用虚拟状态模拟漏洞，模型输入不接触真实 shell / 文件系统 / 网络。
- **每次随机 flag**（`flag{token_hex(12)}`），答案无法靠猜或记忆。
- **分层且单向依赖**：`backend` 可以 import `agent`，`agent` 不反向依赖 `backend`；出题 helper
  （各题型 `challenges/_common.py`）agent 永远碰不到。

## 沙箱

`agent/sandbox.py` 在隔离子进程里跑模型给的代码/二进制：临时目录作 cwd/HOME、`python3 -I`、
**禁网**（macOS `sandbox-exec (deny network*)`，Linux 私有网络命名空间）、CPU/文件 rlimit + 墙钟
超时。复用项目 venv，所以装好的库（pycryptodome、sympy、z3-solver）在沙箱里都能 import。

## 加题

每个题型同构，加一题 = 写一个 `challenges/<name>.py`（暴露 `DESCRIPTION` + `make(flag)` / `start(flag)`），
注册进该题型的 `evaluate.py`，然后：

1. **先脚本验证**：写个短脚本跑一遍**预期**攻击，确认能拿到 flag、没有意外捷径/真实信息泄露。
2. 只对这道题跑模型评测。
3. 即使模型解不出也保留——「脚本验证可解、模型当前打不穿」的题是有价值的能力边界靶标。

详细的题型接口、血的教训见 [CLAUDE.md](CLAUDE.md)，子方向路线图见 [ROADMAP.md](ROADMAP.md)。

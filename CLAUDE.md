# odele-ctf

一个用来打安全 CTF 的 agent，配一套本地 hermetic 靶题来衡量它。默认模型：**DeepSeek**
（`deepseek-chat`），走 OpenAI 兼容接口——因为它的调试积分便宜。

## 目录结构

三层：**frontend 管页面，backend 管数据库与 API，agent 管解题（知识 / 工具 / 题型）**。
依赖单向：`backend` → `agent`，`agent` 绝不 import `backend`。

```
frontend/     控制台前端：React + Material-UI（Vite），src/pages/ 一页一文件
backend/      控制台后端（数据库 + API，纯服务层）
  app.py        FastAPI REST + WebSocket
  db.py         SQLite schema / 连接：sessions、transcript、memories、settings
  settings.py   配置存取：平台 tokens、团队、模型配置（DB 0600；接口只返回打码值）
  manager.py    session 生命周期 + 持久化 · worker.py 解题子进程入口
  controller.py autosolve / retry 控制循环
  platform.py   CTF2 REST 客户端 · autosolve.py 平台题 → spec
  team.py       角色团队配置（团队长 + 扁平角色池）
agent/        解题能力层（纯库）
  loop.py       Tool、run_loop、solve()、flag 提取（FLAG_PATTERN）
  team.py       角色团队编排：团队长计划 → 侦察 → 方向专家 → 报告员复盘
  config.py     厂商/模型配置；加载 .env（真实环境变量优先于 .env）
  sandbox.py    沙箱引擎：run_python / run_command（隔离子进程、禁网、rlimit）
  evaluate.py   benchmark()：各题型共享的 PASS/FAIL 评测循环
  offline.py    tool_call()：离线测试（无 API key）的假模型 helper
  taskbuilder.py  spec → 一次解题任务（工具 + prompt），worker 调用
  tools/        agent 工具（「能力」），每个题型从这里组装
    sandbox.py python_tool() · http.py http_tool() · process.py process_tool()
    chat.py message_tool() · bin.py disassemble_tool()/run_binary_tool()
  knowledge/    技巧卡（按类别）+ search_knowledge 检索
  skills.py     扁平技能库加载 / 检索 / search_role_skill 工具
  skill_library/ 扁平技能库（每篇 md 带 id/name/description/tags）；角色用 skill id
                或 tag:xxx 绑定；Hello-CTF hc-skill 资料在此（CC BY-SA 4.0，见
                NOTICE.md）；导入用 scripts/import_skills.py --source ... --tags ...
  categories/web/     Web 题型：HTTP 靶题
    agent.py       prompt + 工具组装（http_request + run_python）；origin 锁定
    challenges/    一题一文件；_harness.py 是共享 HTTP server，_common.py 是出题 helper
    evaluate.py    用随机 flag 跑 agent 过一遍靶题；输出 PASS/FAIL
    test_offline.py  用脚本化的假模型驱动循环（不需要 API key）
  categories/crypto/  密码学题型：纯计算（只给 run_python）
    agent.py、challenges/、evaluate.py、test_offline.py （结构同 web）
  categories/{pwn,misc,forensics,ai,reverse}/  其余五类，同 web/crypto 结构
```

跑评测：`python agent/categories/web/evaluate.py [名字...]` 或 `python agent/categories/crypto/evaluate.py [名字...]`
（不给名字 = 全跑）。需要 `DEEPSEEK_API_KEY`（见「密钥」）。离线循环测试不需要 key：
`python agent/categories/web/test_offline.py`。

## agent 怎么工作

- `agent.loop.Tool(name, description, parameters, handler)` 是模型能调用的一个能力。
  `run_loop(chat, tools, system, user, max_turns)` 驱动一个 OpenAI 风格的 tool-calling
  循环；`solve(tools, system_prompt, user_prompt)` 接上真实模型。
- 一个题型 = **一段 system prompt + 选用哪几个 Tool**。Web 给模型 `http_request` 和
  `run_python`；crypto 只给 `run_python`。
- 题面数据作为 user prompt 传给模型。flag 形如 `flag{...}`；`FLAG_PATTERN` 从模型最后一条
  消息里提取最终 flag。
- **角色团队**（`agent/team.py`）：**团队长是唯一入口**，接收用户命令后输出 DAG
  （节点=角色任务/依赖/needs_approval），其余角色扁平、任意调度；chain 是线性 DAG。
  需要审批的节点通过 worker 的 approvals 队列阻塞等待，页面批准/驳回后继续。
  默认角色池：信息收集 + 13 个方向专家（web/crypto/misc/forensics/pwn/reverse/ai +
  cloud/blockchain/ics/iot/ir/pentest）+ 知识收割 + 报告收集；后六个方向用
  `agent/categories/generic` 通用工具集。平台 token 不按方向绑定：开始打题时勾选本次
  使用的 token，方向在所选 token 间轮转；token 在配置页维护。
- **知识收割**（`agent/harvest.py`，kind=harvest）：团队长仅在出现可复用新知识时安排；
  `harvest_skill` 强制防冗杂（一题≤2 张、去重、禁 flag/目标域名、标签白名单、不改旧卡）。
- **团队通话**：run_team 发出 `message` 事件（团队长计划 / 分派 / 角色结果），manager 存到
  session.state.messages；每个节点工具集里都有 `ask_user`，角色可 @ 用户并阻塞等待
  `/api/sessions/{id}/reply`，用户也可发 `/guidance`。通话页 `/api/calls` 聚合最近会话的
  消息与 @mention；原来的记忆检索页改名为「记忆池」。
- **技能库**（`agent/skills.py` + `agent/skill_library/`）：扁平库，每篇 md 带
  id/name/description/tags；角色绑定 skill id 或 `tag:xxx`，索引进 prompt、用
  `search_role_skill` 按需读取；导入资料用 `scripts/import_skills.py`。

## 核心设计原则：工具是「能力」，不是「解法」

工具是**模型能做的动词**——发请求、跑代码、（以后）读题目附带的文件、戳一个进程。它们绝不能
是**答案**：不存在一个给 agent import 的 `cube_root`、`fermat_factor`、`wiener` 之类的共享
解题库。agent 要在 `run_python` 里自己写解题代码。共享解题库等于把答案送给 agent，会让这套
benchmark 失去意义。

**目录职责：** agent 工具集中在 `agent/tools/` 包，用工厂函数从同一个菜单组装
（`agent/tools/sandbox.py: python_tool()`、`agent/tools/http.py: http_tool(target)`、`agent/tools/process.py:
process_tool(proc)`、`agent/tools/chat.py: message_tool(send)`、`agent/tools/bin.py:
disassemble_tool(binary)` / `run_binary_tool(binary)`）。出题侧共享 helper 放在各题型的
`challenges/_common.py`（web 的 JWT/base64url/bearer、reverse 的编译 helper——agent 永远
碰不到）。评测框架收在 `agent/`：`agent/evaluate.py: benchmark()` 通用 PASS/FAIL 循环、
`agent/offline.py: tool_call()` 离线测试 helper。三类保持分开：agent 工具（`agent/tools/`）、出题
helper（`challenges/_common.py`）、评测框架（`agent/`）。

## 出题规范

- **Hermetic 且安全。** 靶题要用虚拟状态模拟漏洞——假 shell、虚拟文件系统、模拟内网、内存里的
  密码学。模型的输入**绝不能**接触真实 shell、真实文件系统或真实网络，否则 agent 可能读到宿主机
  （包括这个 `.env`）或打到真实目标。
- **各题型接口：**
  - web：`DESCRIPTION: str` 和 `start(flag) -> (server, base_url)`。server 绑
    `127.0.0.1:0`、跑在 daemon 线程里；`agent/categories/web/challenges/_harness.py` 提供路由
    （`Request`、`start_server`）。
  - crypto：`DESCRIPTION: str` 和 `make(flag) -> str`，返回题面文本（把 flag 加密/编码进去的
    密文和参数）。没有 server。
- **每次随机 flag**（`flag{token_hex(12)}`），这样答案无法靠猜或记忆。
- 把新模块注册进该题型的 `evaluate.py`。

### 加题 checklist

1. 写靶题模块（必须 hermetic，见上）。
2. **先用脚本验证：** 写个短脚本跑一遍**预期**攻击，确认能拿到 flag，且意料外的捷径被堵住、没有
   真实信息泄露。在花模型积分之前做这一步。
3. 只对这道题跑模型评测。
4. 即使模型解不出也保留——一道「脚本验证可解、但模型当前解不出」的题是有价值的能力边界靶标
   （例如 `web/ecb_paste`）。

## 沙箱（run_python）

`agent/sandbox.py` 在隔离子进程里跑模型给的 Python：临时目录作为 cwd/HOME、`python3 -I`、
**禁网**（macOS `sandbox-exec (deny network*)`，Linux 私有网络命名空间）、CPU/文件 rlimit
和墙钟超时（~15s CPU）。它复用项目 venv，所以装好的库（pycryptodome、sympy）在里面能 import。

## 血的教训

- **出题生成（`make`/`start`）里的性能 bug，看起来和模型/API 挂起一模一样**——评测其实卡在
  **到达模型之前**。评测挂起时，要分段计时：出题生成 vs 求解 vs 某个具体库调用。
- `sympy.primitive_root(大素数)` 病态地慢；改用已知分解自己验证原根。
- 构造光滑素数时，用**不重复的小素数**（如 < 1000）来搭 `p-1`。用较大素数且可重复采样会产生大的
  素数幂，让 `sympy.discrete_log` 病态地慢。
- **不要为了逼过某道难题而往 prompt 加针对该题的提示**——它往往会让别的题回归（一次加 AES 提示
  把本来能过的题弄挂了）。优先给通用的、事实性的指导（漏洞清单、有哪些库可用、沙箱时间限制）。
- 单次模型运行有方差；判断回归或改进要多跑几次确认。
- **`run_python` 跨调用无状态**(每次全新子进程),所以题面里用 base64 内嵌的附件,agent 每次
  调用都得把整段重新粘进代码。附件一大(如几 KB 的 WAV),DeepSeek 会陷入「反复粘贴几乎相同的
  代码、不输出任何推理文字」的退化循环,把回合数耗光。**内嵌附件要尽量小**(forensics `wav_lsb`
  从 2000 样本/5.3KB 降到 ~400/1.1KB 缓解了机械负担)。(2026-11-11 起 `wav_lsb` 和 `ecb_paste`
  已能被 DeepSeek 解出——前者是模型变强了,后者靠 web prompt 补了分组密码攻击指导;能力边界现只剩
  `ai/firm`、`ai/both_filters`。)真要塞大件,现已有「可持久化工作区」机制(`run_python(workdir=...)`
  + `agent/categories/forensics/workspace.py`,见 `large_blob`),不再需要把大附件 base64 塞进 prompt。
- 本 harness 会缓冲后台/管道命令的 stdout；要看实时进度，让脚本把结果写进文件再读那个文件。

## 密钥与配置

模型 / API Base / API Key / 平台 token / 团队分工都存本地数据库
`~/.odele-ctf/sessions.db` 的 `settings` 表（文件权限 0600），可在控制台「配置管理」「团队」页直接改；
接口只返回打码值。`.env`（gitignored，由 `agent/config.py` 加载）与真实环境变量只作首次回退，
启动时 `backend.settings.apply_model_settings()` 会把这些值同步进 `os.environ` 与 `agent.config`
（worker 子进程通过环境继承）。**永远不要提交 key**——每次提交前，确认 `.env` 和数据库文件
都没被 staged、且 diff 里没有 key。

## 当前状态

已就绪(ready)的七个类型,共 **78 道题**:

- **web**:21 道题,DeepSeek 全解。SQLi / 命令注入 / SSRF / XXE / SSTI / JWT(alg:none、弱密钥、
  kid)/ 反序列化(pickle)/ 分组密码(ECB 剪切粘贴、CBC 翻转)/ 限流绕过 / session 伪造 等。
- **crypto**:24 道题,DeepSeek 几乎全解。古典(仿射/Vigenère/替换)、RSA(立方根/Fermat/Wiener/
  共模/Håstad/共因子/LSB oracle)、对称(CTR/GCM)、ECC、哈希/PRNG(LCG/梅森旋转)、格(SVP/LLL、HNP)。**能力边界**:
  `padding_oracle`、`ecb_byte_at_a_time`(跨多字节 oracle 编排打不穿,脚本可解;用 `agent/tools/oracle.py`
  批量查询)。
- **misc**:5 道题(brainfuck、compression_layers、xor_sequence、morse、pyjail),DeepSeek 全解。
  pyjail 用 `send_code` 工具打受限 eval。
- **forensics**:10 道题,DeepSeek 全解。文件雕刻 / 归档套娃 / pcap / 隐写(WAV、图像 LSB)/ HTTP
  chunked 协议还原。小附件 base64 嵌题面;大附件走**可持久化工作区**(`agent/categories/forensics/workspace.py`)。
  Pillow 已装。
- **pwn**:8 道题,DeepSeek 全解。**模拟**有漏洞的进程:溢出 / ret2win / 格式化串 / canary / 整数
  溢出 / shellcode(玩具 CPU)/ heap UAF(玩具分配器)。工具 = `send_input` + run_python。
- **ai**:5 关红队阶梯。naive / output_filter / input_filter 可解;firm 与 both_filters 是
  **能力边界**(LLM 打不动同款硬防御)。判结果要多跑(`--runs N`)。
- **reverse**:5 道题,DeepSeek 全解。工具 = `disassemble`(`objdump -d -s`)+ `run_binary` +
  run_python(含 z3):run_me、crackme_xor、crackme_serial、crackme_z3(符号求解)、custom_vm(字节码
  VM)。**angr 在 arm64 macOS 跑不动 Mach-O 符号执行**,用 z3 替代;真 angr 需 x86_64 Linux ELF
  (lld 已装,留待以后)。

> AI 类的血泪:把一个值叫作「secret flag」会让防御模型(DeepSeek)反射性死守,于是本该考
> **机械过滤器**的几关变成了考「能不能越狱模型」。修法:考过滤器的几关让防御模型**明确配合**
> (把值描述成可给的、不敏感的 reference code),挑战点就回到过滤器本身;只有 firm/both_filters
> 才真正考模型拒答。

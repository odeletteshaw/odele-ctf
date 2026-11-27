---
id: zip-symlink-arbitrary-file-read
name: zip 上传解压点：用 Unix 符号链接条目做任意文件读取（含 /proc 路径与关键字过滤绕过）
description: 上传接口解压 zip 并回显文件内容时，构造 create_system=3 + external_attr=0o120777 的符号链接条目指向任意路径，借服务端读取跟随链接拿到 /proc/self/environ 等敏感文件
tags: [web, harvested]
source: harvested
imported_at: 2026-11-27
---

# zip 上传解压点：用 Unix 符号链接条目做任意文件读取（含 /proc 路径与关键字过滤绕过）

## 触发信号
- 存在上传点，提交非 zip 时返回类似 `This file is not a zipfile`；提交正常 zip 后响应体直接是**解压出的文件内容**（多文件时内容被拼接回显）。
- 服务端是 Python/Flask（`zipfile` 模块）或任何「解压后读取某文件再返回」的逻辑。
- 直接 `GET /proc/self/environ`、`/app.py` 等路径 404，说明读取能力只存在于上传解压链路里，不在路由上。

## 步骤
1. 先确认回显语义：上传含 `aaa.txt=AAAA`、`bbb.txt=BBBB` 的 zip，若响应是 `AAAABBBB`，说明服务端遍历解压目录并回显每个文件内容 —— 这就是读取原语。
2. 用 Python 构造**符号链接条目**（不是 zip-slip 的 `../` 文件名，后者常被 `zipfile` 的路径规范化或服务端 `os.path.basename` 吃掉）：
   ```python
   import zipfile, io, base64
   b = io.BytesIO()
   with zipfile.ZipFile(b, 'w') as z:
       zi = zipfile.ZipInfo('test.txt')      # 条目名 = 服务端随后会读取的文件名
       zi.create_system = 3                  # 3 = Unix，否则解压器不认 symlink 位
       zi.external_attr = (0o120777 << 16)   # S_IFLNK | 0777
       z.writestr(zi, '/proc/self/environ')  # 条目内容 = 链接目标
   print(base64.b64encode(b.getvalue()).decode())
   ```
   把 base64 直接作为 multipart 文件体上传（`field` 用页面表单里的字段名，如 `the_file`）。
3. 目标路径优先级：`/proc/self/environ`（flag 常以环境变量注入，一次命中）→ `/proc/self/cmdline`、`/proc/self/cwd/<app>.py`、`/proc/1/cwd/...`（定位源码与工作目录）→ `/etc/passwd`（验证读取确实生效）。
4. 若目标路径含被过滤的关键字（如 `flag`）而返回 302/`?error=1`，改用不含关键字的等价路径：`/proc/self/environ`、`/proc/self/cwd/` 下猜文件名、`/proc/self/root/...`，或先读源码确认 flag 的真实位置。

## 证据/验证
- 上传 symlink→`/etc/passwd` 返回 passwd 内容、symlink→`/proc/self/environ` 返回 `KEY=VALUE\0KEY=VALUE` 串，即证明解压器保留了 symlink 且读取端跟随链接。
- 同一 symlink 指向含被过滤词的路径时返回 302 重定向而非内容，说明存在路径关键字黑名单，而非读取失败。

## 坑
- **必须设 `create_system=3`**：默认 `create_system=0`（Windows）时 `external_attr` 的高 16 位不被当作 Unix mode，解压出来是普通文件，内容就是那串路径字符串，看起来「读到了但没内容」。
- 条目名要与服务端读取的文件名一致（常见是固定名或遍历目录），否则链接建好了却没人读。
- 别只试 zip-slip 的 `../../etc/passwd` 条目名：很多实现会 `os.path.basename` 或拒绝 `..`，symlink 才是稳定通道。
- `/proc/self` 指向的是**执行读取的那个进程**（可能是 `cat` 子进程），其 cwd 未必是应用目录；要拿应用源码时同时试 `/proc/1/cwd/`、`/proc/self/cwd/` 与 `/proc/<pid>/environ`。
- 环境变量里 flag 常以 `FLAG=...` 形式出现，回显是 NUL 分隔的，注意在响应里按 `\x00` 切分再 grep。

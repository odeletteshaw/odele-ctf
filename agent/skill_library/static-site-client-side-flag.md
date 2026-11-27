---
id: static-site-client-side-flag
name: 纯前端站点：先抓首页引用的 JS/CSS 再谈漏洞，flag 常硬编码在客户端逻辑里
description: 首页是游戏/工具类纯静态页时，优先把 HTML 里 <script src>/<link href> 引用的资源全部拉下来读源码；flag 常明文写在触发条件分支里，无需真玩到目标分数或构造服务端利用。
tags: [web, recon, harvested]
source: harvested
imported_at: 2026-11-27
---

# 纯前端站点：先抓首页引用的 JS/CSS 再谈漏洞，flag 常硬编码在客户端逻辑里

## 触发信号
- 首页 HTML 极短（几百字节），只有 `<title>`、`<link rel="stylesheet">`、`<script src="xxx.js">`、`<body onload="main()">`，正文几乎为空。
- 页面文案给出「达成某条件即可获得 flag」的提示（如「得到 4096 的方块即可获得 flag 哦」）。
- 响应头是静态文件指纹：`etag: "2af8-5cbdd275a6600-gzip"`、`last-modified` 为固定旧日期、`accept-ranges: bytes`、`content-type: application/javascript`；无 `Set-Cookie`、无表单、无动态路由。
- 同一站点两个入口（如 openresty 反代 + Apache 源站）返回**完全相同的 ETag/Last-Modified**，说明是同一份静态文件，不存在「另一个后端」。

## 步骤
1. `GET /` 读完整 HTML，把其中所有 `src=` / `href=` 的相对路径列出来（`2048.js`、`2048.css`、`favicon.ico` 之类）。
2. 逐个 `GET` 这些资源，**读全文而不是只看前 200 字节**——工具输出常被截断，flag 往往在文件后半段的判定函数里。
3. 在 JS 里 grep 语义锚点：`flag`、`confirm(`、`alert(`、`win`、`胜利`、`== 4096`、`score`。判定分支形如：
   ```js
   if (map[i][j] == 4096) { confirm("游戏胜利\nDASCTF{...}"); }
   ```
   明文 flag 直接就在字符串里。
4. 若 JS 被混淆（`_0x...` 调用、`atob`/`decodeURIComponent`/RC4），转去按混淆还原流程静态解密，**不要**试图在浏览器里真玩到目标分数。
5. 只有在 JS 里找不到任何 flag 痕迹时，才回头做备份文件/目录枚举（`/www.zip`、`/.git/config`、`/robots.txt` 等）。

## 证据
- 首页 670 字节、`server: openresty`、`etag: "65f-..."`；`/2048.js` 2080 字节、`content-type: application/javascript`，其中 `judge()` 内含 `confirm("游戏胜利\nDASCTF{...}")`。
- 两个目标（openresty:80 与 Apache:9999）返回同 ETag 同 Last-Modified，证明是同一静态站点，无需再找「真后端」。

## 坑
- **别把「达成条件」当成必须完成的任务**：条件只是 flag 的显示时机，源码里是明文，静态读取即可。
- **别只读响应前几百字节就下结论**：`http_request` 的正文常被截断，flag 在文件尾部；必要时重新请求并确认看到 `confirm(` 那一行。
- **别在纯静态站点上继续堆注入/反序列化/SSRF 载荷**：无参数、无 Cookie、无 PHP 路由时，`/admin`、`/api`、`/flag.php`、`/www.zip` 全 404 是预期结果，继续 fuzz 只是浪费请求。
- 报告 flag 前务必在**本次工具输出**里看到完整字符串（含花括号内全部字符），不要凭记忆或从上一轮摘要里抄。

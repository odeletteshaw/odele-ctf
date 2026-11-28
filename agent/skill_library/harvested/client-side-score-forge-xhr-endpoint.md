---
id: client-side-score-forge-xhr-endpoint
name: 客户端计分游戏：从 JS 提取 XHR 提交接口，直接伪造分数绕过前端条件
description: 纯前端 Canvas 游戏把分数由客户端计算并 POST 给后端时，从 JS 里抠出接口与请求体形状，直接重放伪造分数即可拿 flag，无需真玩。
tags: [web, harvested]
source: harvested
imported_at: 2026-11-27
---

# 客户端计分游戏：从 JS 提取 XHR 提交接口，直接伪造分数

## 触发信号
- 首页是 Canvas 小游戏（飞机大战/2048/贪吃蛇），HTML 极短，逻辑全在 `app*.js` / `game*.js` 里。
- 题目描述是「听说你是游戏高手？」这类暗示「达成高分/通关」的文案。
- 站点静态文件指纹明显（`etag`/`last-modified`/`accept-ranges`），但存在一个动态后端（响应头出现 `x-powered-by: PHP`，或某个 `.php` 路径返回 JSON）。
- 两个入口（如 openresty:80 与 Apache:9999）返回**相同 ETag/Last-Modified** → 同一份静态资源，不必再找「另一个后端协议」。

## 步骤
1. `GET /` 读 HTML，列出所有 `<script src>`；把 JS 用 `download_file` 存盘后 `run_python` 打印全文（`http_request` 正文会被截断，别只看前 200 字节）。
2. 在 JS 里 grep 语义锚点：`xhr`、`fetch(`、`open(`、`send(`、`JSON.stringify`、`score`、`gameScore`、`> 100000`、`alert(`、`message`。典型片段：
   ```js
   if (gameScore > 100000) {
     var xhr = new XMLHttpRequest();
     xhr.open("POST", "/api.php", true);
     xhr.setRequestHeader("Content-Type", "application/json");
     xhr.send(JSON.stringify({ score: gameScore }));
   }
   ```
   由此得到三要素：**路径**（`/api.php`）、**方法+Content-Type**（POST JSON）、**请求体字段名**（`score`）。
3. 判断分数是否可信：若 `gameScore` 只在客户端 `+= 10/20/100` 累加、请求体里没有签名/nonce/HMAC/时间戳，则服务端无法验证 → 直接伪造。
4. 用 `http_request` 重放，字段值取**刚好越过阈值**的数（阈值 100000 → 发 100001），避免触发「分数过高」之类的合理性校验：
   ```
   POST /api.php
   Content-Type: application/json

   {"score": 100001}
   ```
   响应 `{"message":"<flag>\n"}` 即成功。
5. 若返回「分数不合法/需要 token」，再回头读 JS 看是否有 `sign`/`md5`/`token` 字段，按同样方式在本地计算后带上。

## 证据
- 首页 `server: openresty`，`/app_v2.js` 中 `gameover()` 分支：`gameScore > 100000` 时 `xhr.open("POST","/api.php")` + `JSON.stringify({score: gameScore})`。
- `POST /api.php` 带 `{"score":100001}` → `200`，`x-powered-by: PHP/7.3.15`，正文 `{"message":"<flag>"}`。
- 反证：`/robots.txt`、`/www.zip`、`/.git/config`、`/admin`、`/flag`、`/api` 全 404，说明入口就是 JS 里那一个接口，无需继续目录爆破。

## 坑
- **别真去玩到目标分数**：分数是客户端变量，改 JS 或直接发请求都行；玩到 10 万分纯属浪费。
- **别只 fuzz 目录**：`/api`、`/score`、`/game` 全 404 是正常的，真实路径是 `/api.php` 这种带扩展名的，只能从 JS 里读出来。
- **Content-Type 要对**：后端按 JSON 解析时，用表单编码发 `score=100001` 会得到空/报错；必须 `Content-Type: application/json` + 合法 JSON 体。
- **阈值边界**：条件是 `>` 而非 `>=`，发等于阈值的数可能不触发；取阈值 +1 最稳。
- **两个入口别重复侦察**：ETag/Last-Modified 相同即同一份静态文件，第二个入口（不同端口/不同 Web 服务器）通常只是同一站点的另一条路径，不必再找「TCP 协议题」。
- **run_python 沙箱无网络/DNS**：想探 TCP 端口只能走 `http_request`，别在 Python 里 `socket.create_connection` 到题目域名，会 `gaierror`。

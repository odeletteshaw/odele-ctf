---
id: web-method
name: Web 专家清单
description: 先按题面锁定漏洞类，再用最小 payload 验证，响应就是 oracle。
tags: [method, web]
---

# Web 专家清单

**一句话**：先按题面锁定漏洞类，再用最小 payload 验证，响应就是 oracle。

## 快速路径

1. 读首页/表单/接口，列出所有输入点（query、body、header、cookie、路径）。
2. 按类验证：SQLi → 鉴权/IDOR → 命令注入 → 文件包含/穿越 → SSRF → XXE → SSTI →
   反序列化 → 业务逻辑。
3. 用 `search_knowledge` 调类别技术卡；用 `search_role_skill` 调本角色清单。
4. 需要计算/编码/爆破时先 `run_python`，并把结果原样复制到请求里。

## 证据习惯

- 每个结论附「请求 + 响应片段」；不要凭感觉判断过滤规则。
- 同一路径换 header 不等于换攻击；响应不变就换 payload 或攻击类。
- 发现备份/源码线索先下载再读，不要在文本响应里猜二进制。

## 导入记录（2026-11-27）
- auth-bypass
- brute-force
- csrf
- file-leak
- file-upload
- go
- http-request
- index
- info-gathering
- java
- js
- logic-vuln
- node
- nosql
- php
- python
- ruby
- sql-injection
- ssrf
- windows
- xss
- xxe

---
id: recon-method
name: 信息收集清单
description: 漏洞利用前的前置侦察：系统枚举入口/参数/指纹/泄露面与防御形状，产出可指回原始响应的事实清单，再交给方向专家。
tags: [method, recon]
---

# 信息收集清单

**一句话**：漏洞利用前的前置侦察——系统枚举攻击面、留下可指回原始响应的证据，再交给方向专家；
只摸清不利用。

## Web

- 入口与输入点：表单、查询参数、JSON 字段、Header、Cookie、上传点。
- 路由与文件：robots.txt、sitemap、备份（www.zip/.bak）、`.git`、源码、配置。
- 技术栈指纹：响应头（`Server`/`X-Powered-By`）、报错页、框架特征、默认路径，定位语言/框架/中间件以选攻击面。
- 隐藏入口：对比前端提交字段与后端接受字段——多塞一个前端没发的 JSON/表单字段常解锁隐藏逻辑；
  注释、JS bundle 里的 API 路径 / AccessKey、历史资产（旧 JS 引用的已删接口）。
- 防御形状：过滤器 ban 了哪些字符/关键字、哪些对象/全局可用、哪条链被拦（为专家省去重复试探）。
- 记录格式：`方法 路径 参数 → 状态码 + 关键响应片段`。

## 文件与二进制

- Magic bytes、长度、尾部附加数据、嵌套归档、字符串。
- 二进制：triage → strings → 只读反汇编片段；不要执行未知程序。

## 纪律

- 不做完整利用，不做破坏性操作；顺手拿到 flag 除外。
- 未验证的写「未验证」，不要写成结论；排除项也记录（例如「/admin 404」）。
- 输出分两类：**可利用信息** 与 **排除项/负结果**。

## 导入记录（2026-11-27）
- ai-index
- ai-info-gathering
- crypto-index
- misc-index
- pwn-index
- reverse-index
- web-index
- web-info-gathering

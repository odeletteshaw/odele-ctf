# 信息收集清单

**一句话**：先摸清目标面和证据，再交给专家；每条事实都要能指回原始响应。

## Web

- 入口与输入点：表单、查询参数、JSON 字段、Header、Cookie、上传点。
- 路由与文件：robots.txt、sitemap、备份（www.zip/.bak）、`.git`、源码、配置。
- 技术栈：响应头、报错页、框架指纹、默认路径。
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

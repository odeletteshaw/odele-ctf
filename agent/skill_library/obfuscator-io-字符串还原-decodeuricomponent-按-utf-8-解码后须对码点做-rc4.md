---
id: obfuscator-io-字符串还原-decodeuricomponent-按-utf-8-解码后须对码点做-rc4
name: obfuscator.io 字符串还原：decodeURIComponent 按 UTF-8 解码后须对码点做 RC4
description: 还原 atob→%XX→decodeURIComponent→RC4 链时，decodeURIComponent 把 %XX 当 UTF-8 解码，结果字符串码点可 >255，RC4 必须异或 charCodeAt 码点而非原始字节。
tags: [web, reverse, harvested]
source: harvested
imported_at: 2026-11-27
---

# obfuscator.io 字符串还原：decodeURIComponent 按 UTF-8 解码后须对码点做 RC4

## 触发信号
JS 里出现 `_0x57fd('0x1','dhCd')` 这类「索引 + 调用点密钥」的字符串数组调用，函数体含自定义 `atob`、`'%'+('00'+charCodeAt(i).toString(16)).slice(-2)` 拼串、`decodeURIComponent`、以及 RC4 的 KSA/PRGA 循环。

## 步骤
1. 抓全 JS，grep 语义锚点（`flag`/`alert`/`win`/`coin`）定位调用点，把「索引 → 密钥 → 密文」三者成对抄下。
2. 严格按 JS 语义复现，**关键在第三步**：
   - `atob(b64)` → `base64.b64decode`，得原始字节；
   - 拼 `%XX` 串后 `decodeURIComponent`：**它把 %XX 当 UTF-8 解码**，等价于 `urllib.parse.unquote_to_bytes(pct).decode('utf-8')`；
   - 得到的 JS 字符串里，非 ASCII 字节已被合并成多字节字符，**`charCodeAt` 返回的是码点（可 >255）**；
   - RC4 的 PRGA 用 `ord(ch)` 码点与 keystream 异或，再 `chr()` 拼回。
3. 每个调用点分别解，多段 flag 常拆在不同分支（如 `coin == 0xc8` 与 `coin > 0xf4240`），需全部解出再拼接。

## 证据/验证
- 正确时输出为可读英文句子（`You really ... this is your flag1: XXX`）。
- 交叉验证：同一密文用 Python 手写实现与 Node 直接执行原函数，明文必须一致。

## 坑
- **最易错点：把 decodeURIComponent 的结果当原始字节去异或**。这样 keystream 与码点错位，输出是「看起来接近明文」的乱码（如 `co(\xe3\x83`、`co`Äp`），极易误判成密钥抄错而反复换 key。
- 判据：若解出前几个字符像明文、后面全乱，几乎一定是字节/码点语义错了，而不是 key 错。
- 不要用 `raw.decode('latin-1')` 绕过 UTF-8 解码——那正是错误路径。
- 分支被代码钳制（如 `if (coin > 999999) coin = 999999`）导致运行时不可达时，静态解密依然有效，不要放弃该分支密文。

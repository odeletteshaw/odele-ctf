---
id: js-obfuscator-string-array-rc4
name: javascript-obfuscator 字符串数组还原：atob→decodeURIComponent→RC4 链的字节语义
description: 还原 obfuscator.io 风格「base64 + 调用点传 RC4 密钥」的字符串数组时，按 JS 语义逐步复现解码链，避免 latin-1/UTF-16 误用导致乱码。
tags: [web, reverse, harvested]
source: harvested
imported_at: 2026-11-27
---

# javascript-obfuscator 字符串数组还原：atob→decodeURIComponent→RC4 链的字节语义

## 触发信号
静态站点（游戏/小游戏/纯前端页）的某个 JS 里出现形如 `_0x57fd('0x1','dhCd')`、`_0x2c19('0x1','GK)i')` 的调用：第一个参数是字符串数组索引，第二个参数是**调用点传入的短密钥**；函数体里有 `atob`/`decodeURIComponent`/`charCodeAt`/`fromCharCode` 与一个 RC4 风格的 KSA/PRGA 循环。语义锚点（`flag`、`alert`、`win`、`coin`）通常就在这些调用点附近。

## 步骤
1. 抓全 JS（`http_batch` 一次拉 `/src/*.js`、`/src/views/*.js`），先 grep 语义锚点定位可疑文件，再读该文件里的解码函数体。
2. 逐行把函数体翻译成 Python，**严格按 JS 语义**：
   - `atob(s)` → `base64.b64decode(s)`，得到**原始字节**；
   - 混淆器通常把字节拼成 `%XX` 串再 `decodeURIComponent`：即 `bytes.fromhex` 式还原，等价于 `urllib.parse.unquote_to_bytes(raw.decode('latin-1'))`；
   - 结果再按 `charCodeAt(i)` 取**码点**（0–255）与 RC4 keystream 异或，最后 `String.fromCharCode` 拼回。
3. RC4 用标准 KSA/PRGA，key 取**调用点第二个参数**（不是全局 key），且 key 是 ASCII 字节。
4. 对每个可疑调用点分别解，打印明文；两段 flag 常被拆到两个不同分支（如 `coin == 0xc8` 与 `coin > 0xf4240`），需要**两个调用点都解**再拼接。

## 证据/验证
- 解出的明文应是可读英文句子（如 `You really ... this is your flag1: XXX`），出现可读句子即说明链正确；乱码说明某一步的字节/码点语义错了。
- 交叉验证：同一段密文用两种实现（Python 手写 / Node 直接执行原函数）应得到同一明文。

## 坑
- **不要把 base64 解码结果直接当 UTF-8 文本**：`raw.decode('utf-8')` 会抛错或替换字符，必须走 latin-1/字节路径。
- **不要用 `ord()` 对已解码的 str 取码点再异或**：若中间误用 UTF-8 编码，多字节字符会让 keystream 错位，输出看似「接近明文」的乱码（如 `co(\xe3\x83`），极易误判为密钥错。
- **密钥与索引要配对**：同一索引在不同调用点可能配不同 key，抄错 key 只会得到乱码；把「索引→key→密文」三者一起抄下来。
- 若分支条件被代码钳制（如 `if (coin > 999999) coin = 999999`），该分支运行时不可达，但**静态解密仍然有效**——不要因为「玩不到」就放弃该分支的密文。

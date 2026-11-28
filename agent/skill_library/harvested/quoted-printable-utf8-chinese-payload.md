---
id: quoted-printable-utf8-chinese-payload
name: Quoted-printable 中文载荷：=XX 三元组按 UTF-8 字节还原，勿按 GBK/URL 误读
description: 附件文本全为 =XX 三元组时用 quopri.decodestring 得字节再按 UTF-8 解码；用「字节数=三元组数」与码点表自证，排除 GBK/URL 误读
tags: [misc, crypto, harvested]
source: harvested
imported_at: 2026-11-27
---

# Quoted-printable 中文载荷：=XX 三元组按 UTF-8 字节还原，勿按 GBK/URL 误读

## 触发信号
- 容器（zip/邮件原文/文本附件）里只有一个 txt，内容形如 `=E9=82=A3=E4=BD=A0...`：整串由 `=` + 两位大写 hex 组成，无 `%`、无换行、无软换行 `=\r\n`。
- 容器目录名/文件名直接写着 `Quoted-printable`（或 `QP`、`quoted printable`），即编码方式提示。
- 题目描述只有「得到结果请包上 xxx{} 提交」，说明是单层编码题。

## 步骤
1. 读原始字节并 `repr()`，确认字符集只有 `=`、hex 数字（`all(32<=c<127 for c in raw)`），且长度是 3 的倍数。
2. 用标准库解码，**先得字节再解字符集**，两步分开：
   ```python
   import quopri
   dec = quopri.decodestring(raw)          # 得到原始字节，不要直接 decode
   s = dec.decode('utf-8')                 # 中文 QP 载荷几乎总是 UTF-8
   ```
3. 自证（关键，避免「看起来对」的误读）：
   - `len(raw)//3 == len(dec)`：每个 `=XX` 恰好还原 1 字节，例如 18 个三元组 → 18 字节 → 6 个三字节汉字，无冗余字节；
   - 打印 `dec.hex()` 与 `[hex(ord(c)) for c in s]`，码点应落在 CJK 区（U+4E00–U+9FFF）；
   - 检查 `unicodedata.category(c)` 全为 `L`，确认无零宽字符/BOM/尾随空格。
4. 结果已是可读中文短语即停手，按题目要求包上外层花括号格式（中文原文直接包，不做拼音转写）。

## 证据
- 本次：54 字节载荷 = 18×`=XX`，`quopri.decodestring` 得 18 字节 UTF-8 序列，解码为 6 个汉字，码点全部为 CJK 字母类，无隐藏字符；`len(raw)//3 == len(dec)` 成立。
- 反证：同一字节串按 GBK 解读得到乱码（形如 `閭ｄ綘涔熷緢妫掑摝`），说明字符集必须是 UTF-8；`urllib.parse.unquote` 对 `=XX` 无作用（`=` 后非 `%`），排除 URL 编码路径。

## 坑
- **别把 `=XX` 当 URL 百分号编码**：URL 用 `%HH`，QP 用 `=HH`；`unquote` 会原样返回，容易误判成「解码失败」。
- **别先 `raw.decode('utf-8')` 再处理**：`=E9` 是 ASCII 文本，必须先 `quopri.decodestring` 还原字节，顺序反了永远解不出中文。
- **别用 GBK/latin-1 兜底**：中文 QP 载荷是 UTF-8 字节流，GBK 解读会得到「形似中文的乱码」，比报错更危险（会误以为解出来了）。
- **别把中文结果转拼音/英文再提交**：题目只说「包上外层花括号」是格式要求，不是转写要求；把中文原文改成拼音变体属于自造答案。
- 若载荷含软换行 `=\r\n`，`quopri.decodestring` 会自动去掉；但若出现 `=3D`（转义的 `=` 本身），说明原文含字面 `=`，不要手工 split。

---
id: misc-attachment-magic-and-name-hints
name: misc 附件：先按魔数判真实格式，再用条目名/目录名当解码提示
description: 拿到小体积 misc 附件时，先读前 64 字节魔数确认容器格式，再列 zip 条目；条目/目录名（如「Url编码」）常直接给出编码方式，按提示单层解码即可，不要盲目堆多层解码。
tags: [misc, crypto, harvested]
source: harvested
imported_at: 2026-11-27
---

# misc 附件：先按魔数判真实格式，再用条目名/目录名当解码提示

## 触发信号
- 题目只给一个几百字节的附件（zip/rar/图片/文本），描述只有「得到结果请包上 xxx{} 提交」，没有任何算法/参数说明。
- 附件文件名带 HTTP 头残留（`xxx.zip"; filename*=UTF-8''xxx.zip`），说明是从下载响应里直接落盘的，别被名字骗了。

## 步骤
1. **先看魔数，别信扩展名**：`open(fn,'rb').read(64)` 后 `binascii.hexlify`。`504b0304`=ZIP、`52617221`=RAR、`89504e47`=PNG、`ffd8ff`=JPEG、`1f8b`=gzip。魔数决定用哪个库，扩展名只作参考。
2. **列容器条目**：`zipfile.ZipFile(fn).infolist()` 打印 `filename / file_size / compress_size / compress_type / flag_bits`。
   - `flag_bits != 0` → 有加密条目，转 zip 明文攻击/口令爆破方向；
   - 只有目录 + 一个 txt → 纯编码题，直接读内容；
   - 条目名本身是乱码/非 UTF-8 → 用 `cp437` 重新解码条目名（`i.filename.encode('cp437').decode('gbk')`）。
3. **把条目名/目录名当提示读**：中文目录名常直接写编码方式（`Url编码`、`base64`、`rot13`、`摩斯`、`栅栏`）。按提示做**单层**解码，先验证结果是否已是目标格式（`xxx{...}`）。
4. 解码工具对应关系：URL 百分号 → `urllib.parse.unquote`（`%HH` 逐字节，`%20` 是空格）；hex → `bytes.fromhex`；base64 → `base64.b64decode`（补 `=`）；base32 → `b32decode`；rot13 → `codecs.decode(s,'rot13')`。
5. 解出目标格式就停手，不要继续套解码（会把已正确的结果破坏成乱码）。

## 证据
- 小体积附件前 64 字节 hex 以 `504b0304` 开头 → 标准 ZIP；`infolist()` 显示一个 0 字节目录 + 一个 39 字节 deflate 文本条目，`flag_bits=0` 未加密，无额外数据流。
- 文本内容全为 `%HH` 形式，`unquote` 后直接得到完整目标串，无需二次解码。

## 坑
- **别被文件名里的引号/分号坑到**：`xxx.zip"; filename*=UTF-8''xxx.zip` 这种名字在 shell 里会被拆开，用 `[f for f in os.listdir('.') if f.endswith('.zip')][0]` 取，不要手写路径。
- **工作目录会变**：每次 `run_python` 的 cwd 可能不同（临时目录），上一次看到的 `snippet_*.py` 下次可能不存在；用 `os.getcwd()` + `os.listdir('.')` 重新确认，别硬编码文件名。
- **不要因为「太简单」就继续套 base64/rot13**：目录名已指明编码方式时，单层解码即答案；多层解码只会把已正确的结果弄坏。
- 内容里的 SQL 注入风格趣味文案只是文本，不是需要利用的注入点，别跑偏去做 SQLi。

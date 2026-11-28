---
id: rsa-text-params-solve-d
name: RSA 参数题：从中文题干提取 p/q/e 求 d，并用 (e·d) mod φ = 1 自证
description: 附件 txt 只给 p、q、e 要求求 d 时，用 pow(e,-1,φ) 一步求解，并以 (e·d) mod φ=1 与 gcd(e,φ)=1 自证，避免把 d 当密文继续解。
tags: [crypto, misc, harvested]
source: harvested
imported_at: 2026-11-27
---

# RSA 参数题：从中文题干提取 p/q/e 求 d，并用 (e·d) mod φ = 1 自证

## 触发信号
- 附件（常为 zip 内单个 txt）内容是一句中文题干，形如「在一次RSA密钥对生成中，假设 p=…，q=…，e=… 求解出 d 作为答案提交」。
- 题干里**没有密文 c**，只有 p、q、e 三个参数；要求提交的是 d 本身，而不是解密后的明文。
- 目录名/文件名直接写着 `RSA`，题目描述只有「把某前缀替换为外层格式，格式 xxx{}」这类格式要求。

## 步骤
1. 解包并**按 GBK 解码**（国内老题 txt 多为 GBK/GB2312，UTF-8 会抛 UnicodeDecodeError）：
   ```python
   import zipfile, os, re, math
   fn = [f for f in os.listdir('.') if f.endswith('.zip')][0]
   z = zipfile.ZipFile(fn)
   name = [i.filename for i in z.infolist() if not i.is_dir()][0]
   raw = z.read(name)
   try:    s = raw.decode('utf-8')
   except UnicodeDecodeError: s = raw.decode('gbk')
   print(repr(s))
   ```
2. **用正则从题干抽参数**，不要手抄数字（长整数手抄极易错位）：
   ```python
   p, q, e = (int(x) for x in re.findall(r'=\s*(\d+)', s)[:3])
   ```
   若题干顺序不是 p/q/e，改用带标签的正则：`re.search(r'p\s*=\s*(\d+)', s)` 等。
3. 求私钥指数，**优先用 Python 3.8+ 的三参 pow**（内部走扩展欧几里得，比手写 inverse 快且不会溢出）：
   ```python
   phi = (p - 1) * (q - 1)
   assert math.gcd(e, phi) == 1          # 不互素则 pow 会抛 ValueError，见「坑」
   d = pow(e, -1, phi)
   ```
4. **自证（必做，这是本题唯一可验证点）**：
   - `(e * d) % phi == 1`；
   - `d < phi` 且 `d > 0`；
   - 若题干给了 c，再补 `pow(pow(c, d, n), e, n) == c % n` 与 `pow(m, e, n) == c`。
5. 按题目要求包外层格式提交：题干里的 `flga` 之类是出题人笔误，按描述统一成正确前缀。

## 证据
- 本次：zip 内单个 txt 共 79 字节，原始字节以 GBK 的「在一次」双字节序列开头，UTF-8 解码失败、GBK 解码得到完整中文题干；正则抽出三个参数，`gcd(e,φ)=1`，`pow(e,-1,φ)` 得 d，`(e*d) % φ == 1` 成立。
- 反证：题干中不存在任何密文/编码串，容器无加密条目、无注释、无额外数据流，排除「还有一层编码」与「需要解密 c」两种误判。

## 坑
- **别把 d 当密文去解密**：题干说「求解出 d 作为答案提交」，d 就是答案本身；再去找 c 或对 d 做 base64/hex 变换都是自造答案。
- **别手抄大整数**：p、q 常是 12 位以上，手抄一位就全错且无法察觉；一律正则提取 + 打印回显核对。
- **编码别默认 UTF-8**：中文题干 txt 常见 GBK；`raw.decode('utf-8')` 抛异常时立刻换 `gbk`，不要用 `errors='ignore'`（会吞掉数字）。
- **gcd(e, φ) ≠ 1 时 `pow(e,-1,phi)` 直接抛 ValueError**：这不是「题目坏了」，而是 e 与 φ 不互素，需转「分模求解 + 单位根补候选 + CRT 合并」，候选数 = gcd(e, φ)。
- **φ 用 (p-1)(q-1)，不是 p*q-1**：这是最常见的低级错误，且结果仍能通过「看起来像随机数」的直觉检查。
- **提交前重跑一次并打印**：从上一轮摘要抄 d 容易漏位；`print(d, (e*d)%phi)` 一次输出即可自证。

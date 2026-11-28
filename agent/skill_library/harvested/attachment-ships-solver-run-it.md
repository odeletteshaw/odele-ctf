---
id: attachment-ships-solver-run-it
name: 附件自带求解脚本：直接移植执行，别另起攻击方向
description: zip 内是出题人自带的穷举/求解脚本时，先移植到 Python3 跑一遍（先算空间），命中后用摘要子串条件自证，不要另起字典/字符集暴力。
tags: [crypto, misc, harvested]
source: harvested
imported_at: 2026-11-27
---

# 附件自带求解脚本：直接移植执行，别另起攻击方向

## 触发信号
- 解包后容器里**没有密文/参数文件**，只有一个几十到几百字节的 `.py`（也可能是 `.c`、`.sage`、`.sh`），文件名/目录名直白（`md5.py`、`brute.py`、`solve.py`）。
- 脚本里出现 `for i in range(32,127)` 之类的嵌套循环 + `hashlib.md5()` + `if 'xxxx' in des` 形式的**摘要子串过滤**，或 `print des` 这类 Python 2 语法。
- 题目描述只有「得到结果请包上 xxx{} 提交」，没有任何算法说明 —— 说明算法就在脚本里，不需要猜。

## 步骤
1. 先 `repr(z.read(name))` 打印脚本原文，**判断它是「求解器」还是「加密器」**：出现 `if ... in des` / `== target` 且循环变量是未知字符 → 求解器，直接跑；出现 `random`/`os.urandom`/密钥生成 → 加密器，才需要另找攻击。
2. **先算空间再跑**：`(127-32)**3 ≈ 857k` 次哈希在纯 Python 里 1~2 秒，安全；若未知字符数 ≥5（95^5 ≈ 7.7e9）则不能直接跑，需换 meet-in-the-middle 或 C 加速。
3. 移植到 Python 3 只需两处改动：
   - `print des` → `print(des)`；
   - `m.update('...')` 的 str 参数 → `m.update(s.encode())`（Python 3 的 hashlib 只收 bytes，否则 `TypeError: Unicode-objects must be encoded`）。
   其余逻辑（`chr(i)`、`range(32,127)`、子串判断）原样保留。
4. 收集**全部**命中而不是只打印第一个：`hits.append((s,d))`，最后 `print(hits, len(hits))`。唯一命中即答案；多命中说明过滤条件太松，需补条件。
5. 自证：把命中的明文重新 `hashlib.md5(plain.encode()).hexdigest()` 与脚本里的过滤子串逐条比对（`'e9032' in d`、`'da' in d`、`'911513' in d` 全为 True），并打印 `repr(plain)` 确认无多余空白。
6. 按题目要求包外层格式提交；**答案通常是摘要本身**（脚本只 `print des`，不 print 明文），所以提交的是 hexdigest，不是明文串。

## 证据
- 本次：576B zip 内仅一个 332B 的 Python 2 脚本，无密文文件、无随机数；脚本对 `'TASC'+chr(i)+'O3RJMV'+chr(j)+'WDJKX'+chr(k)+'ZM'` 做 95³ 穷举，过滤条件为摘要含 `e9032`、`da`、`911513`。
- 移植后一次运行即得唯一命中，三个子串条件同时成立，`len(hits)==1`；容器无加密条目、无注释、无额外数据流，排除隐写与多层编码。

## 坑
- **别把「附件里有脚本」当成「附件里有密文」**：本题没有密文，任何「找 c 去解密」「猜密钥」的方向都是空转；先读脚本再定方向。
- **别跳过脚本去自建字典/字符集暴力**：脚本已经把明文模板（固定前后缀 + 3 个未知位）和过滤条件写死了，自建字典覆盖不到这种「模板 + 随机字符」形态，纯属浪费 15s 预算。
- **Python 2 → 3 的两个必改点**：`print x` 语法错误、`update(str)` 抛 TypeError；只改这两处，别顺手改 `range` 边界（`range(32,127)` 是含 32 不含 127，正好覆盖可打印 ASCII）。
- **提交的是摘要不是明文**：脚本 `print des` 说明出题人期望的答案就是 hexdigest；把明文串当 flag 提交会错。
- **多命中要警惕**：若过滤条件只有 `'da' in des` 这种 2 字符子串，命中数会爆炸（约 857k/256 ≈ 3k 个），必须用长条件（≥5 字符）或组合条件收敛到唯一解。

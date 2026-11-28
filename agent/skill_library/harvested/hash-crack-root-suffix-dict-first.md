---
id: hash-crack-root-suffix-dict-first
name: 哈希反查：无 hashcat/rockyou 时用「词根×后缀」组合字典优先于字符集暴力
description: 拿到裸 MD5/SHA1 时，先跑小规模「常见词根×数字/符号后缀」组合字典（千级候选），再考虑字符集暴力；后者在 15s 沙箱里几乎必然超时。
tags: [crypto, misc, harvested]
source: harvested
imported_at: 2026-11-27
---

# 哈希反查：无 hashcat/rockyou 时用「词根×后缀」组合字典优先于字符集暴力

## 触发信号
- 附件/页面里只有一个裸哈希串（32 位 hex = MD5，40 位 = SHA1），题目描述只有「得到结果请包上 xxx{} 提交」。
- 容器目录名/文件名直接写着 `MD5`、`hash`、`md5sum` 之类，说明这是哈希反查题，不是多层编码题。
- 沙箱里 `which hashcat john crunch` 全空，`/usr/share/wordlists` 不存在，只有 `/usr/share/dict/words`（英文词典，对口令类明文基本无效）。

## 步骤
1. 先确认哈希类型与长度，并试 `/usr/share/dict/*` 词典 + 大小写变体（成本低，几秒）。命中率低但零成本。
2. **主力：自建「词根 × 后缀」组合字典**。词根取口令高频词，后缀取常见数字与符号：
   ```python
   roots=['admin','root','test','guest','user','manager','system','secret','flag','ctf','md5','hash',
          'china','beijing','woaini','love','520','1314','iloveyou','password','pass','key','crypto',
          'hello','world','abc','qwe','asd','zxc','123','1234','12345','123456']
   sufs=['','1','12','123','1234','12345','123456','!','@','#','01','001','2020','2021','888','666']
   for r in roots:
       for s in sufs:
           for cand in (r+s, r.capitalize()+s, r.upper()+s):
               if hashlib.md5(cand.encode()).hexdigest()==h: print('HIT', cand)
   ```
   规模约 1.5k~4w 候选，纯 Python 一两秒跑完，命中率远高于同成本的字符集暴力。
3. 未命中再扩：加拼音/人名/站点名/年份、双词拼接（`admin`+`admin`）、`词根+分隔符+数字`（`admin_1`、`admin.123`）、leet 替换（`a→@`、`o→0`、`i→1`）。
4. 最后才考虑字符集暴力，且必须**先算空间再决定**（见坑）。
5. 命中后必须回验：`hashlib.md5(plain.encode()).hexdigest() == h`，并打印 `repr(plain)` 确认无多余空白/大小写差异；再按题目要求包 `xxx{...}`。

## 证据
- 本次：`/usr/share/dict` 34 万词全不命中；改用 1584 个「词根×后缀×大小写」候选即命中一个「单词+单数字」形态的明文，`md5(明文)` 精确等于目标哈希。
- 反证：首字母大写、全大写、补零（`01`）、下划线分隔等变体均不匹配，说明明文唯一、无需再做大小写或编码处理。
- 空间对比（说明为何暴力必败）：小写+数字 len≤5 = 6.2e7、len=6 = 2.2e9、纯数字≤7 = 1.1e7、纯小写≤5 = 1.2e7；15s 沙箱里纯 Python 连 1.7e6 都跑不完，C 版也就 ~2.5e7/s 量级。

## 坑
- **别一上来就字符集暴力**：「小写字母+数字、长度 6」的明文落在 alnum^6 = 2.2e9 空间里，任何 15s 限制下都跑不完；多轮把时间全耗在 digits≤8 / lower≤6 / alnum≤5 上，全部超时（exit -24）。
- **纯数字/纯小写/纯 alnum≤5 的暴力是「看起来系统」的陷阱**：它覆盖不到最常见的「词+数字」口令形态，命中率极低。
- **C 加速也要先算空间**：`clang -O3` 手写 MD5 约 2.5e7/s，1e8 就要 4s+，1e9 直接超时；分片（按首字符切 26 块）能绕过单次超时，但总时间仍是分钟级，不如换字典。
- **`/usr/share/dict/words` 不是口令字典**：它是英文词典，对「词+数字」、拼音类明文无效，别把它当 rockyou 用。
- **命中后别急着报结果**：先 `repr()` 打印明文并重算哈希比对，避免把带尾随空格或大小写变体的串当成答案。

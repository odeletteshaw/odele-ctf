# Forensics / 取证 — TODO

✅ **已就绪**。做法:把文件 **base64 嵌进题面**,agent 用 `run_python` 自己解析/雕刻——
和 crypto/misc 一样是「文本进 + 只给 run_python」,无需新工具,全程 hermetic。

## 已完成
- [x] `forensics/agent.py`(`solve_forensics` + 取证向 SYSTEM_PROMPT)
- [x] `forensics/evaluate.py`
- [x] 四道题(全部仅用 stdlib,脚本验证可解):
  - **trailing_data** — PNG 的 IEND 之后追加了 flag(文件雕刻)
  - **zip_nested** — 三层嵌套 zip,flag 藏在最内层的 **archive comment**
  - **pcap_stream** — libpcap,flag 拆散在**乱序** TCP 段里,按 seq 重组
  - **wav_lsb** — flag 藏在 16-bit PCM 采样的**最低位**(MSB-first,null 结尾)
- [x] 接入 `core/catalog.py`(ready)与 `gui/builder.py`(并入 text-in 分支)

## 接口
`DESCRIPTION: str` + `make(flag) -> str`(题面文本,内嵌 `file (base64) = ...`)。

## 以后可加(可能需要新依赖/工具)
- [ ] 图像 LSB 隐写 / EXIF 元数据 → 需 **Pillow**
- [ ] 真实 pcap + 协议还原(HTTP/DNS/FTP 提取文件)→ 可选 **scapy/dpkt**
- [ ] 磁盘镜像 / 文件系统雕刻、内存取证(volatility)→ 大件,可能需 `files_tool`
       (把大文件作为附件给 agent,而不是 base64 塞进 prompt)
- [ ] polyglot 文件、gzip/tar 套娃、哈希长度/CRC 碰撞类
- [ ] 办公文档宏 / PDF 对象流

> 注:现在只用 stdlib(struct/zlib/zipfile/wave/gzip/tarfile),所以沙箱无需装依赖。
> 要做图像/真实流量类再按需引入 Pillow/scapy,并写进 requirements.txt。

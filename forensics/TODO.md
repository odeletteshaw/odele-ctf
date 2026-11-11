# Forensics / 取证 — TODO

✅ **已就绪**。两种做法,按附件大小选:
- **小附件**:把文件 **base64 嵌进题面**,agent 用 `run_python` 解码/解析(和 crypto/misc 一样,
  「文本进 + 只给 run_python」)。
- **大附件**:走**可持久化工作区**——`make(flag)` 把文件写进一个持久临时目录(`Workspace`),
  agent 的 `run_python` 以该目录为 cwd,直接 `open()` 读文件、跨调用不重贴。全程 hermetic。

## 已完成
- [x] `forensics/agent.py`(`solve_forensics` + `solve_forensics_workspace` + 两段 SYSTEM_PROMPT)
- [x] `forensics/evaluate.py`(按返回值分派 str 文本 vs Workspace)
- [x] `forensics/workspace.py`:`Workspace`(持久临时目录 + 文件 + cleanup)
- [x] `core/sandbox.py` 的 `run_python(code, workdir=...)` + `tools/sandbox.py` 的
      `python_tool(workdir=...)`:传 workdir 时用持久目录,否则每次全新临时目录
- [x] 五道题(全部仅用 stdlib,脚本验证可解 + DeepSeek 全解):
  - **trailing_data** — PNG 的 IEND 之后追加了 flag(文件雕刻)
  - **zip_nested** — 三层嵌套 zip,flag 藏在最内层的 **archive comment**
  - **pcap_stream** — libpcap,flag 拆散在**乱序** TCP 段里,按 seq 重组
  - **wav_lsb** — flag 藏在 16-bit PCM 采样的**最低位**(MSB-first,null 结尾)
  - **large_blob** — ~1MB 文件,flag 在 magic marker 之后;走工作区(太大塞不进 prompt)
- [x] 接入 `core/catalog.py`(ready)、`gui/builder.py`(text-in 分支 + workspace 分支)

## 接口
- 小附件:`DESCRIPTION: str` + `make(flag) -> str`(题面文本,内嵌 `file (base64) = ...`)。
- 大附件:`DESCRIPTION: str` + `make(flag) -> Workspace`(文件已落盘,agent 从 cwd 读)。

## 以后可加(可能需要新依赖/工具)
- [ ] 图像 LSB 隐写 / EXIF 元数据 → 需 **Pillow**
- [ ] 真实 pcap + 协议还原(HTTP/DNS/FTP 提取文件)→ 可选 **scapy/dpkt**
- [ ] 磁盘镜像 / 文件系统雕刻、内存取证(volatility)→ 大件,可用 **Workspace**(已就绪)直接放文件
- [ ] polyglot 文件、gzip/tar 套娃、哈希长度/CRC 碰撞类
- [ ] 办公文档宏 / PDF 对象流

> 注:现在只用 stdlib(struct/zlib/zipfile/wave/gzip/tarfile),所以沙箱无需装依赖。
> 要做图像/真实流量类再按需引入 Pillow/scapy,并写进 requirements.txt。

# Forensics — TODO

⚠ **先建工具**:给 agent 对"附带文件"的只读访问(`tools/files.py`),加分析库
(PIL / scapy)和命令工具(binwalk / exiftool / strings / tshark)。然后实现
`forensics/agent.py: solve_forensics()`。

## 工具清单
- [ ] `tools/files.py`(列出/读取题目附带的 artifact,按目录隔离)
- [ ] 安装 Pillow、scapy;命令工具(binwalk / exiftool)
- [ ] solve_forensics + forensics/evaluate.py

## 子方向(靶题)
- [ ] 隐写:图像 LSB(把 flag 藏进像素最低位)
- [ ] 元数据:flag 藏在 EXIF / 文件尾
- [ ] 文件雕刻:ZIP/PNG 拼接,binwalk 提取
- [ ] pcap:从流量里还原文件 / 提取凭据
- [ ] 内存取证(volatility)— 较重,后置

> 起步建议:图像 LSB 隐写(用 PIL 生成,agent 用 PIL 提取),完全 hermetic。

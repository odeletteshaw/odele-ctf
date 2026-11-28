---
id: audio-morse-bandpass-hilbert-envelope
name: 音频摩斯题：时域包络不归零时改频域宽带瞬态 + 带通希尔伯特包络切分
description: 机器人嗓音/共振峰合成音频的摩斯题：时域 RMS 包络几乎不归零导致固定阈值切分失效；改用 2.5–3.5kHz 宽带瞬态 + 带通+希尔伯特包络 + 中值归一化自适应阈值切分元素。
tags: [misc, crypto, forensics, harvested]
source: harvested
imported_at: 2026-11-27
---

# 音频摩斯题：时域包络不归零时改频域宽带瞬态 + 带通希尔伯特包络切分

## 触发信号
- 附件是 mp3/wav，时长几十秒，听感是连续的「机器人嗓音 / 共振峰合成音」（类似 espeak、klatt），基频在 100~500 Hz 游走。
- 题目名/目录名带 robo、robot、beep、communication 之类暗示「机器在说话」。
- 用「响 → 静」固定阈值切分时，整段被判成一整块 on，或切出几百个碎片，看不到点划结构。

## 步骤
1. **先量化「时域包络不可用」这个事实，别凭感觉**。10 ms 帧 RMS：
   ```python
   hop=int(sr*0.01); n=len(x)//hop
   env=np.sqrt((x[:n*hop].reshape(n,hop)**2).mean(1))
   print(env.min()/env.max(), (env<0.1*env.max()).mean())
   ```
   实测这类合成音：`min/max ≈ 0.55`，低于 10% 峰值的帧占比 `0.000` —— 噪声底占峰值一半以上，**不存在静音段**，任何全局固定阈值必然失败。看到这两个数字就立刻放弃时域门限。
2. **换频域找元素边界**。`scipy.signal.spectrogram(x, fs=sr, nperseg=2048, noverlap=1536)`，看 0–3 kHz：会有一排贯穿全曲的竖直亮线（宽带瞬态/咔哒），每条竖线 = 一个摩斯元素的起点。量化判据：取 2.5–3.5 kHz 频带能量，`max/median` 可达 10^3 量级（对比时域只有个位数），信噪比高两三个数量级。
3. **带通 + 希尔伯特取包络**：
   ```python
   sos = signal.butter(4,[1800,3500],btype='bandpass',fs=sr,output='sos')
   y   = signal.sosfiltfilt(sos,x)          # 零相位，避免元素边界平移
   env = np.abs(signal.hilbert(y))
   ```
   5 ms 帧取 `max`（不是 mean，mean 会把短元素抹平）。
4. **自适应阈值**：用中值滤波做局部归一化再切，比全局阈值抗噪：
   ```python
   from scipy.ndimage import median_filter
   loc = median_filter(e, size=201)          # ~1 s 窗口
   on  = (e/np.maximum(loc,1e-12)) > 3.0
   ```
   合并间隔 < 30 ms 的碎片，丢弃 < 20 ms 的毛刺。
5. **元素/字母/单词三级切分**：`unit = median(短时长)`（点长），元素 `dur < 2*unit` 为点否则为划；间隔 `> 2.5*unit` 断字母、`> 6*unit` 断单词。查标准 A–Z 表。
6. 明文通常是一句提示语（"HELLO WHAT IS THE KEY IT IS ..."），**通读语义**，key 往往就是句中强调的那个词，直接包外层格式提交。

## 证据
- 实测：解码得 44.1 kHz 单声道 45 s 音频；时域 RMS `min/max≈0.56`、`<10%峰值帧占比=0`；2.5–3.5 kHz 频带 `max/median≈1782`；带通+希尔伯特+中值归一化后切出 54 个元素、51 个码组，与明文 29 字母量级吻合。

## 坑
- **不要在时域响/静上死磕**：这是最大的时间黑洞，反复用固定阈值切分会得到 149/246/853 个碎片，全部无意义。先算 `min/max` 比值，>0.3 就直接转频域。
- **别用 `mean` 做帧内聚合**：短元素（20–40 ms）在 mean 下会被稀释到噪声水平；用 `max`。
- **别用 `sosfilt` 用 `sosfiltfilt`**：前者有相位延迟，会让元素边界整体偏移，进而破坏点划时长比例。
- **mp3 有损压缩会糊掉瞬态**：优先用原始 mp3 解码一次，不要反复转码。
- **自动转写结果必须做语义自检**：若解出的是 90% 以上都是 E/T 的串（如 `MTTTTETEETTTTTTTETTT...`），说明严重过分割（每个元素被当成一个字母），此时不要硬凑，改人工看频谱图转写。
- 环境里可能没有 ffmpeg/sox/mpg123；macOS 上 `afconvert -f WAVE -d LEI16@44100 -c 1 in.mp3 out.wav` 可用。

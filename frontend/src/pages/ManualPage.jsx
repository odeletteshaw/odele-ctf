import { useState } from 'react'
import { Paper, Typography, TextField, MenuItem, Button } from '@mui/material'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import { manualSolve } from '../api.js'

export default function ManualPage() {
  const [direction, setDirection] = useState('web')
  const [urls, setUrls] = useState('')
  const [desc, setDesc] = useState('')
  const [turns, setTurns] = useState(100)
  const [prefix, setPrefix] = useState('')

  const start = async () => {
    const urlsList = urls.split('\n').map((s) => s.trim()).filter(Boolean)
    if (direction === 'web' && !urlsList.length) return alert('web 至少填一个 URL')
    const spec = {
      kind: 'custom', category: direction,
      urls: direction === 'web' ? urlsList : [],
      description: desc.trim(), flag_prefix: prefix.trim(),
      attachments: [], max_turns: parseInt(turns, 10) || 100,
    }
    const title = urlsList[0] ? urlsList[0].split('/')[2] : direction
    await manualSolve(spec, title)
    alert('已启动')
  }

  return (
    <Paper sx={{ p: 3, maxWidth: 640 }}>
      <Typography variant="h6" sx={{ mb: 0.5 }}>手动解题</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        将以角色团队执行：团队长拆解 → 信息收集员侦察 → 方向专家解题 → 报告收集员复盘。
      </Typography>
      <TextField select fullWidth label="方向" value={direction} onChange={(e) => setDirection(e.target.value)} sx={{ mb: 2 }}>
        {['web', 'crypto', 'forensics', 'cloud', 'blockchain', 'ics', 'iot', 'ir', 'pentest']
          .map((d) => <MenuItem key={d} value={d}>{d}</MenuItem>)}
      </TextField>
      <TextField fullWidth multiline minRows={2} label="目标 URL（web 必填，每行一个）" value={urls} onChange={(e) => setUrls(e.target.value)} sx={{ mb: 2 }} />
      <TextField fullWidth label="题目描述 / 提示" value={desc} onChange={(e) => setDesc(e.target.value)} sx={{ mb: 2 }} />
      <TextField fullWidth type="number" label="max turns" value={turns} onChange={(e) => setTurns(e.target.value)} sx={{ mb: 2 }} />
      <TextField fullWidth label="flag 前缀（留空 = 匹配任意 XXX{...}，如 CTF2 / DASCTF）"
        value={prefix} onChange={(e) => setPrefix(e.target.value)} sx={{ mb: 2 }} />
      <Button variant="contained" startIcon={<PlayArrowIcon />} onClick={start}>开始 ▶</Button>
    </Paper>
  )
}

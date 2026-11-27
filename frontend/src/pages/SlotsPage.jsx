import { useEffect, useState } from 'react'
import { Paper, Typography, TextField, Button, Stack, Chip } from '@mui/material'
import SaveIcon from '@mui/icons-material/Save'
import { getTokenSlots, saveTokenSlots } from '../api.js'

const DIRS = ['web', 'crypto', 'misc', 'forensics', 'pwn', 'reverse', 'ai',
  'cloud', 'blockchain', 'ics', 'iot', 'ir', 'pentest']

export default function SlotsPage() {
  const [slots, setSlots] = useState({})
  const [tokenCount, setTokenCount] = useState(0)

  const load = async () => {
    const r = await getTokenSlots()
    setSlots(r.slots || {})
    setTokenCount(r.token_count || 0)
  }
  useEffect(() => { load() }, [])

  const save = async () => {
    const r = await saveTokenSlots(slots)
    setSlots(r.slots || {})
    alert('Token 槽位已保存')
  }

  return (
    <Paper sx={{ p: 3, maxWidth: 720 }}>
      <Typography variant="h6" sx={{ mb: 1 }}>打题 Token 槽位</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        每个方向使用第几个 CTF2 agent token（0 起）。当前配置了 {tokenCount} 个 token；
        这只决定平台自动打题用哪个账号，和「团队」角色分工是两套概念。
      </Typography>
      <Stack spacing={1.5} sx={{ mb: 2 }}>
        {DIRS.map((d) => (
          <Stack key={d} direction="row" spacing={2} alignItems="center">
            <Chip size="small" label={d} color="primary" variant="outlined" sx={{ width: 100 }} />
            <TextField size="small" type="number" label="token 下标" value={slots[d] ?? 0}
              onChange={(e) => setSlots({ ...slots, [d]: parseInt(e.target.value || '0', 10) })}
              sx={{ width: 160 }} />
          </Stack>
        ))}
      </Stack>
      <Button variant="contained" startIcon={<SaveIcon />} onClick={save}>保存槽位</Button>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
        0 表示第一个 token，1 表示第二个，以此类推；超出 token 数量的下标会回退到 0。
      </Typography>
    </Paper>
  )
}

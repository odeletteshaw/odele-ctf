import { useEffect, useState } from 'react'
import { Paper, Typography, Button, List, ListItem, ListItemText, Chip, Stack } from '@mui/material'
import SaveIcon from '@mui/icons-material/Save'
import { getTeam, saveTeam } from '../api.js'

export default function TeamPage() {
  const [members, setMembers] = useState([])
  const [json, setJson] = useState('')

  const load = async () => {
    const t = await getTeam()
    setMembers(t.members || [])
    setJson(JSON.stringify(t, null, 2))
  }
  useEffect(() => { load() }, [])

  const save = async () => {
    try {
      const members = JSON.parse(json).members
      if (!Array.isArray(members)) throw new Error('members 必须是数组')
      await saveTeam(members)
      load()
      alert('团队已保存')
    } catch (e) { alert('JSON 解析失败: ' + e.message) }
  }

  return (
    <Paper sx={{ p: 3, maxWidth: 760 }}>
      <Typography variant="h6" sx={{ mb: 2 }}>团队（方向 → Agent 分工）</Typography>
      <List>
        {members.map((m, i) => (
          <ListItem key={i} divider>
            <ListItemText
              primary={<strong>{m.name || '(未命名)'}</strong>}
              secondary={
                <Stack direction="row" spacing={0.5} sx={{ mt: 0.5 }}>
                  <Chip size="small" label={`token ${m.token_index}`} />
                  {(m.directions || []).map((d) => <Chip key={d} size="small" label={d} color="primary" variant="outlined" />)}
                </Stack>
              }
            />
          </ListItem>
        ))}
      </List>
      <Typography variant="subtitle2" sx={{ mt: 3, mb: 1 }}>编辑（JSON）</Typography>
      <textarea value={json} onChange={(e) => setJson(e.target.value)} rows={10}
        style={{ width: '100%', background: '#141a24', color: '#d6dae3', border: '1px solid #243043', borderRadius: 6, padding: 10, font: '12px Menlo,monospace' }} />
      <Button variant="contained" startIcon={<SaveIcon />} onClick={save} sx={{ mt: 1 }}>保存团队</Button>
    </Paper>
  )
}

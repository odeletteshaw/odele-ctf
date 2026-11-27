import { useEffect, useState } from 'react'
import { Paper, Typography, Button, Chip, Stack, Box, Alert, Tooltip } from '@mui/material'
import SaveIcon from '@mui/icons-material/Save'
import { getTeam, getTeamSkills, saveTeam } from '../api.js'

const ROLE_LABEL = {
  lead: '团队长',
  recon: '信息收集员',
  expert: '攻防专家',
  reporter: '报告收集员',
}
const ROLE_COLOR = {
  lead: 'warning',
  recon: 'info',
  expert: 'primary',
  reporter: 'success',
}

export default function TeamPage() {
  const [members, setMembers] = useState([])
  const [skills, setSkills] = useState({})
  const [json, setJson] = useState('')

  const load = async () => {
    const [t, s] = await Promise.all([getTeam(), getTeamSkills()])
    setMembers(t.members || [])
    setJson(JSON.stringify(t, null, 2))
    const map = {}
    for (const m of s.members || []) map[`${m.role}:${m.name}`] = m
    setSkills(map)
  }
  useEffect(() => { load() }, [])

  const save = async () => {
    try {
      const members = JSON.parse(json).members
      if (!Array.isArray(members)) throw new Error('members 必须是数组')
      await saveTeam(members)
      load()
      alert('团队已保存')
    } catch (e) { alert('保存失败: ' + e.message) }
  }

  const grouped = (role) => members.filter((m) => m.role === role)

  return (
    <Box>
      <Paper sx={{ p: 3, maxWidth: 900, mb: 2 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>角色团队</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          团队按角色协作：团队长拆解与分派 → 信息收集员侦察 → 对应方向的攻防专家解题 → 报告收集员写复盘。
          这里配置的是角色，不是打题 token；token 分配请看「Token 槽位」页。
        </Typography>
        {['lead', 'recon', 'expert', 'reporter'].map((role) => (
          <Box key={role} sx={{ mt: 2 }}>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>{ROLE_LABEL[role]}</Typography>
            <Stack spacing={1}>
              {grouped(role).map((m, i) => (
                <Box key={i} sx={{ p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                  <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
                    <Chip size="small" label={ROLE_LABEL[m.role] || m.role} color={ROLE_COLOR[m.role] || 'default'} />
                    <Typography variant="subtitle2">{m.name || '(未命名)'}</Typography>
                    {(m.directions || []).map((d) => (
                      <Chip key={d} size="small" label={d} variant="outlined" />
                    ))}
                    <Tooltip title={(skills[`${m.role}:${m.name}`]?.skills || []).join('、') || '暂无技能资料'}>
                      <Chip size="small" color="default" variant="outlined"
                        label={`技能包 ${skills[`${m.role}:${m.name}`]?.count ?? 0} 篇`} />
                    </Tooltip>
                  </Stack>
                  {m.description && (
                    <Typography variant="body2" color="text.secondary">{m.description}</Typography>
                  )}
                </Box>
              ))}
              {!grouped(role).length && (
                <Typography variant="body2" color="text.secondary">未配置</Typography>
              )}
            </Stack>
          </Box>
        ))}
      </Paper>

      <Paper sx={{ p: 3, maxWidth: 900 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>编辑（JSON）</Typography>
        <Alert severity="info" sx={{ mb: 2 }}>
          role 取值：lead / recon / expert / reporter；专家的 directions 决定他负责哪些方向。
        </Alert>
        <textarea value={json} onChange={(e) => setJson(e.target.value)} rows={16}
          style={{ width: '100%', background: '#141a24', color: '#d6dae3', border: '1px solid #243043', borderRadius: 6, padding: 10, font: '12px Menlo,monospace' }} />
        <Button variant="contained" startIcon={<SaveIcon />} onClick={save} sx={{ mt: 1 }}>保存团队</Button>
      </Paper>
    </Box>
  )
}

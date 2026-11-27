import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Paper, Typography, Button, Chip, Stack, Box, Alert, Tooltip, Dialog,
  DialogTitle, DialogContent, DialogActions, TextField, Checkbox, FormControlLabel,
  Accordion, AccordionSummary, AccordionDetails, IconButton, Divider,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import SaveIcon from '@mui/icons-material/Save'
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import {
  getTeam, getTeamSkills, getTeamPacks, saveTeam, createTeamRole, deleteTeamRole,
} from '../api.js'

const ROLE_ORDER = ['lead', 'recon', 'expert', 'reporter', 'custom']
const ROLE_META = {
  lead: { label: '团队长', color: 'warning' },
  recon: { label: '信息收集员', color: 'info' },
  expert: { label: '攻防专家', color: 'primary' },
  reporter: { label: '报告收集员', color: 'success' },
  custom: { label: '自定义角色', color: 'secondary' },
}

function SkillPicker({ packs, value, onChange }) {
  const known = new Set(packs.map((p) => p.id))
  const extras = value.filter((pack) => !known.has(pack))
  return (
    <Box sx={{ maxHeight: 220, overflow: 'auto', border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1 }}>
      {packs.map((pack) => (
        <FormControlLabel key={pack.id} sx={{ display: 'flex', mr: 0 }}
          control={<Checkbox size="small" checked={value.includes(pack.id)}
            onChange={(e) => onChange(e.target.checked
              ? [...value, pack.id] : value.filter((x) => x !== pack.id))} />}
          label={<Typography variant="body2">{pack.label} · {pack.id}（{pack.count} 篇）</Typography>} />
      ))}
      {extras.map((pack) => (
        <FormControlLabel key={pack} sx={{ display: 'flex', mr: 0 }}
          control={<Checkbox size="small" checked
            onChange={() => onChange(value.filter((x) => x !== pack))} />}
          label={<Typography variant="body2">{pack}</Typography>} />
      ))}
      {!packs.length && <Typography variant="body2" color="text.secondary">暂无可用技能包</Typography>}
    </Box>
  )
}

export default function TeamPage() {
  const [members, setMembers] = useState([])
  const [skills, setSkills] = useState({})
  const [packs, setPacks] = useState([])
  const [json, setJson] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [draft, setDraft] = useState({ name: '', description: '', skills: [] })
  const [editing, setEditing] = useState(null)
  const navigate = useNavigate()

  const load = async () => {
    const [t, s, p] = await Promise.all([getTeam(), getTeamSkills(), getTeamPacks()])
    const list = t.members || []
    setMembers(list)
    setJson(JSON.stringify({ members: list }, null, 2))
    const map = {}
    for (const m of s.members || []) map[m.id || `${m.role}:${m.name}`] = m
    setSkills(map)
    setPacks(p.packs || [])
  }
  useEffect(() => { load() }, [])

  const byRole = useMemo(() => {
    const groups = {}
    for (const role of ROLE_ORDER) groups[role] = []
    for (const m of members) (groups[m.role] ||= []).push(m)
    return groups
  }, [members])

  const saveJson = async () => {
    try {
      const parsed = JSON.parse(json).members
      if (!Array.isArray(parsed)) throw new Error('members 必须是数组')
      await saveTeam(parsed)
      load()
      alert('团队已保存')
    } catch (e) { alert('保存失败: ' + e.message) }
  }

  const submitCreate = async () => {
    if (!draft.name.trim()) { alert('请填写角色名'); return }
    try {
      await createTeamRole({ name: draft.name.trim(), description: draft.description.trim(), skills: draft.skills })
      setCreateOpen(false)
      setDraft({ name: '', description: '', skills: [] })
      load()
    } catch (e) { alert('创建失败: ' + e.message) }
  }

  const submitEdit = async () => {
    if (!editing) return
    const updated = members.map((m) => m.id === editing.id ? {
      ...m,
      name: editing.name.trim() || m.name,
      description: editing.description,
      directions: editing.role === 'expert'
        ? editing.directions.split(',').map((d) => d.trim()).filter(Boolean)
        : m.directions,
      skills: editing.skills,
    } : m)
    try {
      await saveTeam(updated)
      setEditing(null)
      load()
    } catch (e) { alert('保存失败: ' + e.message) }
  }

  const removeRole = async (member) => {
    if (!confirm(`删除自定义角色「${member.name}」？（技能目录会保留）`)) return
    try {
      await deleteTeamRole(member.id)
      load()
    } catch (e) { alert('删除失败: ' + e.message) }
  }

  return (
    <Box sx={{ width: '100%', minHeight: 'calc(100vh - 140px)', display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Paper sx={{ p: 2.5 }}>
        <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
          <Typography variant="h6" sx={{ mr: 1 }}>角色团队</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ flex: 1, minWidth: 260 }}>
            团队长拆解分派 → 侦察 → 按需调用自定义角色 → 对应方向专家解题 → 报告员复盘。
            每个角色可勾选技能包；MCP 字段本轮预留，暂未接入。
          </Typography>
          <Button variant="outlined" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
            新建角色
          </Button>
          <Button variant="outlined" onClick={() => navigate('/skills')}>浏览技能包</Button>
        </Stack>
      </Paper>

      <Box sx={{
        display: 'grid', gap: 2, flex: 1, alignItems: 'stretch',
        gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)', xl: 'repeat(3, 1fr)' },
      }}>
        {ROLE_ORDER.map((role) => (
          <Paper key={role} sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
              <Chip size="small" color={ROLE_META[role].color} label={ROLE_META[role].label} />
              <Typography variant="body2" color="text.secondary">{byRole[role]?.length || 0} 个</Typography>
            </Stack>
            <Stack spacing={1.5} sx={{ flex: 1, overflow: 'auto', pr: 0.5 }}>
              {(byRole[role] || []).map((m) => {
                const info = skills[m.id] || {}
                return (
                  <Box key={m.id} sx={{ p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 1.5 }}>
                    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                      <Typography variant="subtitle2">{m.name || m.id}</Typography>
                      {(m.directions || []).map((d) => <Chip key={d} size="small" label={d} variant="outlined" />)}
                      <Tooltip title={(info.skill_names || []).join('、') || '暂无技能资料'}>
                        <Chip size="small" variant="outlined" clickable onClick={() => navigate('/skills')}
                          label={`技能包 ${info.count ?? 0} 篇`} />
                      </Tooltip>
                      <Box sx={{ flex: 1 }} />
                      <Tooltip title="编辑">
                        <IconButton size="small" onClick={() => setEditing({
                          ...m,
                          directions: (m.directions || []).join(', '),
                          skills: [...(m.skills || [])],
                        })}><EditIcon fontSize="small" /></IconButton>
                      </Tooltip>
                      {m.role === 'custom' && (
                        <Tooltip title="删除角色">
                          <IconButton size="small" color="error" onClick={() => removeRole(m)}>
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}
                    </Stack>
                    {m.description && (
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
                        {m.description}
                      </Typography>
                    )}
                    <Stack direction="row" spacing={0.5} sx={{ mt: 0.75 }} flexWrap="wrap" useFlexGap>
                      {(m.skills || []).map((pack) => (
                        <Chip key={pack} size="small" label={pack} sx={{ fontFamily: 'Menlo,monospace', fontSize: 11 }} />
                      ))}
                      {(m.mcp || []).length > 0 && <Chip size="small" color="default" label="MCP" />}
                    </Stack>
                  </Box>
                )
              })}
              {!(byRole[role] || []).length && (
                <Typography variant="body2" color="text.secondary">未配置</Typography>
              )}
            </Stack>
          </Paper>
        ))}
      </Box>

      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="body2">高级：JSON 批量编辑</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Alert severity="info" sx={{ mb: 1.5 }}>
            role 取值 lead / recon / expert / reporter / custom；id 用于团队长调用自定义角色；skills 为技能包 id。
          </Alert>
          <textarea value={json} onChange={(e) => setJson(e.target.value)} rows={12}
            style={{ width: '100%', background: '#141a24', color: '#d6dae3', border: '1px solid #243043', borderRadius: 6, padding: 10, font: '12px Menlo,monospace' }} />
          <Button variant="contained" startIcon={<SaveIcon />} onClick={saveJson} sx={{ mt: 1 }}>保存 JSON</Button>
        </AccordionDetails>
      </Accordion>

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>新建自定义角色</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="角色名" fullWidth value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
            <TextField label="职责定义" fullWidth multiline minRows={2} value={draft.description}
              onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
            <Typography variant="subtitle2">技能包（默认会新建以角色命名的包）</Typography>
            <SkillPicker packs={packs} value={draft.skills}
              onChange={(skills) => setDraft({ ...draft, skills })} />
            <Typography variant="body2" color="text.secondary">
              团队长会在计划阶段按需调用该角色；MCP 字段本轮预留。
            </Typography>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>取消</Button>
          <Button variant="contained" onClick={submitCreate}>创建</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={!!editing} onClose={() => setEditing(null)} fullWidth maxWidth="sm">
        <DialogTitle>编辑角色</DialogTitle>
        <DialogContent>
          {editing && (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <TextField label="角色名" fullWidth value={editing.name}
                onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
              <TextField label="职责定义" fullWidth multiline minRows={2} value={editing.description}
                onChange={(e) => setEditing({ ...editing, description: e.target.value })} />
              {editing.role === 'expert' && (
                <TextField label="负责方向（逗号分隔）" fullWidth value={editing.directions}
                  onChange={(e) => setEditing({ ...editing, directions: e.target.value })} />
              )}
              <Typography variant="subtitle2">技能包</Typography>
              <SkillPicker packs={packs} value={editing.skills || []}
                onChange={(skills) => setEditing({ ...editing, skills })} />
              <Divider />
              <Typography variant="body2" color="text.secondary">
                MCP 服务器：本轮暂未接入（字段已在数据模型中预留）。
              </Typography>
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditing(null)}>取消</Button>
          <Button variant="contained" onClick={submitEdit}>保存</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

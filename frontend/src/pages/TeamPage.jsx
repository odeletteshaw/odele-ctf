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

const KIND_META = {
  lead: { label: '团队长', color: 'warning' },
  recon: { label: '信息收集', color: 'info' },
  expert: { label: '方向专家', color: 'primary' },
  reporter: { label: '报告收集', color: 'success' },
  custom: { label: '自定义', color: 'secondary' },
  worker: { label: '通用', color: 'default' },
}

function SkillPicker({ library, tags, value, onChange }) {
  const [q, setQ] = useState('')
  const known = new Set([...library.map((s) => s.id), ...tags.map((t) => `tag:${t}`)])
  const extras = value.filter((v) => !known.has(v))
  const toggle = (selector) => onChange(value.includes(selector)
    ? value.filter((x) => x !== selector) : [...value, selector])
  const needle = q.trim().toLowerCase()
  const filtered = needle
    ? library.filter((s) => `${s.name} ${s.description} ${s.tags.join(' ')}`.toLowerCase().includes(needle))
    : library
  return (
    <Box>
      <Typography variant="caption" color="text.secondary">按标签整组绑定（tag:）</Typography>
      <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mb: 1, mt: 0.5 }}>
        {tags.map((tag) => (
          <Chip key={tag} size="small" label={`tag:${tag}`} clickable
            color={value.includes(`tag:${tag}`) ? 'primary' : 'default'}
            variant={value.includes(`tag:${tag}`) ? 'filled' : 'outlined'}
            onClick={() => toggle(`tag:${tag}`)} />
        ))}
      </Stack>
      <TextField size="small" fullWidth placeholder="搜索技能…" value={q}
        onChange={(e) => setQ(e.target.value)} sx={{ mb: 1 }} />
      <Box sx={{ maxHeight: 260, overflow: 'auto', border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1 }}>
        {filtered.map((skill) => (
          <FormControlLabel key={skill.id} sx={{ display: 'flex', mr: 0 }}
            control={<Checkbox size="small" checked={value.includes(skill.id)}
              onChange={() => toggle(skill.id)} />}
            label={<Typography variant="body2" noWrap>{skill.name} · {skill.id}
              <Typography component="span" variant="caption" color="text.secondary">
                {skill.tags.length ? `（${skill.tags.join('/')}）` : ''}
              </Typography>
            </Typography>} />
        ))}
        {extras.map((selector) => (
          <FormControlLabel key={selector} sx={{ display: 'flex', mr: 0 }}
            control={<Checkbox size="small" checked onChange={() => toggle(selector)} />}
            label={<Typography variant="body2">{selector}</Typography>} />
        ))}
        {!filtered.length && <Typography variant="body2" color="text.secondary">没有匹配技能</Typography>}
      </Box>
    </Box>
  )
}

export default function TeamPage() {
  const [members, setMembers] = useState([])
  const [skills, setSkills] = useState({})
  const [library, setLibrary] = useState([])
  const [tags, setTags] = useState([])
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
    for (const m of s.members || []) map[m.id] = m
    setSkills(map)
    setLibrary(p.packs || [])
    setTags(p.tags || [])
  }
  useEffect(() => { load() }, [])

  const lead = useMemo(() => members.find((m) => m.role === 'lead'), [members])
  const workers = useMemo(() => members.filter((m) => m.role !== 'lead'), [members])

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
      directions: editing.kind === 'expert'
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
    if (!confirm(`删除角色「${member.name}」？`)) return
    try {
      await deleteTeamRole(member.id)
      load()
    } catch (e) { alert('删除失败: ' + e.message) }
  }

  const card = (m, isLead = false) => {
    const info = skills[m.id] || {}
    const meta = KIND_META[m.kind] || KIND_META.worker
    return (
      <Box key={m.id} sx={{
        p: 2, border: '1px solid', borderColor: isLead ? 'warning.main' : 'divider',
        borderRadius: 1.5, height: '100%', display: 'flex', flexDirection: 'column',
      }}>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
          <Chip size="small" color={meta.color} label={meta.label} />
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>{m.name}</Typography>
          {(m.directions || []).map((d) => <Chip key={d} size="small" label={d} variant="outlined" />)}
          <Box sx={{ flex: 1 }} />
          <Tooltip title={(info.skill_names || []).join('、') || '暂无技能'}>
            <Chip size="small" variant="outlined" clickable onClick={() => navigate('/skills')}
              label={`技能 ${info.count ?? 0} 条`} />
          </Tooltip>
          <Tooltip title="编辑">
            <IconButton size="small" onClick={() => setEditing({
              ...m, directions: (m.directions || []).join(', '), skills: [...(m.skills || [])],
            })}><EditIcon fontSize="small" /></IconButton>
          </Tooltip>
          {!isLead && m.kind === 'custom' && (
            <Tooltip title="删除">
              <IconButton size="small" color="error" onClick={() => removeRole(m)}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Stack>
        {m.description && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1, flex: 1 }}>
            {m.description}
          </Typography>
        )}
        <Stack direction="row" spacing={0.5} sx={{ mt: 1 }} flexWrap="wrap" useFlexGap>
          {(m.skills || []).map((selector) => (
            <Chip key={selector} size="small" label={selector}
              sx={{ fontFamily: 'Menlo,monospace', fontSize: 11 }} />
          ))}
          {!(m.skills || []).length && (
            <Typography variant="caption" color="text.secondary">未绑定技能</Typography>
          )}
        </Stack>
      </Box>
    )
  }

  return (
    <Box sx={{ width: '100%', minHeight: 'calc(100vh - 140px)', display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Paper sx={{ p: 2.5 }}>
        <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
          <Typography variant="h6" sx={{ mr: 1 }}>团队</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ flex: 1, minWidth: 300 }}>
            团队长是唯一入口，接收命令后输出 DAG；其余角色扁平，可被任意调度。需要拍板的节点会暂停并请求你审批。
            技能来自统一扁平技能库。
          </Typography>
          <Button variant="outlined" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>新建角色</Button>
          <Button variant="outlined" onClick={() => navigate('/skills')}>技能库</Button>
        </Stack>
      </Paper>

      {lead && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>入口</Typography>
          {card(lead, true)}
        </Paper>
      )}

      <Paper sx={{ p: 2, flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
          <Typography variant="subtitle2">扁平角色池</Typography>
          <Typography variant="body2" color="text.secondary">{workers.length} 个</Typography>
        </Stack>
        <Box sx={{
          display: 'grid', gap: 1.5, overflow: 'auto', alignContent: 'start',
          gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)', xl: 'repeat(3, 1fr)' },
        }}>
          {workers.map((m) => card(m))}
        </Box>
      </Paper>

      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="body2">高级：JSON 批量编辑</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Alert severity="info" sx={{ mb: 1.5 }}>
            role 只有 lead / worker；kind 用于展示（recon/expert/reporter/custom）；
            skills 为技能 id 或 tag:xxx。
          </Alert>
          <textarea value={json} onChange={(e) => setJson(e.target.value)} rows={12}
            style={{ width: '100%', background: '#141a24', color: '#d6dae3', border: '1px solid #243043', borderRadius: 6, padding: 10, font: '12px Menlo,monospace' }} />
          <Button variant="contained" startIcon={<SaveIcon />} onClick={saveJson} sx={{ mt: 1 }}>保存 JSON</Button>
        </AccordionDetails>
      </Accordion>

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>新建角色</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="角色名" fullWidth value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
            <TextField label="职责定义" fullWidth multiline minRows={2} value={draft.description}
              onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
            <Typography variant="subtitle2">绑定技能（id 或 tag 整组）</Typography>
            <SkillPicker library={library} tags={tags} value={draft.skills}
              onChange={(skills) => setDraft({ ...draft, skills })} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>取消</Button>
          <Button variant="contained" onClick={submitCreate}>创建</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={!!editing} onClose={() => setEditing(null)} fullWidth maxWidth="md">
        <DialogTitle>编辑角色</DialogTitle>
        <DialogContent>
          {editing && (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <TextField label="角色名" fullWidth value={editing.name}
                onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
              <TextField label="职责定义" fullWidth multiline minRows={2} value={editing.description}
                onChange={(e) => setEditing({ ...editing, description: e.target.value })} />
              {editing.kind === 'expert' && (
                <TextField label="负责方向（逗号分隔）" fullWidth value={editing.directions}
                  onChange={(e) => setEditing({ ...editing, directions: e.target.value })} />
              )}
              <Typography variant="subtitle2">绑定技能</Typography>
              <SkillPicker library={library} tags={tags} value={editing.skills || []}
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

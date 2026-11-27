import { useEffect, useMemo, useState } from 'react'
import {
  Paper, Typography, Button, Chip, Stack, Box, Alert, Tooltip, Dialog,
  DialogTitle, DialogContent, DialogActions, TextField, Checkbox, FormControlLabel,
  IconButton, Divider, List, ListItemButton, ListItemText, InputAdornment,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import SaveIcon from '@mui/icons-material/Save'
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'
import SearchIcon from '@mui/icons-material/Search'
import DataObjectIcon from '@mui/icons-material/DataObject'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  getTeam, getTeamSkills, getTeamPacks, saveTeam, createTeamRole, deleteTeamRole,
  getSkillContent,
} from '../api.js'

const KIND_META = {
  lead: { label: '团队长', color: 'warning' },
  recon: { label: '信息收集', color: 'info' },
  expert: { label: '方向专家', color: 'primary' },
  reporter: { label: '报告收集', color: 'success' },
  custom: { label: '自定义', color: 'secondary' },
  worker: { label: '通用', color: 'default' },
}
const KIND_LABEL = { method: '方法', reference: '资料' }

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
      <Typography variant="caption" color="text.secondary">按标签整组绑定</Typography>
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
  const [skillsById, setSkillsById] = useState({})
  const [library, setLibrary] = useState([])
  const [tags, setTags] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [selectedEntry, setSelectedEntry] = useState(0)
  const [content, setContent] = useState(null)
  const [loading, setLoading] = useState(false)
  const [skillQuery, setSkillQuery] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [draft, setDraft] = useState({ name: '', description: '', skills: [] })
  const [editing, setEditing] = useState(null)
  const [jsonOpen, setJsonOpen] = useState(false)
  const [json, setJson] = useState('')

  const load = async () => {
    const [t, s, p] = await Promise.all([getTeam(), getTeamSkills(), getTeamPacks()])
    const list = t.members || []
    setMembers(list)
    setJson(JSON.stringify({ members: list }, null, 2))
    const byId = {}
    for (const m of s.members || []) byId[m.id] = m
    setSkillsById(byId)
    setLibrary(p.packs || [])
    setTags(p.tags || [])
    setSelectedId((current) => (
      current && list.some((m) => m.id === current)
        ? current
        : (list.find((m) => m.role === 'lead')?.id || list[0]?.id || null)
    ))
  }
  useEffect(() => { load() }, [])

  const member = useMemo(() => members.find((m) => m.id === selectedId) || null, [members, selectedId])
  const info = member ? skillsById[member.id] : null
  const entries = useMemo(() => {
    const list = info?.entries || []
    const needle = skillQuery.trim().toLowerCase()
    if (!needle) return list
    return list.filter((e) => `${e.name} ${e.description}`.toLowerCase().includes(needle))
  }, [info, skillQuery])

  useEffect(() => {
    setSelectedEntry(0)
    setContent(null)
    setSkillQuery('')
  }, [selectedId])

  useEffect(() => {
    if (!info?.entries?.length || info.index == null) { setContent(null); return }
    const target = info.entries[selectedEntry] || info.entries[0]
    let alive = true
    setLoading(true)
    getSkillContent(info.index, target.index)
      .then((c) => { if (alive) setContent(c) })
      .catch(() => { if (alive) setContent(null) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [skillsById, selectedId, selectedEntry])

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

  const removeRole = async (target) => {
    if (!confirm(`删除角色「${target.name}」？`)) return
    try {
      await deleteTeamRole(target.id)
      load()
    } catch (e) { alert('删除失败: ' + e.message) }
  }

  const saveJson = async () => {
    try {
      const parsed = JSON.parse(json).members
      if (!Array.isArray(parsed)) throw new Error('members 必须是数组')
      await saveTeam(parsed)
      setJsonOpen(false)
      load()
    } catch (e) { alert('保存失败: ' + e.message) }
  }

  const meta = member ? (KIND_META[member.kind] || KIND_META.worker) : KIND_META.worker
  const lead = members.find((m) => m.role === 'lead')

  return (
    <Box sx={{ display: 'flex', gap: 1.5, height: 'calc(100vh - 112px)', minHeight: 560 }}>
      {/* members */}
      <Paper sx={{ width: 250, flexShrink: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <Box sx={{ p: 1.5, pb: 0.5 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>团队</Typography>
          <Typography variant="caption" color="text.secondary">
            {members.length} 个角色 · 团队长唯一入口
          </Typography>
        </Box>
        <Divider />
        <List dense sx={{ flex: 1, overflow: 'auto', px: 0.5, py: 0.5 }}>
          {members.map((m) => {
            const mInfo = skillsById[m.id]
            const mMeta = KIND_META[m.kind] || KIND_META.worker
            return (
              <ListItemButton key={m.id} selected={m.id === selectedId}
                onClick={() => setSelectedId(m.id)} sx={{ borderRadius: 1, mb: 0.25 }}>
                <ListItemText
                  primary={<Stack direction="row" spacing={0.5} alignItems="center">
                    <Typography variant="body2" sx={{ fontWeight: m.role === 'lead' ? 700 : 500 }}>
                      {m.name}
                    </Typography>
                    {m.role === 'lead' && <Chip size="small" color="warning" label="入口" />}
                  </Stack>}
                  secondary={`${mMeta.label} · 技能 ${mInfo?.count ?? 0}`}
                />
              </ListItemButton>
            )
          })}
        </List>
        <Divider />
        <Stack direction="row" spacing={0.5} sx={{ p: 1 }}>
          <Button size="small" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>新建</Button>
          <Button size="small" startIcon={<DataObjectIcon />} onClick={() => setJsonOpen(true)}>JSON</Button>
        </Stack>
      </Paper>

      {/* selected member skills */}
      <Paper sx={{ width: 340, flexShrink: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {member ? (
          <>
            <Box sx={{ p: 1.5, pb: 0.75 }}>
              <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" useFlexGap>
                <Chip size="small" color={meta.color} label={meta.label} />
                <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>{member.name}</Typography>
                {(member.directions || []).map((d) => <Chip key={d} size="small" label={d} variant="outlined" />)}
                <Box sx={{ flex: 1 }} />
                <Tooltip title="编辑角色">
                  <IconButton size="small" onClick={() => setEditing({
                    ...member, directions: (member.directions || []).join(', '),
                    skills: [...(member.skills || [])],
                  })}><EditIcon fontSize="small" /></IconButton>
                </Tooltip>
                {member.kind === 'custom' && member.role !== 'lead' && (
                  <Tooltip title="删除角色">
                    <IconButton size="small" color="error" onClick={() => removeRole(member)}>
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                )}
              </Stack>
              {member.description && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
                  {member.description}
                </Typography>
              )}
              <Stack direction="row" spacing={0.5} sx={{ mt: 1 }} flexWrap="wrap" useFlexGap>
                {(member.skills || []).map((selector) => (
                  <Chip key={selector} size="small" label={selector}
                    sx={{ fontFamily: 'Menlo,monospace', fontSize: 11 }} />
                ))}
                {!(member.skills || []).length && (
                  <Typography variant="caption" color="text.secondary">未绑定技能</Typography>
                )}
              </Stack>
              <TextField size="small" fullWidth placeholder="搜索该角色的技能…" value={skillQuery}
                onChange={(e) => setSkillQuery(e.target.value)} sx={{ mt: 1.5 }}
                InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> }} />
              <Typography variant="caption" color="text.secondary">
                {entries.length} 条技能
              </Typography>
            </Box>
            <Divider />
            <List dense sx={{ flex: 1, overflow: 'auto', px: 0.5, py: 0.5 }}>
              {entries.map((entry) => (
                <ListItemButton key={entry.index} selected={entry.index === selectedEntry}
                  onClick={() => setSelectedEntry(entry.index)} sx={{ borderRadius: 1, mb: 0.25 }}>
                  <ListItemText
                    primary={<Stack direction="row" spacing={0.5} alignItems="center">
                      <Typography variant="body2" noWrap>{entry.name}</Typography>
                      <Chip size="small" label={KIND_LABEL[entry.kind] || entry.kind} variant="outlined" />
                    </Stack>}
                    secondary={entry.description || entry.file}
                    secondaryTypographyProps={{ noWrap: true }}
                  />
                </ListItemButton>
              ))}
              {!entries.length && (
                <Typography variant="body2" color="text.secondary" sx={{ p: 1 }}>
                  {info?.count ? '没有匹配技能' : '未绑定技能，点编辑绑定'}
                </Typography>
              )}
            </List>
          </>
        ) : (
          <Box sx={{ p: 2 }}><Typography color="text.secondary">选择左侧角色</Typography></Box>
        )}
      </Paper>

      {/* content */}
      <Paper sx={{ flex: 1, minWidth: 360, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {content ? (
          <>
            <Box sx={{ px: 3, pt: 2, pb: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
              <Typography variant="h6">{content.name}</Typography>
              <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mt: 0.5 }} flexWrap="wrap" useFlexGap>
                <Chip size="small" label={KIND_LABEL[content.kind] || content.kind} variant="outlined" />
                <Typography variant="caption" color="text.secondary"
                  sx={{ fontFamily: 'Menlo,monospace' }}>{content.source}</Typography>
              </Stack>
            </Box>
            <Box sx={{
              flex: 1, overflow: 'auto', px: 3, py: 2, fontSize: 14, lineHeight: 1.75,
              wordBreak: 'break-word',
              '& h1': { fontSize: 22, mt: 2, mb: 1 },
              '& h2': { fontSize: 18, mt: 2, mb: 1 },
              '& h3': { fontSize: 16, mt: 1.5, mb: 0.75 },
              '& pre': { bgcolor: '#0b0f15', p: 1.5, borderRadius: 1, overflow: 'auto' },
              '& code': { fontFamily: 'Menlo,monospace' },
              '& blockquote': { borderLeft: '3px solid', borderColor: 'primary.main',
                                ml: 0, pl: 1.5, color: 'text.secondary' },
              '& table': { borderCollapse: 'collapse', width: '100%', my: 1 },
              '& th, & td': { border: '1px solid', borderColor: 'divider', px: 1, py: 0.5 },
            }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content.content}</ReactMarkdown>
            </Box>
          </>
        ) : (
          <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Typography color="text.secondary">
              {loading ? '加载中…' : (lead ? '选择一个角色的技能查看内容' : '团队为空')}
            </Typography>
          </Box>
        )}
      </Paper>

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>新建角色</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="角色名" fullWidth value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
            <TextField label="职责定义" fullWidth multiline minRows={2} value={draft.description}
              onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
            <Typography variant="subtitle2">绑定技能</Typography>
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
              <Alert severity="info">MCP 服务器本轮暂未接入（字段已在数据模型中预留）。</Alert>
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditing(null)}>取消</Button>
          <Button variant="contained" onClick={submitEdit}>保存</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={jsonOpen} onClose={() => setJsonOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>团队 JSON</DialogTitle>
        <DialogContent>
          <Alert severity="info" sx={{ mb: 1.5 }}>
            role 只有 lead / worker；kind 用于展示；skills 为技能 id 或 tag:xxx。
          </Alert>
          <textarea value={json} onChange={(e) => setJson(e.target.value)} rows={18}
            style={{ width: '100%', background: '#141a24', color: '#d6dae3', border: '1px solid #243043', borderRadius: 6, padding: 10, font: '12px Menlo,monospace' }} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setJsonOpen(false)}>取消</Button>
          <Button variant="contained" startIcon={<SaveIcon />} onClick={saveJson}>保存</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

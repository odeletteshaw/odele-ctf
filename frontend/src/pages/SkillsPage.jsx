import { useEffect, useMemo, useState } from 'react'
import {
  Paper, Typography, List, ListItemButton, ListItemText, TextField, Box, Divider,
  Chip, Stack, InputAdornment,
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getTeamSkills, getSkillContent } from '../api.js'

const KIND_LABEL = { skill: '角色方法', reference: '参考资料' }
const KIND_COLOR = { skill: 'primary', reference: 'default' }
const ROLE_LABEL = {
  lead: '团队长', recon: '信息收集员', expert: '专家', reporter: '报告收集员', custom: '自定义',
}

export default function SkillsPage() {
  const [members, setMembers] = useState([])
  const [memberIndex, setMemberIndex] = useState(0)
  const [entryIndex, setEntryIndex] = useState(0)
  const [content, setContent] = useState(null)
  const [loading, setLoading] = useState(false)
  const [q, setQ] = useState('')

  useEffect(() => { getTeamSkills().then((r) => setMembers(r.members || [])) }, [])

  const member = members[memberIndex]
  const entries = useMemo(() => {
    const list = member?.entries || []
    const needle = q.trim().toLowerCase()
    if (!needle) return list
    return list.filter((e) => `${e.name} ${e.description}`.toLowerCase().includes(needle))
  }, [member, q])

  useEffect(() => {
    if (!member?.entries?.length) { setContent(null); return }
    const target = member.entries[entryIndex] || member.entries[0]
    let alive = true
    setLoading(true)
    getSkillContent(memberIndex, target.index)
      .then((c) => { if (alive) setContent(c) })
      .catch(() => { if (alive) setContent(null) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [members, memberIndex, entryIndex])

  const selectMember = (index) => {
    setMemberIndex(index)
    setEntryIndex(0)
    setContent(null)
    setQ('')
  }

  return (
    <Box sx={{
      display: 'flex', gap: 2, alignItems: 'stretch',
      height: 'calc(100vh - 140px)', minHeight: 540,
    }}>
      <Paper sx={{ width: 240, flexShrink: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <Box sx={{ p: 1.5, pb: 0.5 }}>
          <Typography variant="subtitle2">角色</Typography>
          <Typography variant="caption" color="text.secondary">{members.length} 个角色</Typography>
        </Box>
        <List dense sx={{ flex: 1, overflow: 'auto', px: 0.5 }}>
          {members.map((m, i) => (
            <ListItemButton key={m.id || `${m.role}:${m.name}`} selected={i === memberIndex}
              onClick={() => selectMember(i)} sx={{ borderRadius: 1, mb: 0.25 }}>
              <ListItemText
                primary={m.name || m.role}
                secondary={`${ROLE_LABEL[m.role] || m.role} · ${m.count} 篇`}
              />
            </ListItemButton>
          ))}
        </List>
      </Paper>

      <Paper sx={{ width: 360, flexShrink: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <Box sx={{ p: 1.5, pb: 0.75 }}>
          <TextField size="small" fullWidth placeholder="搜索技能 / 关键词…" value={q}
            onChange={(e) => setQ(e.target.value)}
            InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> }} />
          <Stack direction="row" spacing={1} sx={{ mt: 1 }} alignItems="center">
            <Chip size="small" label={member?.name || '—'} />
            <Chip size="small" variant="outlined" label={`${entries.length} 项`} />
            {member?.skills?.length ? (
              <Typography variant="caption" color="text.secondary" noWrap>
                {member.skills.join('、')}
              </Typography>
            ) : null}
          </Stack>
        </Box>
        <Divider />
        <List dense sx={{ flex: 1, overflow: 'auto', px: 0.5, py: 0.5 }}>
          {entries.map((e) => (
            <ListItemButton key={e.index} selected={e.index === entryIndex}
              onClick={() => setEntryIndex(e.index)} sx={{ borderRadius: 1, mb: 0.25 }}>
              <ListItemText
                primary={<Stack direction="row" spacing={0.75} alignItems="center">
                  <Typography variant="body2" noWrap>{e.name}</Typography>
                  <Chip size="small" label={KIND_LABEL[e.kind] || e.kind}
                    color={KIND_COLOR[e.kind] || 'default'} variant="outlined" />
                </Stack>}
                secondary={e.description || e.file}
                secondaryTypographyProps={{ noWrap: true }}
              />
            </ListItemButton>
          ))}
          {!entries.length && (
            <Typography variant="body2" color="text.secondary" sx={{ p: 1 }}>没有匹配的技能</Typography>
          )}
        </List>
      </Paper>

      <Paper sx={{ flex: 1, minWidth: 360, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {content ? (
          <>
            <Box sx={{ px: 3, pt: 2.5, pb: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
              <Typography variant="h6">{content.name}</Typography>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 0.5 }} flexWrap="wrap" useFlexGap>
                <Chip size="small" label={KIND_LABEL[content.kind] || content.kind}
                  color={KIND_COLOR[content.kind] || 'default'} variant="outlined" />
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
              {loading ? '加载中…' : '选择左侧角色与技能查看内容'}
            </Typography>
          </Box>
        )}
      </Paper>
    </Box>
  )
}

import { useEffect, useMemo, useState } from 'react'
import {
  Paper, Typography, List, ListItemButton, ListItemText, TextField, Box, Divider,
  Chip, Stack,
} from '@mui/material'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getTeamSkills, getSkillContent } from '../api.js'

const KIND_LABEL = { skill: '角色方法', reference: '参考资料' }

export default function SkillsPage() {
  const [members, setMembers] = useState([])
  const [memberIndex, setMemberIndex] = useState(0)
  const [entryIndex, setEntryIndex] = useState(0)
  const [content, setContent] = useState(null)
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
    getSkillContent(memberIndex, target.index)
      .then((c) => { if (alive) setContent(c) })
      .catch(() => { if (alive) setContent(null) })
    return () => { alive = false }
  }, [members, memberIndex, entryIndex])

  const selectMember = (index) => {
    setMemberIndex(index)
    setEntryIndex(0)
    setQ('')
  }

  return (
    <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start', flexWrap: 'wrap' }}>
      <Paper sx={{ width: 230, p: 1 }}>
        <Typography variant="subtitle2" sx={{ px: 1, py: 0.5 }}>角色</Typography>
        <List dense>
          {members.map((m, i) => (
            <ListItemButton key={`${m.role}:${m.name}`} selected={i === memberIndex}
              onClick={() => selectMember(i)}>
              <ListItemText primary={m.name || m.role} secondary={`${m.count} 篇`} />
            </ListItemButton>
          ))}
        </List>
      </Paper>

      <Paper sx={{ width: 330, p: 1.5 }}>
        <TextField size="small" fullWidth placeholder="搜索技能 / 关键词…" value={q}
          onChange={(e) => setQ(e.target.value)} sx={{ mb: 1 }} />
        <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
          <Chip size="small" label={member?.name || '—'} />
          <Chip size="small" variant="outlined" label={`${entries.length} 项`} />
        </Stack>
        <List dense sx={{ maxHeight: 540, overflow: 'auto' }}>
          {entries.map((e) => (
            <ListItemButton key={e.index} selected={e.index === entryIndex}
              onClick={() => setEntryIndex(e.index)}>
              <ListItemText
                primary={e.name}
                secondary={KIND_LABEL[e.kind] || e.kind}
                secondaryTypographyProps={{ noWrap: true }}
              />
            </ListItemButton>
          ))}
          {!entries.length && (
            <Typography variant="body2" color="text.secondary" sx={{ p: 1 }}>没有匹配的技能</Typography>
          )}
        </List>
      </Paper>

      <Paper sx={{ flex: 1, minWidth: 360, p: 3, maxHeight: 640, overflow: 'auto' }}>
        {content ? (
          <>
            <Typography variant="h6">{content.name}</Typography>
            <Typography variant="caption" color="text.secondary">
              {content.source} · {KIND_LABEL[content.kind] || content.kind}
            </Typography>
            <Divider sx={{ my: 1.5 }} />
            <Box sx={{
              fontSize: 14, lineHeight: 1.75, wordBreak: 'break-word',
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
          <Typography color="text.secondary">选择左侧角色与技能查看内容</Typography>
        )}
      </Paper>
    </Box>
  )
}

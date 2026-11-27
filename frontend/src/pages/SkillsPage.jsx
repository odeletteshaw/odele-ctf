import { useEffect, useMemo, useState } from 'react'
import {
  Paper, Typography, List, ListItemButton, ListItemText, TextField, Box, Divider,
  Chip, Stack, InputAdornment,
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getTeamPacks, getLibrarySkill } from '../api.js'

const KIND_LABEL = { method: '方法', reference: '资料' }

export default function SkillsPage() {
  const [library, setLibrary] = useState([])
  const [tags, setTags] = useState([])
  const [selected, setSelected] = useState(null)
  const [content, setContent] = useState(null)
  const [loading, setLoading] = useState(false)
  const [q, setQ] = useState('')
  const [activeTags, setActiveTags] = useState([])

  useEffect(() => {
    getTeamPacks().then((r) => {
      setLibrary(r.packs || [])
      setTags(r.tags || [])
    })
  }, [])

  useEffect(() => {
    if (!library.length) return
    load(library[0].id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [library])

  const load = (id) => {
    setSelected(id)
    setLoading(true)
    getLibrarySkill(id)
      .then(setContent)
      .catch(() => setContent(null))
      .finally(() => setLoading(false))
  }

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return library.filter((s) => {
      if (activeTags.length && !activeTags.every((t) => s.tags.includes(t))) return false
      if (!needle) return true
      return `${s.name} ${s.id} ${s.description} ${s.tags.join(' ')}`
        .toLowerCase().includes(needle)
    })
  }, [library, q, activeTags])

  const toggleTag = (tag) => setActiveTags((current) => (
    current.includes(tag) ? current.filter((t) => t !== tag) : [...current, tag]
  ))

  return (
    <Box sx={{
      display: 'flex', flexDirection: 'column', gap: 1.5,
      height: 'calc(100vh - 140px)', minHeight: 560,
    }}>
      <Paper sx={{ p: 1.5 }}>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
          <TextField size="small" placeholder="搜索技能 / 标签 / 关键词…" value={q}
            onChange={(e) => setQ(e.target.value)} sx={{ minWidth: 280, flex: 1 }}
            InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> }} />
          <Typography variant="body2" color="text.secondary">
            {filtered.length} / {library.length} 条
          </Typography>
        </Stack>
        <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
          {tags.map((tag) => (
            <Chip key={tag} size="small" label={tag} clickable
              color={activeTags.includes(tag) ? 'primary' : 'default'}
              variant={activeTags.includes(tag) ? 'filled' : 'outlined'}
              onClick={() => toggleTag(tag)} />
          ))}
          {activeTags.length > 0 && (
            <Chip size="small" label="清除" variant="outlined" onClick={() => setActiveTags([])} />
          )}
        </Stack>
      </Paper>

      <Box sx={{ display: 'flex', gap: 1.5, flex: 1, minHeight: 0 }}>
        <Paper sx={{ width: 380, flexShrink: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <List dense sx={{ flex: 1, overflow: 'auto', px: 0.5, py: 0.5 }}>
            {filtered.map((skill) => (
              <ListItemButton key={skill.id} selected={skill.id === selected}
                onClick={() => load(skill.id)} sx={{ borderRadius: 1, mb: 0.25, alignItems: 'flex-start' }}>
                <ListItemText
                  primary={<Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" useFlexGap>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>{skill.name}</Typography>
                    <Chip size="small" label={KIND_LABEL[skill.kind] || skill.kind} variant="outlined" />
                  </Stack>}
                  secondary={<>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontFamily: 'Menlo,monospace' }}>
                      {skill.id}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }} noWrap>
                      {skill.description}
                    </Typography>
                  </>}
                />
              </ListItemButton>
            ))}
            {!filtered.length && (
              <Typography variant="body2" color="text.secondary" sx={{ p: 1 }}>没有匹配的技能</Typography>
            )}
          </List>
        </Paper>

        <Paper sx={{ flex: 1, minWidth: 360, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          {content ? (
            <>
              <Box sx={{ px: 3, pt: 2.5, pb: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
                <Typography variant="h6">{content.name}</Typography>
                <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mt: 0.5 }} flexWrap="wrap" useFlexGap>
                  <Chip size="small" label={KIND_LABEL[content.kind] || content.kind} variant="outlined" />
                  {(content.tags || []).map((t) => <Chip key={t} size="small" label={t} />)}
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
              <Typography color="text.secondary">{loading ? '加载中…' : '选择左侧技能查看内容'}</Typography>
            </Box>
          )}
        </Paper>
      </Box>
    </Box>
  )
}

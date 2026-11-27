import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Box, Paper, Typography, TextField, MenuItem, Button, Stack, Chip,
  IconButton, Tooltip, List, ListItemButton, Collapse,
} from '@mui/material'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import StopIcon from '@mui/icons-material/Stop'
import ReplayIcon from '@mui/icons-material/Replay'
import DeleteIcon from '@mui/icons-material/Delete'
import AddIcon from '@mui/icons-material/Add'
import {
  manualSolve, listSessions, stopSession, deleteSession, retrySession,
} from '../api.js'
import SessionPage from './SessionPage.jsx'

const STATUS = {
  running: { label: '进行中', color: 'warning' },
  preparing: { label: '准备中', color: 'default' },
  solved: { label: '已解', color: 'success' },
  done: { label: '完成', color: 'info' },
  failed: { label: '失败', color: 'error' },
  error: { label: '错误', color: 'error' },
  cancelled: { label: '已停止', color: 'warning' },
}
const FAILED = ['done', 'failed', 'error', 'cancelled']

export default function ManualPage() {
  const [direction, setDirection] = useState('web')
  const [urls, setUrls] = useState('')
  const [desc, setDesc] = useState('')
  const [turns, setTurns] = useState(100)
  const [prefix, setPrefix] = useState('')
  const [formOpen, setFormOpen] = useState(true)
  const [sessions, setSessions] = useState([])
  const [selectedId, setSelectedId] = useState(null)

  const refresh = useCallback(async () => {
    try { setSessions(await listSessions()) } catch { /* transient */ }
  }, [])

  useEffect(() => { refresh() }, [refresh])
  useEffect(() => {
    let ws
    function connect() {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/ws`)
      ws.onmessage = (e) => { if (JSON.parse(e.data).type === 'changed') refresh() }
      ws.onclose = () => setTimeout(connect, 2000)
    }
    connect()
    const timer = setInterval(refresh, 5000)
    return () => { clearInterval(timer); if (ws) ws.close() }
  }, [refresh])

  const manualSessions = useMemo(
    () => sessions.filter((s) => s.manual).sort((a, b) => b.id - a.id),
    [sessions],
  )

  useEffect(() => {
    if (!manualSessions.some((s) => s.id === selectedId)) {
      setSelectedId(manualSessions.length ? manualSessions[0].id : null)
    }
  }, [manualSessions, selectedId])

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
    try {
      const r = await manualSolve(spec, title)
      setUrls(''); setDesc('')
      setFormOpen(false)
      await refresh()
      if (r?.id) setSelectedId(r.id)
    } catch (e) { alert('启动失败: ' + e.message) }
  }

  const act = (fn) => (e) => { e.stopPropagation(); fn() }

  return (
    <Box sx={{ display: 'flex', gap: 2, height: 'calc(100vh - 112px)', minHeight: 560 }}>
      {/* ---- left: launch form + manual task list ---- */}
      <Paper sx={{ width: 420, flexShrink: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <Box sx={{ p: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
          <Stack direction="row" alignItems="center" sx={{ mb: formOpen ? 1.5 : 0 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, flex: 1 }}>手动解题</Typography>
            <Button size="small" startIcon={formOpen ? null : <AddIcon />}
              onClick={() => setFormOpen((v) => !v)}>
              {formOpen ? '收起' : '新建任务'}
            </Button>
          </Stack>
          <Collapse in={formOpen}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
              对你手动起的靶机执行角色团队：团队长拆解 → 侦察 → 方向专家 → 复盘。
            </Typography>
            <TextField select fullWidth size="small" label="方向" value={direction}
              onChange={(e) => setDirection(e.target.value)} sx={{ mb: 1.5 }}>
              {['web', 'crypto', 'forensics', 'cloud', 'blockchain', 'ics', 'iot']
                .map((d) => <MenuItem key={d} value={d}>{d}</MenuItem>)}
            </TextField>
            <TextField fullWidth size="small" multiline minRows={2} label="目标 URL（web 必填，每行一个）"
              value={urls} onChange={(e) => setUrls(e.target.value)} sx={{ mb: 1.5 }} />
            <TextField fullWidth size="small" label="题目描述 / 提示" value={desc}
              onChange={(e) => setDesc(e.target.value)} sx={{ mb: 1.5 }} />
            <Stack direction="row" spacing={1.5} sx={{ mb: 1.5 }}>
              <TextField size="small" type="number" label="max turns" value={turns}
                onChange={(e) => setTurns(e.target.value)} sx={{ width: 120 }} />
              <TextField size="small" fullWidth label="flag 前缀（留空 = 任意 XXX{...}）"
                value={prefix} onChange={(e) => setPrefix(e.target.value)} />
            </Stack>
            <Button fullWidth variant="contained" startIcon={<PlayArrowIcon />} onClick={start}>开始 ▶</Button>
          </Collapse>
        </Box>

        <List dense sx={{ flex: 1, overflow: 'auto', px: 1, py: 1 }}>
          {manualSessions.map((s) => {
            const st = STATUS[s.status] || { label: s.status, color: 'default' }
            const selected = s.id === selectedId
            return (
              <ListItemButton key={s.id} selected={selected} onClick={() => setSelectedId(s.id)}
                sx={{ borderRadius: 1, mb: 0.5, flexDirection: 'column', alignItems: 'stretch',
                  '&:hover .rowActions': { opacity: 1 } }}>
                <Stack direction="row" spacing={0.75} alignItems="center">
                  <Typography variant="caption" color="text.secondary">#{s.id}</Typography>
                  <Chip size="small" label={s.category} variant="outlined" sx={{ height: 18 }} />
                  <Box sx={{ flex: 1 }} />
                  <Chip size="small" label={st.label} color={st.color} sx={{ height: 20 }} />
                </Stack>
                <Typography variant="body2" noWrap title={s.title}
                  sx={{ mt: 0.5, fontWeight: selected ? 600 : 400 }}>
                  {s.title || '（未命名）'}
                </Typography>
                <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: 0.5 }}>
                  <Typography variant="caption" color="text.secondary">{s.created_at || '—'}</Typography>
                  <Box sx={{ flex: 1 }} />
                  <Stack direction="row" spacing={0.25} className="rowActions" sx={{ opacity: 0, transition: 'opacity .15s' }}>
                    {s.is_running
                      ? <Tooltip title="停止"><IconButton size="small" color="error" onClick={act(() => stopSession(s.id).then(refresh))}><StopIcon fontSize="small" /></IconButton></Tooltip>
                      : FAILED.includes(s.status) && <Tooltip title="重试"><IconButton size="small" onClick={act(() => retrySession(s.id).then(refresh))}><ReplayIcon fontSize="small" /></IconButton></Tooltip>}
                    <Tooltip title="删除"><IconButton size="small" color="error" onClick={act(() => deleteSession(s.id).then(refresh))}><DeleteIcon fontSize="small" /></IconButton></Tooltip>
                  </Stack>
                </Stack>
              </ListItemButton>
            )
          })}
          {!manualSessions.length && (
            <Typography color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>
              还没有手动任务，填上面的表单启动一个
            </Typography>
          )}
        </List>
      </Paper>

      {/* ---- right: selected manual task detail ---- */}
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <SessionPage key={selectedId ?? 'none'} id={selectedId} embedded />
      </Box>
    </Box>
  )
}

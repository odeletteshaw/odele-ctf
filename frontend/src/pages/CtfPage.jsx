import { useEffect, useState, useCallback } from 'react'
import {
  Box, Button, Chip, Dialog, DialogTitle, DialogContent, DialogActions,
  FormControlLabel, Checkbox, TextField, MenuItem, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, Paper, Typography,
  Stack, IconButton, Tooltip, Tabs, Tab,
} from '@mui/material'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import StopIcon from '@mui/icons-material/Stop'
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep'
import VisibilityIcon from '@mui/icons-material/Visibility'
import ReplayIcon from '@mui/icons-material/Replay'
import DeleteIcon from '@mui/icons-material/Delete'
import {
  listSessions, getStatus, getSlots, getSession, startAutosolve, stopAutosolve,
  stopSession, deleteSession, retrySession, batchDelete,
} from '../api.js'

const STATUS = {
  running: { label: '进行中', color: 'warning' },
  preparing: { label: '准备中', color: 'default' },
  solved: { label: '已解', color: 'success' },
  done: { label: '失败', color: 'error' },
  failed: { label: '失败', color: 'error' },
  error: { label: '错误', color: 'error' },
  cancelled: { label: '已停止', color: 'warning' },
  idle: { label: '待命', color: 'default' },
}
const FAILED = ['done', 'failed', 'error', 'cancelled']
const DIRS = ['web', 'crypto', 'misc', 'forensics']

export default function CtfPage() {
  const [sessions, setSessions] = useState([])
  const [autosolving, setAutosolving] = useState(false)
  const [slots, setSlots] = useState([])
  const [autoOpen, setAutoOpen] = useState(false)
  const [dirs, setDirs] = useState({})
  const [diff, setDiff] = useState('')
  const [maxn, setMaxn] = useState(3)
  const [detail, setDetail] = useState(null)
  const [tab, setTab] = useState(0)

  const refresh = useCallback(async () => {
    try {
      const [ss, st, sl] = await Promise.all([listSessions(), getStatus(), getSlots()])
      setSessions(ss)
      setAutosolving(st.is_autosolving)
      setSlots(sl)
    } catch (e) { /* ignore transient */ }
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

  const openAuto = () => {
    if (autosolving) { stopAutosolve().then(refresh); return }
    setDirs({})
    setAutoOpen(true)
  }
  const doStart = async () => {
    const chosen = DIRS.filter((d) => dirs[d])
    if (!chosen.length) return
    await startAutosolve({ directions: chosen, max: maxn, difficulty: diff ? { 简单: 'Easy', 中等: 'Medium', 困难: 'Hard' }[diff] : null })
    setAutoOpen(false)
    refresh()
  }

  const view = async (id) => { setDetail(await getSession(id)); setTab(0) }

  const slotText = slots.map((s) =>
    `${s.direction}·t${s.token_index} ${s.running ? s.phase + (s.current_title ? ':' + s.current_title : '') : '停'}`).join(' | ')

  return (
    <Box>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
        <Button variant="contained" startIcon={autosolving ? <StopIcon /> : <PlayArrowIcon />} onClick={openAuto}>
          {autosolving ? '停止打题' : '开始打题'}
        </Button>
        <Button color="error" startIcon={<DeleteSweepIcon />} onClick={() => batchDelete().then(refresh)}>批量删除失败</Button>
        <Typography variant="body2" color="text.secondary">
          {sessions.length} 个 session{slotText ? ` · ${slotText}` : ''}
        </Typography>
      </Stack>

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell width={60}>编号</TableCell>
              <TableCell width={80}>大类</TableCell>
              <TableCell>题目名称</TableCell>
              <TableCell width={80}>状态</TableCell>
              <TableCell width={110}>创建时间</TableCell>
              <TableCell width={220}>操作</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sessions.map((s) => {
              const st = STATUS[s.status] || { label: s.status, color: 'default' }
              return (
                <TableRow key={s.id} hover>
                  <TableCell color="text.secondary">{s.id}</TableCell>
                  <TableCell color="text.secondary">{s.category}</TableCell>
                  <TableCell>{s.title}</TableCell>
                  <TableCell><Chip size="small" label={st.label} color={st.color} /></TableCell>
                  <TableCell color="text.secondary">{s.created_at || '—'}</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5}>
                      <Tooltip title="查看"><IconButton size="small" onClick={() => view(s.id)}><VisibilityIcon /></IconButton></Tooltip>
                      {s.is_running
                        ? <Tooltip title="停止"><IconButton size="small" color="error" onClick={() => stopSession(s.id).then(refresh)}><StopIcon /></IconButton></Tooltip>
                        : FAILED.includes(s.status) && <Tooltip title="重试"><IconButton size="small" onClick={() => retrySession(s.id).then(refresh)}><ReplayIcon /></IconButton></Tooltip>}
                      <Tooltip title="删除"><IconButton size="small" color="error" onClick={() => deleteSession(s.id).then(refresh)}><DeleteIcon /></IconButton></Tooltip>
                    </Stack>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </TableContainer>

      {/* start autosolve dialog */}
      <Dialog open={autoOpen} onClose={() => setAutoOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>开始打题</DialogTitle>
        <DialogContent>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>方向（多选）</Typography>
          <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
            {DIRS.map((d) => (
              <FormControlLabel key={d} control={<Checkbox checked={!!dirs[d]} onChange={(e) => setDirs({ ...dirs, [d]: e.target.checked })} />} label={d} />
            ))}
          </Stack>
          <TextField select fullWidth label="难度" value={diff} onChange={(e) => setDiff(e.target.value)} sx={{ mb: 2 }}>
            <MenuItem value="">不限</MenuItem><MenuItem value="简单">简单</MenuItem><MenuItem value="中等">中等</MenuItem><MenuItem value="困难">困难</MenuItem>
          </TextField>
          <TextField fullWidth type="number" label="每个 token 最多解几道（0 = 不限）" value={maxn} onChange={(e) => setMaxn(parseInt(e.target.value || '0', 10))} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAutoOpen(false)}>取消</Button>
          <Button variant="contained" onClick={doStart}>开始 ▶</Button>
        </DialogActions>
      </Dialog>

      {/* detail dialog */}
      <Dialog open={!!detail} onClose={() => setDetail(null)} fullWidth maxWidth="md">
        {detail && (
          <>
            <DialogTitle>{detail.title} · {detail.category}</DialogTitle>
            <DialogContent>
              <Chip size="small" label={(STATUS[detail.status] || {}).label || detail.status} color={(STATUS[detail.status] || {}).color} />
              <Typography variant="body1" sx={{ mt: 1, color: 'success.main', fontFamily: 'Menlo,monospace' }}>
                FLAG {detail.flag || '—'}
              </Typography>
              <Tabs value={tab} onChange={(e, v) => setTab(v)} sx={{ mt: 1 }}>
                <Tab label="Findings" /><Tab label="Thinking" /><Tab label="题解" />
              </Tabs>
              <Box sx={{ mt: 1, whiteSpace: 'pre-wrap', fontFamily: 'Menlo,monospace', fontSize: 13, maxHeight: 420, overflow: 'auto' }}>
                {tab === 0 ? (detail.paths || []).map((p) => `- ${p}`).join('\n') || '—'
                  : tab === 1 ? (detail.thinking || '—')
                  : (detail.writeup || '（未生成）')}
              </Box>
            </DialogContent>
            <DialogActions><Button onClick={() => setDetail(null)}>关闭</Button></DialogActions>
          </>
        )}
      </Dialog>
    </Box>
  )
}

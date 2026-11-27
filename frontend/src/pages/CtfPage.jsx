import { useEffect, useState, useCallback, useMemo } from 'react'
import {
  Box, Button, Chip, Dialog, DialogTitle, DialogContent, DialogActions,
  FormControlLabel, Checkbox, TextField, MenuItem, Paper, Typography,
  Stack, IconButton, Tooltip, Alert, List, ListItemButton,
} from '@mui/material'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import StopIcon from '@mui/icons-material/Stop'
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep'
import ReplayIcon from '@mui/icons-material/Replay'
import DeleteIcon from '@mui/icons-material/Delete'
import {
  listSessions, getStatus, getSlots, startAutosolve, stopAutosolve,
  stopSession, deleteSession, retrySession, batchDelete, listTokens,
} from '../api.js'
import SessionPage from './SessionPage.jsx'

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
  const [q, setQ] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [catFilter, setCatFilter] = useState('all')
  const [selectedId, setSelectedId] = useState(null)
  const [availableTokens, setAvailableTokens] = useState([])
  const [chosenTokens, setChosenTokens] = useState([])

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

  const openAuto = async () => {
    if (autosolving) { stopAutosolve().then(refresh).catch((e) => alert('停止失败: ' + e.message)); return }
    try {
      const r = await listTokens()
      const hints = r.tokens || []
      setAvailableTokens(hints)
      setChosenTokens(hints.map((t) => t.index))
    } catch {
      setAvailableTokens([])
      setChosenTokens([])
    }
    setDirs({})
    setAutoOpen(true)
  }
  const doStart = async () => {
    const chosen = DIRS.filter((d) => dirs[d])
    if (!chosen.length) { alert('请至少勾选一个方向'); return }
    if (!chosenTokens.length) { alert('请至少选择一个 token'); return }
    try {
      await startAutosolve({
        directions: chosen,
        max: maxn,
        difficulty: diff ? { 简单: 'Easy', 中等: 'Medium', 困难: 'Hard' }[diff] : null,
        tokens: chosenTokens,
      })
      setAutoOpen(false)
      await refresh()
    } catch (e) {
      alert('启动失败: ' + e.message)
    }
  }

  const categories = useMemo(
    () => [...new Set(sessions.map((s) => s.category).filter(Boolean))].sort(),
    [sessions],
  )

  const visible = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return sessions
      .filter((s) => {
        if (statusFilter !== 'all' && s.status !== statusFilter) return false
        if (catFilter !== 'all' && s.category !== catFilter) return false
        if (!needle) return true
        return [s.id, s.title, s.category, s.status]
          .some((v) => String(v ?? '').toLowerCase().includes(needle))
      })
      .sort((a, b) => b.id - a.id)  // newest first
  }, [sessions, q, statusFilter, catFilter])

  // Default to the first task; keep a valid selection when the list changes.
  useEffect(() => {
    if (!visible.some((s) => s.id === selectedId)) {
      setSelectedId(visible.length ? visible[0].id : null)
    }
  }, [visible, selectedId])

  const act = (fn) => (e) => { e.stopPropagation(); fn() }

  const slotText = slots.map((s) =>
    `${s.direction}·t${s.token_index} ${s.running ? s.phase + (s.current_title ? ':' + s.current_title : '') : '停'}`).join(' | ')

  return (
    <Box sx={{ display: 'flex', gap: 2, height: 'calc(100vh - 112px)', minHeight: 560 }}>
      {/* ---- left: task list ---- */}
      <Paper sx={{ width: 400, flexShrink: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <Box sx={{ p: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
          <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
            <Button fullWidth variant="contained" size="small"
              startIcon={autosolving ? <StopIcon /> : <PlayArrowIcon />} onClick={openAuto}>
              {autosolving ? '停止打题' : '开始打题'}
            </Button>
            <Tooltip title="批量删除失败任务">
              <IconButton color="error" size="small" onClick={() => batchDelete().then(refresh)}>
                <DeleteSweepIcon />
              </IconButton>
            </Tooltip>
          </Stack>
          <TextField fullWidth size="small" label="搜索题目 / 编号 / 大类" value={q}
            onChange={(e) => setQ(e.target.value)} sx={{ mb: 1 }} />
          <Stack direction="row" spacing={1}>
            <TextField select size="small" label="状态" value={statusFilter} fullWidth
              onChange={(e) => setStatusFilter(e.target.value)}>
              <MenuItem value="all">全部状态</MenuItem>
              {Object.entries(STATUS).map(([key, st]) => (
                <MenuItem key={key} value={key}>{st.label}</MenuItem>
              ))}
            </TextField>
            <TextField select size="small" label="大类" value={catFilter} fullWidth
              onChange={(e) => setCatFilter(e.target.value)}>
              <MenuItem value="all">全部大类</MenuItem>
              {categories.map((c) => <MenuItem key={c} value={c}>{c}</MenuItem>)}
            </TextField>
          </Stack>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
            {visible.length} / {sessions.length} 个任务{slotText ? ` · ${slotText}` : ''}
          </Typography>
        </Box>

        <List dense sx={{ flex: 1, overflow: 'auto', px: 1, py: 1 }}>
          {visible.map((s) => {
            const st = STATUS[s.status] || { label: s.status, color: 'default' }
            const selected = s.id === selectedId
            return (
              <ListItemButton key={s.id} selected={selected} onClick={() => setSelectedId(s.id)}
                sx={{
                  borderRadius: 1, mb: 0.5, flexDirection: 'column', alignItems: 'stretch',
                  '&:hover .rowActions': { opacity: 1 },
                }}>
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
                  {s.pending_approvals > 0 && (
                    <Chip size="small" color="warning" sx={{ height: 18 }} label={`待审批 ${s.pending_approvals}`} />
                  )}
                  {s.pending_mentions > 0 && (
                    <Chip size="small" color="info" sx={{ height: 18 }} label={`@你 ${s.pending_mentions}`} />
                  )}
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
          {!visible.length && (
            <Typography color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>没有匹配的任务</Typography>
          )}
        </List>
      </Paper>

      {/* ---- right: selected task detail ---- */}
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <SessionPage key={selectedId ?? 'none'} id={selectedId} embedded />
      </Box>

      {/* start autosolve dialog */}
      <Dialog open={autoOpen} onClose={() => setAutoOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>开始打题</DialogTitle>
        <DialogContent>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>方向（多选）</Typography>
          <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
            {DIRS.map((d) => (
              <FormControlLabel key={d} control={<Checkbox checked={!!dirs[d]} onChange={(e) => setDirs({ ...dirs, [d]: e.target.checked })} />} label={d} />
            ))}
          </Stack>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            将以角色团队执行：团队长接收命令后输出 DAG，扁平角色按需调度，需要时请求你审批。
          </Typography>
          <Typography variant="subtitle2" sx={{ mb: 0.5 }}>本次使用哪些 token</Typography>
          <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
            {availableTokens.map((t) => (
              <FormControlLabel key={t.index}
                control={<Checkbox checked={chosenTokens.includes(t.index)}
                  onChange={(e) => setChosenTokens(e.target.checked
                    ? [...chosenTokens, t.index].sort((a, b) => a - b)
                    : chosenTokens.filter((x) => x !== t.index))} />}
                label={`#${t.index} ${t.hint}`} />
            ))}
            {!availableTokens.length && (
              <Alert severity="warning">还没有平台 token，请到「配置管理」页添加</Alert>
            )}
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
    </Box>
  )
}

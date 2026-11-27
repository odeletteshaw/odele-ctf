import { useEffect, useState, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Box, Button, Chip, Dialog, DialogTitle, DialogContent, DialogActions,
  FormControlLabel, Checkbox, TextField, MenuItem, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, Paper, Typography,
  Stack, IconButton, Tooltip, TableSortLabel, Alert, TablePagination,
} from '@mui/material'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import StopIcon from '@mui/icons-material/Stop'
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep'
import VisibilityIcon from '@mui/icons-material/Visibility'
import ReplayIcon from '@mui/icons-material/Replay'
import DeleteIcon from '@mui/icons-material/Delete'
import {
  listSessions, getStatus, getSlots, startAutosolve, stopAutosolve,
  stopSession, deleteSession, retrySession, batchDelete, listTokens,
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
  const navigate = useNavigate()
  const [sessions, setSessions] = useState([])
  const [autosolving, setAutosolving] = useState(false)
  const [slots, setSlots] = useState([])
  const [autoOpen, setAutoOpen] = useState(false)
  const [dirs, setDirs] = useState({})
  const [diff, setDiff] = useState('')
  const [maxn, setMaxn] = useState(3)
  const [page, setPage] = useState(0)
  const [rowsPerPage, setRowsPerPage] = useState(20)
  const [q, setQ] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [catFilter, setCatFilter] = useState('all')
  const [sort, setSort] = useState({ key: 'id', dir: 'desc' })
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
      setSort({ key: 'id', dir: 'desc' })  // newest session first
      await refresh()
    } catch (e) {
      alert('启动失败: ' + e.message)
    }
  }

  const categories = useMemo(
    () => [...new Set(sessions.map((s) => s.category).filter(Boolean))].sort(),
    [sessions],
  )

  const toggleSort = (key) => setSort((cur) => (
    cur.key === key
      ? { key, dir: cur.dir === 'asc' ? 'desc' : 'asc' }
      : { key, dir: key === 'id' || key === 'created' ? 'desc' : 'asc' }
  ))

  const visible = useMemo(() => {
    const needle = q.trim().toLowerCase()
    const created = (s) => {
      if (s.created_ts) return s.created_ts
      if (!s.created_at) return 0
      const t = Date.parse(`${new Date().getFullYear()}-${s.created_at.replace(' ', 'T')}`)
      return Number.isNaN(t) ? 0 : t
    }
    const value = (s) => (
      sort.key === 'created' ? created(s)
        : sort.key === 'id' ? s.id
          : String(s[sort.key] ?? '')
    )
    return sessions
      .filter((s) => {
        if (statusFilter !== 'all' && s.status !== statusFilter) return false
        if (catFilter !== 'all' && s.category !== catFilter) return false
        if (!needle) return true
        return [s.id, s.title, s.category, s.status]
          .some((v) => String(v ?? '').toLowerCase().includes(needle))
      })
      .sort((a, b) => {
        const va = value(a)
        const vb = value(b)
        const cmp = typeof va === 'number' && typeof vb === 'number'
          ? va - vb
          : String(va).localeCompare(String(vb))
        return sort.dir === 'asc' ? cmp : -cmp
      })
  }, [sessions, q, statusFilter, catFilter, sort])

  const view = (id) => navigate(`/sessions/${id}`)
  const shown = visible.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)

  useEffect(() => { setPage(0) }, [q, statusFilter, catFilter, sort])

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
          显示 {visible.length} / {sessions.length} 个任务{slotText ? ` · ${slotText}` : ''}
        </Typography>
      </Stack>

      <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
        <TextField size="small" label="搜索题目 / 编号 / 大类" value={q}
          onChange={(e) => setQ(e.target.value)} sx={{ minWidth: 240 }} />
        <TextField select size="small" label="状态" value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)} sx={{ minWidth: 140 }}>
          <MenuItem value="all">全部状态</MenuItem>
          {Object.entries(STATUS).map(([key, st]) => (
            <MenuItem key={key} value={key}>{st.label}（{key}）</MenuItem>
          ))}
        </TextField>
        <TextField select size="small" label="大类" value={catFilter}
          onChange={(e) => setCatFilter(e.target.value)} sx={{ minWidth: 140 }}>
          <MenuItem value="all">全部大类</MenuItem>
          {categories.map((c) => <MenuItem key={c} value={c}>{c}</MenuItem>)}
        </TextField>
        <Button onClick={() => { setQ(''); setStatusFilter('all'); setCatFilter('all') }}>
          重置筛选
        </Button>
      </Stack>

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              {[
                ['id', '编号', 70],
                ['category', '大类', 90],
                ['title', '题目名称', null],
                ['status', '状态', 90],
                ['created', '创建时间', 120],
              ].map(([key, label, width]) => (
                <TableCell key={key} width={width || undefined} sortDirection={sort.key === key ? sort.dir : false}>
                  <TableSortLabel
                    active={sort.key === key}
                    direction={sort.key === key ? sort.dir : 'asc'}
                    onClick={() => toggleSort(key)}
                  >
                    {label}
                  </TableSortLabel>
                </TableCell>
              ))}
              <TableCell width={220}>操作</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {shown.map((s) => {
              const st = STATUS[s.status] || { label: s.status, color: 'default' }
              return (
                <TableRow key={s.id} hover>
                  <TableCell color="text.secondary">{s.id}</TableCell>
                  <TableCell color="text.secondary">{s.category}</TableCell>
                  <TableCell>{s.title}</TableCell>
                  <TableCell>
                    <Chip size="small" label={st.label} color={st.color} />
                    {s.pending_approvals > 0 && (
                      <Chip size="small" color="warning" sx={{ ml: 0.5 }}
                        label={`待审批 ${s.pending_approvals}`} />
                    )}
                    {s.pending_mentions > 0 && (
                      <Chip size="small" color="info" sx={{ ml: 0.5 }}
                        label={`@你 ${s.pending_mentions}`} />
                    )}
                  </TableCell>
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
        <TablePagination
          component="div"
          count={visible.length}
          page={page}
          rowsPerPage={rowsPerPage}
          onPageChange={(e, next) => setPage(next)}
          onRowsPerPageChange={(e) => {
            setRowsPerPage(parseInt(e.target.value, 10))
            setPage(0)
          }}
          rowsPerPageOptions={[10, 20, 50, 100]}
          labelRowsPerPage="每页"
        />
      </TableContainer>

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

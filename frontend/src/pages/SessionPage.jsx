import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Paper, Typography, Box, Stack, Chip, Button, IconButton, Tooltip, Alert,
  Tabs, Tab, Divider, List, ListItem, ListItemText,
} from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getSession, approveSession } from '../api.js'

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
const NODE_STATUS = {
  start: { label: '执行中', color: 'warning' },
  end: { label: '完成', color: 'success' },
  skipped: { label: '跳过', color: 'default' },
  rejected: { label: '驳回', color: 'error' },
  approved: { label: '已批准', color: 'info' },
}

function eventLine(event) {
  const role = event.name || event.role || event.role_id || ''
  const prefix = role ? `[${role}] ` : ''
  switch (event.type) {
    case 'agent': return `${prefix}${event.text || ''}`
    case 'tool_call': return `${prefix}▶ ${event.name} ${JSON.stringify(event.args || {})}`
    case 'tool_result': {
      const out = String(event.output || '')
      return `${prefix}◀ ${event.name}: ${out.length > 500 ? out.slice(0, 500) + ' …' : out}`
    }
    case 'guidance': return `[supervisor] ${event.text || ''}`
    case 'approval': return `[approval] ${event.node || ''} ${event.status || ''}`
    case 'role': return `[role] ${event.name || ''} ${event.node || ''} ${event.status || ''}`
    case 'status': return `[status] ${event.status || ''} ${event.flag || ''}`
    default: return null
  }
}

export default function SessionPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [session, setSession] = useState(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState(0)

  const refresh = useCallback(async () => {
    try {
      setSession(await getSession(id))
      setError('')
    } catch (e) {
      setError(e.message)
    }
  }, [id])

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, 2000)
    return () => clearInterval(timer)
  }, [refresh])

  const pending = (session?.approvals || []).filter((a) => a.status === 'pending')
  const status = STATUS[session?.status] || { label: session?.status, color: 'default' }
  const transcript = useMemo(() => {
    const events = session?.transcript || []
    const lines = events.map(eventLine).filter(Boolean)
    return lines.slice(-300).join('\n')
  }, [session])

  const approve = async (node, ok) => {
    try {
      await approveSession(id, node, ok)
      refresh()
    } catch (e) { setError(e.message) }
  }

  if (!session) {
    return (
      <Box sx={{ p: 2 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/')}>返回</Button>
        <Typography sx={{ mt: 2 }} color="text.secondary">
          {error || '加载中…'}
        </Typography>
      </Box>
    )
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, height: 'calc(100vh - 112px)', minHeight: 560 }}>
      <Paper sx={{ p: 2 }}>
        <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
          <Tooltip title="返回列表">
            <IconButton onClick={() => navigate('/')}><ArrowBackIcon /></IconButton>
          </Tooltip>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>{session.title}</Typography>
          <Chip size="small" label={session.category} variant="outlined" />
          <Chip size="small" label={status.label} color={status.color} />
          {pending.length > 0 && <Chip size="small" color="warning" label={`待审批 ${pending.length}`} />}
          <Box sx={{ flex: 1 }} />
          <Typography variant="body2" color="text.secondary">
            #{session.id} · {session.created_at || '—'} · {session.tool_calls} 次调用 · {session.replies} 条回复
          </Typography>
        </Stack>
        <Typography variant="body1" sx={{ mt: 1, fontFamily: 'Menlo,monospace', color: 'success.main' }}>
          FLAG {session.flag || '—'}
        </Typography>
        {pending.map((a) => (
          <Alert key={a.node} severity="warning" sx={{ mt: 1.5 }}
            action={
              <Stack direction="row" spacing={1}>
                <Button color="success" size="small" variant="contained" onClick={() => approve(a.node, true)}>批准</Button>
                <Button color="error" size="small" variant="outlined" onClick={() => approve(a.node, false)}>驳回</Button>
              </Stack>
            }>
            <Typography variant="subtitle2">{a.role} 请求审批 · 节点 {a.node}</Typography>
            <Typography variant="body2">{a.task || '（无任务说明）'}</Typography>
          </Alert>
        ))}
        {error && <Alert severity="error" sx={{ mt: 1.5 }}>{error}</Alert>}
      </Paper>

      <Box sx={{ display: 'flex', gap: 1.5, flex: 1, minHeight: 0 }}>
        <Paper sx={{ width: 380, flexShrink: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <Box sx={{ p: 1.5, pb: 0.5 }}>
            <Typography variant="subtitle2">团队复盘（实时）</Typography>
            <Typography variant="caption" color="text.secondary">{(session.roles || []).length} 个事件</Typography>
          </Box>
          <Divider />
          <List dense sx={{ flex: 1, overflow: 'auto', px: 0.5, py: 0.5 }}>
            {(session.roles || []).map((r, i) => {
              const meta = NODE_STATUS[r.status] || { label: r.status, color: 'default' }
              return (
                <ListItem key={i} alignItems="flex-start" sx={{ py: 0.75 }}>
                  <ListItemText
                    primary={<Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" useFlexGap>
                      <Chip size="small" color={meta.color} label={meta.label} />
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>{r.name || r.role}</Typography>
                      <Typography variant="caption" color="text.secondary">节点 {r.node}</Typography>
                    </Stack>}
                    secondary={r.summary || ''}
                    secondaryTypographyProps={{ sx: { whiteSpace: 'pre-wrap', fontSize: 12 } }}
                  />
                </ListItem>
              )
            })}
            {!(session.roles || []).length && (
              <Typography variant="body2" color="text.secondary" sx={{ p: 1 }}>等待团队开始…</Typography>
            )}
          </List>
        </Paper>

        <Paper sx={{ flex: 1, minWidth: 380, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <Tabs value={tab} onChange={(e, v) => setTab(v)} sx={{ px: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
            <Tab label="题解" /><Tab label="执行对话" /><Tab label="Thinking" /><Tab label="Findings" />
          </Tabs>
          <Box sx={{
            flex: 1, overflow: 'auto', px: 2.5, py: 2, fontSize: 14, lineHeight: 1.75,
            wordBreak: 'break-word',
            '& h1': { fontSize: 22, mt: 2, mb: 1 },
            '& h2': { fontSize: 18, mt: 2, mb: 1 },
            '& h3': { fontSize: 16, mt: 1.5, mb: 0.75 },
            '& pre': { bgcolor: '#0b0f15', p: 1.5, borderRadius: 1, overflow: 'auto' },
            '& code': { fontFamily: 'Menlo,monospace' },
            '& blockquote': { borderLeft: '3px solid', borderColor: 'primary.main', ml: 0, pl: 1.5, color: 'text.secondary' },
            '& table': { borderCollapse: 'collapse', width: '100%', my: 1 },
            '& th, & td': { border: '1px solid', borderColor: 'divider', px: 1, py: 0.5 },
          }}>
            {tab === 0 && (session.writeup ? (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{session.writeup}</ReactMarkdown>
            ) : <Typography color="text.secondary">（尚未生成题解）</Typography>)}
            {tab === 1 && (
              <Typography component="pre" sx={{ fontFamily: 'Menlo,monospace', fontSize: 12, whiteSpace: 'pre-wrap', m: 0 }}>
                {transcript || '（暂无对话）'}
              </Typography>
            )}
            {tab === 2 && (
              <Typography component="pre" sx={{ fontFamily: 'Menlo,monospace', fontSize: 13, whiteSpace: 'pre-wrap', m: 0 }}>
                {session.thinking || '（暂无）'}
              </Typography>
            )}
            {tab === 3 && (
              <Stack spacing={2}>
                <Box>
                  <Typography variant="subtitle2" sx={{ mb: 0.5 }}>访问过的路径</Typography>
                  <Typography component="pre" sx={{ fontFamily: 'Menlo,monospace', fontSize: 12, whiteSpace: 'pre-wrap', m: 0 }}>
                    {(session.paths || []).map((p) => `- ${p}`).join('\n') || '—'}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="subtitle2" sx={{ mb: 0.5 }}>工具使用</Typography>
                  <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                    {Object.entries(session.tools_used || {}).map(([name, count]) => (
                      <Chip key={name} size="small" label={`${name} × ${count}`} />
                    ))}
                  </Stack>
                </Box>
              </Stack>
            )}
          </Box>
        </Paper>
      </Box>
    </Box>
  )
}

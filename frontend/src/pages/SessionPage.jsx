import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Paper, Typography, Box, Stack, Chip, Button, IconButton, Tooltip, Alert,
  Tabs, Tab, Divider, TextField,
} from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import SendIcon from '@mui/icons-material/Send'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getSession, approveSession, sendGuidance, sendReply } from '../api.js'

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
    case 'message': return `[${event.from || ''} → ${event.to || ''}] ${event.text || ''}`
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
  const [text, setText] = useState('')

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

  const transcript = useMemo(() => {
    const lines = (session?.transcript || []).map(eventLine).filter(Boolean)
    return lines.slice(-300).join('\n')
  }, [session])

  const pendingApprovals = (session?.approvals || []).filter((a) => a.status === 'pending')
  const pendingMentions = (session?.mentions || []).filter((m) => m.status === 'pending')
  const pendingMention = pendingMentions[0]
  const status = STATUS[session?.status] || { label: session?.status, color: 'default' }

  const approve = async (node, ok) => {
    try {
      await approveSession(id, node, ok)
      refresh()
    } catch (e) { setError(e.message) }
  }

  const send = async () => {
    if (!session || !text.trim()) return
    try {
      if (pendingMention) await sendReply(id, text.trim())
      else await sendGuidance(id, text.trim())
      setText('')
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
          <Tooltip title="返回任务列表">
            <IconButton onClick={() => navigate('/')}><ArrowBackIcon /></IconButton>
          </Tooltip>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>{session.title}</Typography>
          <Chip size="small" label={session.category} variant="outlined" />
          <Chip size="small" label={status.label} color={status.color} />
          {pendingApprovals.length > 0 && <Chip size="small" color="warning" label={`待审批 ${pendingApprovals.length}`} />}
          {pendingMentions.length > 0 && <Chip size="small" color="info" label={`@你 ${pendingMentions.length}`} />}
          <Box sx={{ flex: 1 }} />
          <Typography variant="body2" color="text.secondary">
            任务 #{session.id} · {session.created_at || '—'} · {session.tool_calls} 次调用 · {session.replies} 条回复
          </Typography>
        </Stack>
        <Typography variant="body1" sx={{ mt: 1, fontFamily: 'Menlo,monospace', color: 'success.main' }}>
          FLAG {session.flag || '—'}
        </Typography>
        {pendingApprovals.map((a) => (
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
        {pendingMentions.map((m) => (
          <Alert key={m.node} severity="info" sx={{ mt: 1.5 }}
            action={<Button size="small" onClick={() => setTab(0)}>去回复</Button>}>
            <Typography variant="subtitle2">{m.from} @ 你 · 节点 {m.node}</Typography>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{m.text}</Typography>
          </Alert>
        ))}
        {error && <Alert severity="error" sx={{ mt: 1.5 }}>{error}</Alert>}
      </Paper>

      <Paper sx={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <Tabs value={tab} onChange={(e, v) => setTab(v)} sx={{ px: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
          <Tab label="通话" /><Tab label="题解" /><Tab label="执行对话" /><Tab label="Thinking" /><Tab label="Findings" />
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
          {tab === 0 && (
            <Stack spacing={1}>
              {(session.messages || []).map((m, i) => {
                const mine = m.from === '你'
                return (
                  <Box key={i} sx={{ display: 'flex', justifyContent: mine ? 'flex-end' : 'flex-start' }}>
                    <Box sx={{
                      maxWidth: '85%', px: 1.25, py: 0.75, borderRadius: 2,
                      bgcolor: mine ? 'primary.dark' : 'background.paper',
                      border: mine ? 'none' : '1px solid', borderColor: 'divider',
                    }}>
                      <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mb: 0.25 }}>
                        <Typography variant="caption" sx={{ fontWeight: 600 }}>{m.from || '系统'}</Typography>
                        <Typography variant="caption" color="text.secondary">→ {m.to || '团队'}</Typography>
                        {m.node && m.node !== 'plan' && (
                          <Typography variant="caption" color="text.secondary">节点 {m.node}</Typography>
                        )}
                      </Stack>
                      <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                        {m.text}
                      </Typography>
                    </Box>
                  </Box>
                )
              })}
              {pendingMentions.map((m) => (
                <Alert key={m.node} severity="warning">
                  <Typography variant="subtitle2">{m.from} @ 你 · 节点 {m.node}</Typography>
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{m.text}</Typography>
                </Alert>
              ))}
              {!(session.messages || []).length && (
                <Typography color="text.secondary">等待团队开始…</Typography>
              )}
            </Stack>
          )}
          {tab === 1 && (session.writeup ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{session.writeup}</ReactMarkdown>
          ) : <Typography color="text.secondary">（尚未生成题解）</Typography>)}
          {tab === 2 && (
            <Typography component="pre" sx={{ fontFamily: 'Menlo,monospace', fontSize: 12, whiteSpace: 'pre-wrap', m: 0 }}>
              {transcript || '（暂无对话）'}
            </Typography>
          )}
          {tab === 3 && (
            <Typography component="pre" sx={{ fontFamily: 'Menlo,monospace', fontSize: 13, whiteSpace: 'pre-wrap', m: 0 }}>
              {session.thinking || '（暂无）'}
            </Typography>
          )}
          {tab === 4 && (
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
        {tab === 0 && (
          <>
            <Divider />
            <Stack direction="row" spacing={1} sx={{ p: 1.5 }}>
              <TextField fullWidth size="small" value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
                placeholder={pendingMention
                  ? `回复 @${pendingMention.from}…`
                  : '给团队发消息（supervisor guidance）…'}
                disabled={!session.is_running && !pendingMention} />
              <Button variant="contained" endIcon={<SendIcon />} onClick={send}
                disabled={!text.trim() || (!session.is_running && !pendingMention)}>
                发送
              </Button>
            </Stack>
          </>
        )}
      </Paper>
    </Box>
  )
}

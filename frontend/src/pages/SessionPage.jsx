import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Paper, Typography, Box, Stack, Chip, Button, IconButton, Tooltip, Alert,
  Tabs, Tab, Divider, TextField, Avatar,
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

const AVATAR_COLORS = ['#4caf8f', '#5c8df6', '#c17bf0', '#e0a458',
  '#e06c75', '#56b6c2', '#a3be8c', '#d08770']

function colorFor(name = '') {
  let hash = 0
  for (const ch of name) hash = (hash * 31 + (ch.codePointAt(0) || 0)) >>> 0
  return AVATAR_COLORS[hash % AVATAR_COLORS.length]
}

function RoleAvatar({ name, size = 30 }) {
  return (
    <Avatar sx={{
      width: size, height: size, bgcolor: colorFor(name),
      color: '#0f1218', fontSize: 13, fontWeight: 700, flexShrink: 0,
    }}>
      {(name || '?').slice(0, 1)}
    </Avatar>
  )
}

function MessageBubble({ m, onReply }) {
  const mine = m.from === '你'
  const targeted = m.to && m.to !== '团队' && m.to !== '你'
  return (
    <Stack direction={mine ? 'row-reverse' : 'row'} spacing={1} alignItems="flex-start">
      <RoleAvatar name={m.from} />
      <Box sx={{ maxWidth: '82%' }}>
        <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mb: 0.35 }}
          justifyContent={mine ? 'flex-end' : 'flex-start'} flexWrap="wrap" useFlexGap>
          <Typography variant="caption" sx={{ fontWeight: 600 }}>{m.from || '系统'}</Typography>
          {targeted ? (
            <Chip
              size="small"
              label={`@${m.to}`}
              onClick={onReply ? () => onReply(m.to) : undefined}
              sx={{
                height: 20, fontWeight: 700, color: '#0f1218',
                bgcolor: colorFor(m.to),
                '& .MuiChip-label': { px: 0.75 },
              }}
            />
          ) : (
            <Typography variant="caption" color="text.secondary">→ {m.to || '团队'}</Typography>
          )}
          {m.kind === 'plan' && <Chip size="small" variant="outlined" label="计划" sx={{ height: 18 }} />}
          {m.kind === 'result' && <Chip size="small" variant="outlined" label="结果" sx={{ height: 18 }} />}
        </Stack>
        <Box sx={{
          px: 1.5, py: 1, borderRadius: 2,
          bgcolor: targeted ? 'rgba(76,175,143,0.12)' : mine ? 'primary.dark' : 'background.paper',
          border: '1px solid',
          borderColor: targeted ? colorFor(m.to) : 'divider',
          boxShadow: targeted ? `inset 3px 0 0 ${colorFor(m.to)}` : 'none',
        }}>
          {targeted && (
            <Typography variant="caption" sx={{ display: 'block', mb: 0.35, color: colorFor(m.to), fontWeight: 600 }}>
              任务分派给 {m.to}
            </Typography>
          )}
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {m.text}
          </Typography>
        </Box>
      </Box>
    </Stack>
  )
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
    const timer = setInterval(refresh, 3000)
    return () => clearInterval(timer)
  }, [refresh])

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
            <Typography variant="subtitle2">{a.role} 请求审批</Typography>
            <Typography variant="body2">{a.task || '（无任务说明）'}</Typography>
          </Alert>
        ))}
        {pendingMentions.map((m) => (
          <Alert key={m.node} severity="info" sx={{ mt: 1.5 }}
            action={<Button size="small" onClick={() => setTab(0)}>去回复</Button>}>
            <Typography variant="subtitle2">{m.from} @ 你</Typography>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{m.text}</Typography>
          </Alert>
        ))}
        {error && <Alert severity="error" sx={{ mt: 1.5 }}>{error}</Alert>}
      </Paper>

      <Paper sx={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <Tabs value={tab} onChange={(e, v) => setTab(v)} sx={{ px: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
          <Tab label="通话" /><Tab label="题解" /><Tab label="Findings" />
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
            <Stack spacing={1.5}>
              {(session.messages || []).map((m, i) => (
                <MessageBubble key={i} m={m}
                  onReply={(name) => setText(`@${name} `)} />
              ))}
              {pendingMentions.map((m) => (
                <Alert key={m.node} severity="warning">
                  <Typography variant="subtitle2">{m.from} @ 你</Typography>
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

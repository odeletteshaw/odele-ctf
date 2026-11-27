import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Paper, Typography, Box, Stack, Chip, TextField, Button, List, ListItemButton,
  ListItemText, Divider, Alert,
} from '@mui/material'
import SendIcon from '@mui/icons-material/Send'
import ForumIcon from '@mui/icons-material/Forum'
import { getCalls, sendGuidance, sendReply } from '../api.js'

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
const KIND_LABEL = {
  plan: '计划', assignment: '分派', result: '结果', user: '你的消息',
}

export default function CallsPage() {
  const [sessions, setSessions] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const load = useCallback(async () => {
    try {
      const r = await getCalls()
      const list = r.sessions || []
      setSessions(list)
      setSelectedId((current) => (
        current && list.some((s) => s.id === current) ? current : (list[0]?.id ?? null)
      ))
      setError('')
    } catch (e) { setError(e.message) }
  }, [])

  useEffect(() => {
    load()
    const timer = setInterval(load, 3000)
    return () => clearInterval(timer)
  }, [load])

  const current = useMemo(() => sessions.find((s) => s.id === selectedId) || null, [sessions, selectedId])
  const pendingMention = (current?.mentions || []).find((m) => m.status === 'pending')
  const messages = current?.messages || []

  const send = async () => {
    if (!current || !text.trim()) return
    try {
      if (pendingMention) await sendReply(current.id, text.trim())
      else await sendGuidance(current.id, text.trim())
      setText('')
      load()
    } catch (e) { setError(e.message) }
  }

  const status = STATUS[current?.status] || { label: current?.status, color: 'default' }

  return (
    <Box sx={{ display: 'flex', gap: 1.5, height: 'calc(100vh - 112px)', minHeight: 560 }}>
      <Paper sx={{ width: 300, flexShrink: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <Box sx={{ p: 1.5, pb: 0.5 }}>
          <Stack direction="row" spacing={1} alignItems="center">
            <ForumIcon fontSize="small" />
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>通话</Typography>
            <Chip size="small" label={`${sessions.length} 个会话`} />
          </Stack>
          <Typography variant="caption" color="text.secondary">
            团队成员之间的消息、角色 @ 你的求助与你的回复
          </Typography>
        </Box>
        <Divider />
        <List dense sx={{ flex: 1, overflow: 'auto', px: 0.5, py: 0.5 }}>
          {sessions.map((s) => {
            const st = STATUS[s.status] || { label: s.status, color: 'default' }
            const last = (s.messages || []).slice(-1)[0]
            return (
              <ListItemButton key={s.id} selected={s.id === selectedId}
                onClick={() => setSelectedId(s.id)} sx={{ borderRadius: 1, mb: 0.25 }}>
                <ListItemText
                  primary={<Stack direction="row" spacing={0.5} alignItems="center" flexWrap="wrap" useFlexGap>
                    <Typography variant="body2" noWrap sx={{ fontWeight: 600, maxWidth: 170 }}>{s.title}</Typography>
                    <Chip size="small" color={st.color} label={st.label} />
                    {s.pending_mentions > 0 && <Chip size="small" color="warning" label={`@你 ${s.pending_mentions}`} />}
                  </Stack>}
                  secondary={last ? `${last.from || ''}: ${(last.text || '').slice(0, 60)}` : '（暂无消息）'}
                  secondaryTypographyProps={{ noWrap: true }}
                />
              </ListItemButton>
            )
          })}
          {!sessions.length && (
            <Typography variant="body2" color="text.secondary" sx={{ p: 1 }}>
              还没有团队通话。开始一次打题后，团队消息会实时出现在这里。
            </Typography>
          )}
        </List>
      </Paper>

      <Paper sx={{ flex: 1, minWidth: 400, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {current ? (
          <>
            <Box sx={{ p: 1.5, pb: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>{current.title}</Typography>
                <Chip size="small" label={current.category} variant="outlined" />
                <Chip size="small" color={status.color} label={status.label} />
                <Box sx={{ flex: 1 }} />
                <Button size="small" onClick={() => navigate(`/sessions/${current.id}`)}>打开详情</Button>
              </Stack>
            </Box>
            {error && <Alert severity="error" sx={{ m: 1.5 }}>{error}</Alert>}
            <Box sx={{ flex: 1, overflow: 'auto', px: 2, py: 1.5, display: 'flex', flexDirection: 'column', gap: 1 }}>
              {messages.map((m, i) => {
                const mine = m.from === '你'
                return (
                  <Box key={i} sx={{ display: 'flex', justifyContent: mine ? 'flex-end' : 'flex-start' }}>
                    <Box sx={{
                      maxWidth: '78%', px: 1.5, py: 1, borderRadius: 2,
                      bgcolor: mine ? 'primary.dark' : 'background.paper',
                      border: mine ? 'none' : '1px solid', borderColor: 'divider',
                    }}>
                      <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mb: 0.25 }}>
                        <Typography variant="caption" sx={{ fontWeight: 600 }}>
                          {m.from || '系统'}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          → {m.to || '团队'}
                        </Typography>
                        {m.kind && KIND_LABEL[m.kind] && (
                          <Chip size="small" label={KIND_LABEL[m.kind]} variant="outlined" sx={{ height: 18 }} />
                        )}
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
              {(current.mentions || []).filter((m) => m.status === 'pending').map((m) => (
                <Alert key={m.node} severity="warning">
                  <Typography variant="subtitle2">{m.from} @ 你 · 节点 {m.node}</Typography>
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{m.text}</Typography>
                </Alert>
              ))}
              {(current.pending_approvals || []).map((a) => (
                <Alert key={a.node} severity="info"
                  action={<Button size="small" onClick={() => navigate(`/sessions/${current.id}`)}>去审批</Button>}>
                  <Typography variant="body2">{a.role} 请求审批 · 节点 {a.node}：{a.task}</Typography>
                </Alert>
              ))}
              {!messages.length && (
                <Typography color="text.secondary">等待团队消息…</Typography>
              )}
            </Box>
            <Divider />
            <Stack direction="row" spacing={1} sx={{ p: 1.5 }}>
              <TextField fullWidth size="small" value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
                placeholder={pendingMention
                  ? `回复 @${pendingMention.from}…`
                  : '给团队发消息（作为 supervisor guidance）…'}
                disabled={!current.is_running && !pendingMention} />
              <Button variant="contained" endIcon={<SendIcon />} onClick={send}
                disabled={!text.trim() || (!current.is_running && !pendingMention)}>
                发送
              </Button>
            </Stack>
          </>
        ) : (
          <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Typography color="text.secondary">选择一个会话查看团队通话</Typography>
          </Box>
        )}
      </Paper>
    </Box>
  )
}

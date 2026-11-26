import { useEffect, useState } from 'react'
import {
  Paper, Typography, Button, Stack, TextField, IconButton, Tooltip, Divider,
  Table, TableBody, TableCell, TableRow, Alert,
} from '@mui/material'
import SaveIcon from '@mui/icons-material/Save'
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep'
import DeleteIcon from '@mui/icons-material/Delete'
import AddIcon from '@mui/icons-material/Add'
import { getConfig, updateConfig, listTokens, addToken, deleteToken, clearFailed } from '../api.js'

function Section({ title, children }) {
  return (
    <Paper sx={{ p: 3, maxWidth: 760, mb: 2 }}>
      <Typography variant="h6" sx={{ mb: 2 }}>{title}</Typography>
      {children}
    </Paper>
  )
}

export default function ConfigPage() {
  const [cfg, setCfg] = useState(null)
  const [tokens, setTokens] = useState([])
  const [newToken, setNewToken] = useState('')
  const [saved, setSaved] = useState(false)
  const [form, setForm] = useState({ model: '', api_base: '', api_key: '', api_timeout: '' })

  const load = async () => {
    const c = await getConfig()
    setCfg(c)
    setTokens(c.token_hints || [])
    setForm({
      model: c.model || '',
      api_base: c.api_base || '',
      api_key: '',
      api_timeout: String(c.api_timeout ?? ''),
    })
  }
  useEffect(() => { load() }, [])

  if (!cfg) return null

  const save = async () => {
    const body = {
      model: form.model.trim(),
      api_base: form.api_base.trim(),
      api_timeout: form.api_timeout ? Number(form.api_timeout) : null,
      api_key: form.api_key.trim(),  // blank = keep the stored key
    }
    const c = await updateConfig(body)
    setCfg(c)
    setForm((f) => ({ ...f, api_key: '' }))
    setSaved(true)
    setTimeout(() => setSaved(false), 2500)
  }

  const add = async () => {
    if (!newToken.trim()) return
    const r = await addToken(newToken.trim())
    setTokens(r.tokens)
    setNewToken('')
    load()
  }

  const remove = async (index) => {
    const r = await deleteToken(index)
    setTokens(r.tokens)
    load()
  }

  const rows = [
    ['数据库', cfg.db_path],
    ['记忆池', `${cfg.memory_count} 条`],
    ['失败黑名单', `${cfg.failed_count} 道`],
  ]

  return (
    <div>
      <Section title="模型与 API">
        <Stack spacing={2}>
          <Stack direction="row" spacing={2}>
            <TextField fullWidth label="模型" value={form.model}
              onChange={(e) => setForm({ ...form, model: e.target.value })} />
            <TextField fullWidth label="API Base" value={form.api_base}
              onChange={(e) => setForm({ ...form, api_base: e.target.value })} />
          </Stack>
          <Stack direction="row" spacing={2}>
            <TextField fullWidth type="password" label="API Key"
              value={form.api_key} autoComplete="off"
              placeholder={cfg.api_key || '未设置'}
              helperText="留空表示不修改；填写则覆盖"
              onChange={(e) => setForm({ ...form, api_key: e.target.value })} />
            <TextField type="number" label="超时（秒）" value={form.api_timeout}
              onChange={(e) => setForm({ ...form, api_timeout: e.target.value })}
              sx={{ minWidth: 160 }} />
          </Stack>
          <Stack direction="row" spacing={1} alignItems="center">
            <Button variant="contained" startIcon={<SaveIcon />} onClick={save}>保存</Button>
            {saved && <Alert severity="success" sx={{ py: 0 }}>已保存，对新建任务生效</Alert>}
          </Stack>
        </Stack>
      </Section>

      <Section title="平台 Token（CTF2）">
        <Stack spacing={1}>
          {tokens.map((t) => (
            <Stack key={t.index} direction="row" spacing={1} alignItems="center">
              <Typography variant="body2" sx={{ fontFamily: 'Menlo,monospace', minWidth: 120 }}>
                #{t.index}  {t.hint}
              </Typography>
              <Tooltip title="删除">
                <IconButton size="small" color="error" onClick={() => remove(t.index)}>
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Stack>
          ))}
          {!tokens.length && (
            <Typography variant="body2" color="text.secondary">暂无 token（可回退使用 .env）</Typography>
          )}
          <Divider sx={{ my: 1 }} />
          <Stack direction="row" spacing={1}>
            <TextField size="small" fullWidth label="新增 token" value={newToken}
              autoComplete="off" onChange={(e) => setNewToken(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && add()} />
            <Button variant="outlined" startIcon={<AddIcon />} onClick={add}>添加</Button>
          </Stack>
        </Stack>
      </Section>

      <Section title="存储与清理">
        <Table size="small">
          <TableBody>
            {rows.map(([k, v]) => (
              <TableRow key={k}>
                <TableCell sx={{ color: 'text.secondary', width: 160 }}>{k}</TableCell>
                <TableCell sx={{ fontFamily: 'Menlo,monospace' }}>{v}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Button color="error" startIcon={<DeleteSweepIcon />} sx={{ mt: 2 }}
          onClick={() => clearFailed().then((r) => { alert(`清除了 ${r.cleared} 条`); load() })}>
          清空失败黑名单
        </Button>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          配置保存在本地数据库（文件权限 0600），页面保存后对新建任务生效；.env 仅作首次回退。
        </Typography>
      </Section>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { Paper, Typography, Button, Table, TableBody, TableCell, TableRow } from '@mui/material'
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep'
import { getConfig, clearFailed } from '../api.js'

export default function ConfigPage() {
  const [cfg, setCfg] = useState(null)

  const load = async () => setCfg(await getConfig())
  useEffect(() => { load() }, [])

  if (!cfg) return null
  const rows = [
    ['模型', cfg.model],
    ['API Base', cfg.api_base],
    ['API Key', cfg.api_key],
    ['API 超时', `${cfg.api_timeout}s`],
    ['Agent token', `${cfg.tokens} 个`],
    ['失败黑名单', `${cfg.failed_count} 道`],
    ['记忆池', `${cfg.memory_count} 条`],
  ]

  return (
    <Paper sx={{ p: 3, maxWidth: 640 }}>
      <Typography variant="h6" sx={{ mb: 2 }}>配置管理</Typography>
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
        配置通过 .env 修改，重启服务生效。
      </Typography>
    </Paper>
  )
}

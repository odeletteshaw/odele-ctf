import { useEffect, useState } from 'react'
import { Box, Paper, Typography, TextField, InputAdornment, IconButton, Chip, Stack } from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import { listMemories, searchMemories } from '../api.js'

export default function MemoriesPage() {
  const [mems, setMems] = useState([])
  const [q, setQ] = useState('')

  const load = async (query) => {
    setMems(query ? await searchMemories(query) : await listMemories())
  }
  useEffect(() => { load('') }, [])

  return (
    <Box>
      <TextField
        fullWidth size="small" placeholder="搜索记忆池…" value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && load(q)}
        InputProps={{ endAdornment: <InputAdornment position="end"><IconButton onClick={() => load(q)}><SearchIcon /></IconButton></InputAdornment> }}
        sx={{ mb: 2 }}
      />
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>{mems.length} 条记忆</Typography>
      {mems.map((m) => (
        <Paper key={m.id} sx={{ p: 2, mb: 1.5 }}>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
            <Typography variant="subtitle1">{m.title || '(无标题)'}</Typography>
            <Chip size="small" label={m.category} color="primary" variant="outlined" />
            <Chip size="small" label={m.source} />
          </Stack>
          <Typography variant="body2" component="pre" sx={{ whiteSpace: 'pre-wrap', m: 0, fontSize: 13 }}>
            {m.content}
          </Typography>
        </Paper>
      ))}
    </Box>
  )
}

import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { AppBar, Toolbar, Typography, Button, Box, Stack } from '@mui/material'
import SecurityIcon from '@mui/icons-material/Security'
import ForumIcon from '@mui/icons-material/Forum'
import StorageIcon from '@mui/icons-material/Storage'
import BuildIcon from '@mui/icons-material/Build'
import GroupIcon from '@mui/icons-material/Group'
import SettingsIcon from '@mui/icons-material/Settings'
import CtfPage from './pages/CtfPage.jsx'
import CallsPage from './pages/CallsPage.jsx'
import MemoriesPage from './pages/MemoriesPage.jsx'
import ManualPage from './pages/ManualPage.jsx'
import TeamPage from './pages/TeamPage.jsx'
import SessionPage from './pages/SessionPage.jsx'
import ConfigPage from './pages/ConfigPage.jsx'

const NAV = [
  { path: '/', label: 'CTF 打题', icon: <SecurityIcon /> },
  { path: '/calls', label: '通话', icon: <ForumIcon /> },
  { path: '/memories', label: '记忆池', icon: <StorageIcon /> },
  { path: '/manual', label: '手动解题', icon: <BuildIcon /> },
  { path: '/team', label: '团队与技能', icon: <GroupIcon /> },
  { path: '/config', label: '配置管理', icon: <SettingsIcon /> },
]

export default function App() {
  const location = useLocation()
  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar position="fixed" sx={{ zIndex: (t) => t.zIndex.drawer + 1 }}>
        <Toolbar sx={{ gap: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, mr: 2 }}>Odele</Typography>
          <Stack direction="row" spacing={0.5} sx={{ flexGrow: 1, overflowX: 'auto' }}>
            {NAV.map((n) => {
              const active = location.pathname === n.path
              return (
                <Button key={n.path} component={Link} to={n.path} color="inherit"
                  startIcon={n.icon}
                  sx={{
                    whiteSpace: 'nowrap', borderRadius: 0, px: 1.5,
                    opacity: active ? 1 : 0.72,
                    borderBottom: active ? '2px solid' : '2px solid transparent',
                  }}>
                  {n.label}
                </Button>
              )
            })}
          </Stack>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>v0.1.0</Typography>
        </Toolbar>
      </AppBar>
      <Box component="main" sx={{ pt: '80px', px: 3, pb: 3 }}>
        <Routes>
          <Route path="/" element={<CtfPage />} />
          <Route path="/calls" element={<CallsPage />} />
          <Route path="/memories" element={<MemoriesPage />} />
          <Route path="/manual" element={<ManualPage />} />
          <Route path="/team" element={<TeamPage />} />
          <Route path="/sessions/:id" element={<SessionPage />} />
          <Route path="/config" element={<ConfigPage />} />
        </Routes>
      </Box>
    </Box>
  )
}

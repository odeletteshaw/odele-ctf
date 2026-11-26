import { Routes, Route, Link, useLocation } from 'react-router-dom'
import {
  AppBar, Toolbar, Typography, Drawer, List, ListItemButton,
  ListItemIcon, ListItemText, Box,
} from '@mui/material'
import SecurityIcon from '@mui/icons-material/Security'
import StorageIcon from '@mui/icons-material/Storage'
import BuildIcon from '@mui/icons-material/Build'
import GroupIcon from '@mui/icons-material/Group'
import SettingsIcon from '@mui/icons-material/Settings'
import CtfPage from './pages/CtfPage.jsx'
import MemoriesPage from './pages/MemoriesPage.jsx'
import ManualPage from './pages/ManualPage.jsx'
import TeamPage from './pages/TeamPage.jsx'
import ConfigPage from './pages/ConfigPage.jsx'

const NAV = [
  { path: '/', label: 'CTF 打题', icon: <SecurityIcon /> },
  { path: '/memories', label: '通话池', icon: <StorageIcon /> },
  { path: '/manual', label: '手动解题', icon: <BuildIcon /> },
  { path: '/team', label: '团队', icon: <GroupIcon /> },
  { path: '/config', label: '配置管理', icon: <SettingsIcon /> },
]

const DRAWER_WIDTH = 220

export default function App() {
  const location = useLocation()
  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar position="fixed" sx={{ zIndex: (t) => t.zIndex.drawer + 1 }}>
        <Toolbar>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>Odele</Typography>
          <Typography variant="caption" sx={{ ml: 1, color: 'text.secondary' }}>v0.1.0</Typography>
        </Toolbar>
      </AppBar>
      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          '& .MuiDrawer-paper': { width: DRAWER_WIDTH, boxSizing: 'border-box' },
        }}
      >
        <Toolbar />
        <List>
          {NAV.map((n) => (
            <ListItemButton key={n.path} component={Link} to={n.path} selected={location.pathname === n.path}>
              <ListItemIcon>{n.icon}</ListItemIcon>
              <ListItemText primary={n.label} />
            </ListItemButton>
          ))}
        </List>
      </Drawer>
      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar />
        <Routes>
          <Route path="/" element={<CtfPage />} />
          <Route path="/memories" element={<MemoriesPage />} />
          <Route path="/manual" element={<ManualPage />} />
          <Route path="/team" element={<TeamPage />} />
          <Route path="/config" element={<ConfigPage />} />
        </Routes>
      </Box>
    </Box>
  )
}

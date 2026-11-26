import { createTheme } from '@mui/material/styles'

export default createTheme({
  palette: {
    mode: 'dark',
    background: { default: '#0f1218', paper: '#141a24' },
    primary: { main: '#4caf8f' },
    error: { main: '#ff6b6b' },
    success: { main: '#79d98a' },
    warning: { main: '#ffd166' },
    text: { primary: '#d6dae3', secondary: '#7f8a9b' },
  },
  typography: {
    fontFamily: '-apple-system, "PingFang SC", "Microsoft YaHei", sans-serif',
  },
})

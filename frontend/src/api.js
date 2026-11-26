async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts })
  if (!r.ok) {
    const j = await r.json().catch(() => ({}))
    throw new Error(j.error || j.detail || r.statusText)
  }
  return r.json()
}

export const listSessions = () => api('/api/sessions')
export const getSession = (id) => api(`/api/sessions/${id}`)
export const getStatus = () => api('/api/status')
export const getSlots = () => api('/api/autosolve/slots')

export const startAutosolve = (body) => api('/api/autosolve/start', { method: 'POST', body: JSON.stringify(body) })
export const stopAutosolve = () => api('/api/autosolve/stop', { method: 'POST' })
export const stopSession = (id) => api(`/api/sessions/${id}/stop`, { method: 'POST' })
export const deleteSession = (id) => api(`/api/sessions/${id}/delete`, { method: 'POST' })
export const retrySession = (id) => api(`/api/sessions/${id}/retry`, { method: 'POST' })
export const batchDelete = () => api('/api/sessions/batch_delete', { method: 'POST' })

export const listMemories = () => api('/api/memories')
export const searchMemories = (q) => api(`/api/memories/search?q=${encodeURIComponent(q)}`)
export const getConfig = () => api('/api/config')
export const updateConfig = (body) => api('/api/config', { method: 'PUT', body: JSON.stringify(body) })
export const listTokens = () => api('/api/tokens')
export const addToken = (token) => api('/api/tokens', { method: 'POST', body: JSON.stringify({ token }) })
export const deleteToken = (index) => api(`/api/tokens/${index}`, { method: 'DELETE' })
export const clearFailed = () => api('/api/config/clear_failed', { method: 'POST' })
export const manualSolve = (spec, title) => api('/api/manual', { method: 'POST', body: JSON.stringify({ spec, title }) })
export const getTeam = () => api('/api/team')
export const saveTeam = (members) => api('/api/team', { method: 'POST', body: JSON.stringify({ members }) })

export default api

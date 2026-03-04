const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function fetchStatus() {
  const res = await fetch(`${API_URL}/api/status`)
  if (!res.ok) throw new Error('Failed to fetch status')
  return res.json()
}

export async function fetchPortfolio() {
  const res = await fetch(`${API_URL}/api/portfolio`)
  if (!res.ok) throw new Error('Failed to fetch portfolio')
  return res.json()
}

export async function fetchTrades(limit = 50) {
  const res = await fetch(`${API_URL}/api/trades?limit=${limit}`)
  if (!res.ok) throw new Error('Failed to fetch trades')
  return res.json()
}

export async function fetchRisk() {
  const res = await fetch(`${API_URL}/api/risk`)
  if (!res.ok) throw new Error('Failed to fetch risk')
  return res.json()
}

export async function fetchLeaderboard() {
  const res = await fetch(`${API_URL}/api/leaderboard`)
  if (!res.ok) throw new Error('Failed to fetch leaderboard')
  return res.json()
}

export async function agentStart() {
  const res = await fetch(`${API_URL}/api/agent/start`, { method: 'POST' })
  return res.json()
}

export async function agentStop() {
  const res = await fetch(`${API_URL}/api/agent/stop`, { method: 'POST' })
  return res.json()
}

export async function agentResume() {
  const res = await fetch(`${API_URL}/api/agent/resume`, { method: 'POST' })
  return res.json()
}

export function createSSEConnection(onMessage: (data: any) => void): EventSource {
  const es = new EventSource(`${API_URL}/api/stream`)
  es.onmessage = (e) => {
    try { onMessage(JSON.parse(e.data)) } catch {}
  }
  return es
}

'use client'

import { useEffect, useState, useCallback } from 'react'
import StatCard from '../components/StatCard'
import SignalBadge from '../components/SignalBadge'
import { fetchStatus, fetchTrades, fetchLeaderboard, agentStart, agentStop, agentResume, createSSEConnection } from '../lib/api'

interface AgentStatus {
  running: boolean
  iteration: number
  last_cycle_at: string | null
  portfolio_value: number
  daily_pnl: number
  daily_pnl_pct: number
  drawdown_pct: number
  halted: boolean
  halt_reason: string
  trade_count_today: number
  total_trades: number
  last_signals: Record<string, any>
  last_error: string | null
  sandbox: boolean
  agent_name: string
}

interface Trade {
  timestamp: string
  from_symbol: string
  to_symbol: string
  from_amount: number
  to_amount: number
  price: number
  reason: string
  strategy: string
  tx_id: string
}

export default function Dashboard() {
  const [status, setStatus] = useState<AgentStatus | null>(null)
  const [trades, setTrades] = useState<Trade[]>([])
  const [leaderboard, setLeaderboard] = useState<any[]>([])
  const [connected, setConnected] = useState(false)
  const [loading, setLoading] = useState(true)

  const loadData = useCallback(async () => {
    try {
      const [s, t] = await Promise.all([fetchStatus(), fetchTrades(20)])
      setStatus(s)
      setTrades(t.trades || [])
      setLoading(false)
    } catch (e) {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()

    // SSE for real-time updates
    let es: EventSource | null = null
    try {
      es = createSSEConnection((data) => {
        setStatus(data)
        setConnected(true)
      })
      es.onopen = () => setConnected(true)
      es.onerror = () => setConnected(false)
    } catch {}

    // Fallback polling every 10s
    const poll = setInterval(loadData, 10000)

    // Load leaderboard less frequently
    fetchLeaderboard().then(d => setLeaderboard(d.agents || [])).catch(() => {})
    const lbPoll = setInterval(() => {
      fetchLeaderboard().then(d => setLeaderboard(d.agents || [])).catch(() => {})
    }, 60000)

    return () => {
      es?.close()
      clearInterval(poll)
      clearInterval(lbPoll)
    }
  }, [loadData])

  const handleStart = async () => { await agentStart(); loadData() }
  const handleStop = async () => { await agentStop(); loadData() }
  const handleResume = async () => { await agentResume(); loadData() }

  const pnlColor = (v: number) => v > 0 ? 'green' : v < 0 ? 'red' : 'default'
  const fmt = (n: number) => n?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  const fmtPct = (n: number) => `${n >= 0 ? '+' : ''}${n?.toFixed(2)}%`

  return (
    <div className="min-h-screen bg-[#0a0f1e] text-slate-100">
      {/* Header */}
      <header className="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-sm font-bold">R</div>
          <div>
            <h1 className="font-bold text-lg">Recall AI Trading Agent</h1>
            <p className="text-xs text-slate-400">{status?.agent_name || 'recall-ai-agent'} · {status?.sandbox ? '🟡 Sandbox' : '🟢 Live'}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-xs px-2 py-1 rounded-full border ${connected ? 'border-green-500 text-green-400' : 'border-slate-600 text-slate-500'}`}>
            {connected ? '● Live' : '○ Polling'}
          </span>
          {status?.halted && (
            <button onClick={handleResume} className="px-3 py-1.5 text-xs bg-yellow-600 hover:bg-yellow-500 rounded-lg font-medium">
              Resume
            </button>
          )}
          {status?.running ? (
            <button onClick={handleStop} className="px-3 py-1.5 text-xs bg-red-700 hover:bg-red-600 rounded-lg font-medium">
              Stop Agent
            </button>
          ) : (
            <button onClick={handleStart} className="px-3 py-1.5 text-xs bg-green-700 hover:bg-green-600 rounded-lg font-medium">
              Start Agent
            </button>
          )}
        </div>
      </header>

      <main className="px-6 py-6 max-w-7xl mx-auto space-y-6">

        {/* Alert: Halted */}
        {status?.halted && (
          <div className="bg-red-900/40 border border-red-500 rounded-xl p-4 flex items-center gap-3">
            <span className="text-red-400 text-xl">⚠️</span>
            <div>
              <p className="font-semibold text-red-300">Trading Halted</p>
              <p className="text-sm text-red-400">{status.halt_reason}</p>
            </div>
          </div>
        )}

        {/* KPI Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <StatCard
            label="Portfolio Value"
            value={status ? `$${fmt(status.portfolio_value)}` : '—'}
            color="blue"
          />
          <StatCard
            label="Daily P&L"
            value={status ? `$${fmt(status.daily_pnl)}` : '—'}
            sub={status ? fmtPct(status.daily_pnl_pct) : undefined}
            color={status ? pnlColor(status.daily_pnl) : 'default'}
          />
          <StatCard
            label="Drawdown"
            value={status ? fmtPct(-status.drawdown_pct) : '—'}
            color={status && status.drawdown_pct > 5 ? 'red' : 'default'}
          />
          <StatCard
            label="Trades Today"
            value={status?.trade_count_today ?? '—'}
            sub={`Total: ${status?.total_trades ?? 0}`}
          />
          <StatCard
            label="Iterations"
            value={status?.iteration ?? '—'}
          />
          <StatCard
            label="Status"
            value={status?.halted ? 'HALTED' : status?.running ? 'RUNNING' : 'STOPPED'}
            color={status?.halted ? 'red' : status?.running ? 'green' : 'yellow'}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Signals panel */}
          <div className="bg-slate-800/40 border border-slate-700 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">Latest Signals</h2>
            {status?.last_signals && Object.keys(status.last_signals).length > 0 ? (
              <div className="space-y-3">
                {Object.entries(status.last_signals).map(([token, sig]: [string, any]) => (
                  <div key={token} className="space-y-1">
                    <p className="text-xs text-slate-400 font-mono">{token}</p>
                    <SignalBadge
                      signal={sig.signal || 'HOLD'}
                      strategy={sig.strategy}
                      reason={sig.reason}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-slate-500 text-sm">No signals yet — agent loop pending</p>
            )}
          </div>

          {/* Recent trades */}
          <div className="lg:col-span-2 bg-slate-800/40 border border-slate-700 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">Recent Trades</h2>
            {trades.length === 0 ? (
              <p className="text-slate-500 text-sm">No trades executed yet</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-slate-400 text-xs border-b border-slate-700">
                      <th className="text-left pb-2">Time</th>
                      <th className="text-left pb-2">Pair</th>
                      <th className="text-right pb-2">Amount</th>
                      <th className="text-right pb-2">Price</th>
                      <th className="text-left pb-2">Strategy</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700/50">
                    {trades.map((t, i) => (
                      <tr key={i} className="text-slate-300 hover:bg-slate-700/30">
                        <td className="py-2 text-xs text-slate-400">
                          {new Date(t.timestamp).toLocaleTimeString()}
                        </td>
                        <td className="py-2 font-mono text-xs">
                          {t.from_symbol}→{t.to_symbol}
                        </td>
                        <td className="py-2 text-right text-xs font-mono">
                          {t.from_amount?.toFixed(4)}
                        </td>
                        <td className="py-2 text-right text-xs font-mono">
                          ${t.price?.toFixed(2)}
                        </td>
                        <td className="py-2 text-xs">
                          <span className="bg-blue-900/50 text-blue-300 px-1.5 py-0.5 rounded text-xs">
                            {t.strategy || 'manual'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Leaderboard */}
        {leaderboard.length > 0 && (
          <div className="bg-slate-800/40 border border-slate-700 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">🏆 Competition Leaderboard</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-slate-400 text-xs border-b border-slate-700">
                    <th className="text-left pb-2">Rank</th>
                    <th className="text-left pb-2">Agent</th>
                    <th className="text-right pb-2">Portfolio Value</th>
                    <th className="text-right pb-2">P&L</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/50">
                  {leaderboard.slice(0, 10).map((a: any, i: number) => (
                    <tr key={i} className={`text-slate-300 hover:bg-slate-700/30 ${a.isOurs ? 'bg-blue-900/20' : ''}`}>
                      <td className="py-2 font-bold text-slate-400">#{i + 1}</td>
                      <td className="py-2 text-xs font-mono">{a.agentName || a.agentId?.slice(0, 12) + '...'}</td>
                      <td className="py-2 text-right font-mono">${fmt(a.portfolioValue)}</td>
                      <td className={`py-2 text-right font-mono ${a.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {a.pnl >= 0 ? '+' : ''}{fmt(a.pnl)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Error */}
        {status?.last_error && (
          <div className="bg-red-900/20 border border-red-800 rounded-xl p-4">
            <p className="text-xs text-red-400 font-mono">{status.last_error}</p>
          </div>
        )}

        <footer className="text-center text-slate-600 text-xs pt-4 pb-8">
          Recall AI Trading Agent · Multi-strategy (Momentum + Mean Reversion + Sentiment) ·{' '}
          <a href="https://recall.network" className="text-slate-500 hover:text-slate-400" target="_blank" rel="noopener noreferrer">
            recall.network
          </a>
        </footer>
      </main>
    </div>
  )
}

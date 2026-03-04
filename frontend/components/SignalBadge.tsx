interface SignalBadgeProps {
  signal: string
  strategy?: string
  reason?: string
}

export default function SignalBadge({ signal, strategy, reason }: SignalBadgeProps) {
  const colors: Record<string, string> = {
    BUY: 'bg-green-900/60 border-green-500 text-green-300',
    SELL: 'bg-red-900/60 border-red-500 text-red-300',
    HOLD: 'bg-slate-800 border-slate-600 text-slate-400',
  }
  const cls = colors[signal] || colors.HOLD
  return (
    <div className={`border rounded-lg p-3 ${cls}`}>
      <div className="flex items-center gap-2">
        <span className="font-bold text-lg">{signal}</span>
        {strategy && <span className="text-xs opacity-70 bg-black/30 px-2 py-0.5 rounded">{strategy}</span>}
      </div>
      {reason && <p className="text-xs mt-1 opacity-80">{reason}</p>}
    </div>
  )
}

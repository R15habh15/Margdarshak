import { TrendingDown, TrendingUp, Minus } from 'lucide-react'

function DeltaBadge({ value, lowerIsBetter = true }) {
  if (value === undefined || value === null) return null
  const improved = lowerIsBetter ? value < 0 : value > 0
  const neutral  = Math.abs(value) < 0.5

  return (
    <span className={`flex items-center gap-1 text-xs font-mono font-medium
      ${neutral ? 'text-muted' : improved ? 'text-success' : 'text-danger'}`}>
      {neutral
        ? <Minus size={12} />
        : improved ? <TrendingDown size={12} /> : <TrendingUp size={12} />
      }
      {value > 0 ? '+' : ''}{value?.toFixed(1)}%
    </span>
  )
}

function CompareRow({ label, staticVal, aiVal, unit, lowerIsBetter }) {
  const delta = staticVal && aiVal
    ? ((aiVal - staticVal) / Math.abs(staticVal)) * 100
    : null

  return (
    <div className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-3 py-2 border-b border-border last:border-0">
      <span className="text-xs text-muted font-mono">{label}</span>
      <span className="font-mono text-xs text-white text-right">
        {staticVal?.toLocaleString() ?? '—'} <span className="text-muted">{unit}</span>
      </span>
      <span className="font-mono text-xs text-accent text-right">
        {aiVal?.toLocaleString() ?? '—'} <span className="text-muted">{unit}</span>
      </span>
      <DeltaBadge value={delta} lowerIsBetter={lowerIsBetter} />
    </div>
  )
}

export default function PerformanceComparison({ comparison }) {
  if (!comparison?.ready) {
    return (
      <div className="panel p-5 flex flex-col gap-3">
        <h3 className="font-display text-sm font-bold uppercase tracking-widest text-white">
          Performance Comparison
        </h3>
        <p className="text-muted text-xs font-mono leading-relaxed">
          Run the simulation in <span className="text-white">Static</span> mode,
          click <span className="text-white">Save Run</span>, then run in{' '}
          <span className="text-accent">AI</span> mode and save again.
        </p>
        <div className="grid grid-cols-2 gap-2 mt-1">
          {['Static', 'AI'].map(m => (
            <div key={m} className={`panel p-3 border ${m === 'AI' ? 'border-accent/30' : 'border-border'}`}>
              <p className={`font-display text-xs font-bold uppercase tracking-wider ${m === 'AI' ? 'text-accent' : 'text-muted'}`}>
                {m} Mode
              </p>
              <p className="font-mono text-[10px] text-muted mt-1">
                {comparison?.[m.toLowerCase()] ? '✓ Saved' : 'Not yet run'}
              </p>
            </div>
          ))}
        </div>
      </div>
    )
  }

  const { static: s, ai, improvement } = comparison

  return (
    <div className="panel p-4 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-sm font-bold uppercase tracking-widest text-white">
          Performance Comparison
        </h3>
        <span className="badge badge-ai">Results Ready</span>
      </div>

      {/* Column headers */}
      <div className="grid grid-cols-[1fr_auto_auto_auto] gap-3 pb-1 border-b border-border">
        <span className="text-[10px] font-mono text-muted uppercase">Metric</span>
        <span className="text-[10px] font-mono text-muted uppercase">Static</span>
        <span className="text-[10px] font-mono text-accent uppercase">AI</span>
        <span className="text-[10px] font-mono text-muted uppercase">Delta</span>
      </div>

      <div className="flex flex-col">
        <CompareRow label="Total Wait Time"  staticVal={s.total_waiting_time} aiVal={ai.total_waiting_time} unit="s"  lowerIsBetter={true}  />
        <CompareRow label="Vehicles Arrived" staticVal={s.total_arrived}      aiVal={ai.total_arrived}      unit=""   lowerIsBetter={false} />
        <CompareRow label="Total Departed"   staticVal={s.total_departed}     aiVal={ai.total_departed}     unit=""   lowerIsBetter={false} />
        <CompareRow label="Steps Run"        staticVal={s.total_steps}        aiVal={ai.total_steps}        unit=""   lowerIsBetter={false} />
      </div>

      {/* Summary callout */}
      <div className={`rounded-lg p-3 border ${
        improvement.waiting_reduced ? 'bg-success/8 border-success/25' : 'bg-danger/8 border-danger/25'
      }`}>
        <p className="font-display text-xs font-bold uppercase tracking-wider text-white mb-1">
          Summary
        </p>
        <p className="font-mono text-[11px] text-muted leading-relaxed">
          {improvement.waiting_reduced
            ? `AI reduced wait time by ${Math.abs(improvement.waiting_time_change_pct).toFixed(1)}%`
            : `AI increased wait time by ${Math.abs(improvement.waiting_time_change_pct).toFixed(1)}%`
          }
          {' · '}
          {improvement.throughput_increased
            ? `throughput improved by ${improvement.throughput_change_pct.toFixed(1)}%`
            : `throughput changed by ${improvement.throughput_change_pct.toFixed(1)}%`
          }
        </p>
      </div>
    </div>
  )
}

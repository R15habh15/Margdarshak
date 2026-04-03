export default function MetricCard({ label, value, unit, delta, color = 'accent', icon: Icon }) {
  const colorMap = {
    accent:  { text: 'text-accent',   bg: 'bg-accent/10',   border: 'border-accent/20'   },
    success: { text: 'text-success',  bg: 'bg-success/10',  border: 'border-success/20'  },
    warning: { text: 'text-warning',  bg: 'bg-warning/10',  border: 'border-warning/20'  },
    danger:  { text: 'text-danger',   bg: 'bg-danger/10',   border: 'border-danger/20'   },
    muted:   { text: 'text-muted',    bg: 'bg-muted/10',    border: 'border-muted/20'    },
  }
  const c = colorMap[color] || colorMap.accent

  return (
    <div className={`panel p-3 flex flex-col gap-2 ${c.border} border fade-in`}>
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono text-muted uppercase tracking-wider">{label}</span>
        {Icon && <Icon size={13} className={c.text} />}
      </div>
      <div className="flex items-end gap-1.5">
        <span className={`font-display text-2xl font-bold ${c.text}`}>
          {value ?? '—'}
        </span>
        {unit && <span className="font-mono text-[11px] text-muted mb-0.5">{unit}</span>}
      </div>
      {delta !== undefined && (
        <span className={`text-[10px] font-mono ${delta < 0 ? 'text-success' : 'text-danger'}`}>
          {delta > 0 ? '▲' : '▼'} {Math.abs(delta).toFixed(1)}% vs baseline
        </span>
      )}
    </div>
  )
}

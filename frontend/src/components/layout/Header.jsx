import { Activity, Cpu, Radio } from 'lucide-react'

export default function Header({ simStatus, streamActive }) {
  const isRunning = simStatus?.running
  const mode      = simStatus?.mode
  const step      = simStatus?.step ?? 0
  const simTime   = simStatus?.sim_time ?? 0

  const formatTime = (s) => {
    const m = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`
  }

  return (
    <header className="flex items-center justify-between px-5 py-3 border-b border-border bg-panel">
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-accent/10 border border-accent/30 flex items-center justify-center">
          <Activity size={16} className="text-accent" />
        </div>
        <div>
          <h1 className="font-display text-lg font-bold tracking-widest text-white uppercase">
            Margadarshak
          </h1>
          <p className="text-[10px] text-muted font-mono tracking-wider uppercase">
            AI Traffic Control System
          </p>
        </div>
      </div>

      {/* Status indicators */}
      <div className="flex items-center gap-6">
        {/* Stream indicator */}
        <div className="flex items-center gap-2">
          <Radio size={13} className={streamActive ? 'text-success' : 'text-muted'} />
          <span className="font-mono text-[11px] text-muted uppercase tracking-wider">
            {streamActive ? 'Live' : 'Offline'}
          </span>
          {streamActive && (
            <span className="w-1.5 h-1.5 rounded-full bg-success pulse-dot" />
          )}
        </div>

        {/* Sim time */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded border border-border bg-surface">
          <Cpu size={12} className="text-muted" />
          <span className="font-mono text-[11px] text-muted">T</span>
          <span className="font-mono text-[11px] text-white">{formatTime(simTime)}</span>
        </div>

        {/* Step counter */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded border border-border bg-surface">
          <span className="font-mono text-[11px] text-muted">STEP</span>
          <span className="font-mono text-[11px] text-accent">{step.toLocaleString()}</span>
        </div>

        {/* Mode badge */}
        <span className={`badge ${
          !isRunning  ? 'badge-idle'
          : mode === 'ai' ? 'badge-ai'
          : 'badge-static'
        }`}>
          <span className="w-1.5 h-1.5 rounded-full bg-current" />
          {!isRunning ? 'Idle' : mode === 'ai' ? 'AI Mode' : 'Static Mode'}
        </span>
      </div>
    </header>
  )
}

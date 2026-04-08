/**
 * PerformanceComparison.jsx
 * Full 3-mode comparison panel: Static vs Backpressure vs AI
 *
 * Workflow displayed:
 *  Step 1 → Run Static → "Save Run" → shows ✓
 *  Step 2 → Run Backpressure → "Save Run" → shows ✓
 *  Step 3 → Run AI → "Save Run" → shows ✓
 *  Then: full comparison table with delta badges + winner callout
 */

import { TrendingDown, TrendingUp, Minus, Trophy, AlertCircle } from 'lucide-react'

// ── Delta badge (green = improved, red = worse) ──────────────────
function DeltaBadge({ value, lowerIsBetter = true }) {
  if (value == null || isNaN(value)) return <span className="text-muted font-mono text-xs">—</span>
  const improved = lowerIsBetter ? value < 0 : value > 0
  const neutral  = Math.abs(value) < 0.5
  return (
    <span className={`flex items-center gap-0.5 text-xs font-mono font-semibold
      ${neutral ? 'text-muted' : improved ? 'text-emerald-400' : 'text-red-400'}`}>
      {neutral ? <Minus size={11}/> : improved ? <TrendingDown size={11}/> : <TrendingUp size={11}/>}
      {value > 0 ? '+' : ''}{value.toFixed(1)}%
    </span>
  )
}

function pct(base, val) {
  if (!base || base === 0) return null
  return ((val - base) / Math.abs(base)) * 100
}

function fmt(v, unit = '') {
  if (v == null) return '—'
  const n = typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 1 }) : v
  return unit ? `${n} ${unit}` : n
}

// ── Mode status card ─────────────────────────────────────────────
function ModeCard({ label, color, data, saved }) {
  const colorMap = {
    muted:   { border: 'border-white/10',   text: 'text-white/60',  dot: 'bg-white/30'    },
    yellow:  { border: 'border-yellow-400/40', text: 'text-yellow-300', dot: 'bg-yellow-400' },
    cyan:    { border: 'border-cyan-400/40',   text: 'text-cyan-300',   dot: 'bg-cyan-400'   },
  }
  const c = colorMap[color] || colorMap.muted

  return (
    <div className={`flex-1 rounded-xl border p-3 bg-white/[0.03] ${c.border}`}>
      <div className="flex items-center gap-1.5 mb-2">
        <div className={`w-2 h-2 rounded-full ${c.dot} ${saved ? 'animate-none' : 'opacity-30'}`}/>
        <span className={`font-display text-[11px] font-bold uppercase tracking-wider ${c.text}`}>{label}</span>
        {saved && <span className="ml-auto text-emerald-400 text-[10px] font-mono">✓ Saved</span>}
      </div>
      {saved && data ? (
        <div className="space-y-0.5">
          <p className="font-mono text-[10px] text-white/50">Wait: <span className="text-white/80">{fmt(data.total_waiting_time, 's')}</span></p>
          <p className="font-mono text-[10px] text-white/50">Arrived: <span className="text-white/80">{fmt(data.total_arrived)}</span></p>
        </div>
      ) : (
        <p className="font-mono text-[10px] text-white/30 italic">Run & save to compare</p>
      )}
    </div>
  )
}

// ── Metric row in comparison table ───────────────────────────────
function MetricRow({ label, unit, lowerIsBetter, staticVal, bpVal, aiVal }) {
  const deltaAI = pct(staticVal, aiVal)
  const deltaBP = pct(staticVal, bpVal)
  const winner  = (() => {
    const vals = [
      { k: 'static', v: staticVal },
      { k: 'bp',     v: bpVal },
      { k: 'ai',     v: aiVal },
    ].filter(x => x.v != null)
    if (!vals.length) return null
    return lowerIsBetter
      ? vals.reduce((a, b) => a.v < b.v ? a : b).k
      : vals.reduce((a, b) => a.v > b.v ? a : b).k
  })()

  const cell = (val, key) => (
    <span className={`font-mono text-xs text-right ${winner === key ? 'text-emerald-400 font-bold' : 'text-white/70'}`}>
      {fmt(val, unit)}
      {winner === key && <span className="ml-1 text-[9px]">👑</span>}
    </span>
  )

  return (
    <div className="grid grid-cols-5 items-center gap-2 py-2 border-b border-white/5 last:border-0">
      <span className="col-span-1 font-mono text-[10px] text-white/40 leading-tight">{label}</span>
      {cell(staticVal, 'static')}
      {cell(bpVal,     'bp')}
      {cell(aiVal,     'ai')}
      <div className="flex flex-col gap-0.5 items-end">
        {bpVal != null && <DeltaBadge value={deltaBP} lowerIsBetter={lowerIsBetter}/>}
        {aiVal  != null && <DeltaBadge value={deltaAI} lowerIsBetter={lowerIsBetter}/>}
      </div>
    </div>
  )
}

// ── Main export ──────────────────────────────────────────────────
export default function PerformanceComparison({ comparison, onSaveComparison, simStatus }) {
  const s = comparison?.static
  const b = comparison?.backpressure
  const a = comparison?.ai

  const isRunning = simStatus?.running
  const currentMode = String(simStatus?.mode || '').toLowerCase()

  // Determine best mode for summary
  const bestMode = (() => {
    const opts = [
      { k: 'Static',      v: s?.total_waiting_time },
      { k: 'Backpressure',v: b?.total_waiting_time },
      { k: 'AI',          v: a?.total_waiting_time },
    ].filter(x => x.v != null)
    if (!opts.length) return null
    return opts.reduce((a, b) => a.v < b.v ? a : b).k
  })()

  const aiImprovement = s && a
    ? Math.abs(pct(s.total_waiting_time, a.total_waiting_time) ?? 0).toFixed(1)
    : null

  return (
    <div className="panel p-4 flex flex-col gap-4">

      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-display text-sm font-bold uppercase tracking-widest text-white flex items-center gap-2">
          <Trophy size={15} className="text-yellow-400"/>
          Mode Comparison
        </h3>
        {bestMode && (
          <span className="text-[10px] font-mono text-emerald-400 bg-emerald-400/10 border border-emerald-400/25 rounded px-2 py-0.5">
            🏆 {bestMode} wins
          </span>
        )}
      </div>

      {/* Workflow guide */}
      <div className="bg-white/[0.03] rounded-xl border border-white/10 p-3">
        <p className="font-mono text-[10px] text-white/40 mb-2 uppercase tracking-wider">How to compare</p>
        <ol className="space-y-1.5">
          {['Run Static mode → click Save Run', 'Run Backpressure mode → click Save Run', 'Run AI mode → click Save Run'].map((step, i) => (
            <li key={i} className="flex items-start gap-2 font-mono text-[10px] text-white/50">
              <span className={`shrink-0 w-4 h-4 rounded-full text-center text-[9px] leading-4 font-bold
                ${i === 0 && s ? 'bg-emerald-500/30 text-emerald-300' :
                  i === 1 && b ? 'bg-emerald-500/30 text-emerald-300' :
                  i === 2 && a ? 'bg-cyan-500/30 text-cyan-300' :
                  'bg-white/10 text-white/30'}`}>{i + 1}</span>
              {step}
            </li>
          ))}
        </ol>
      </div>

      {/* Save button (context-aware) */}
      {isRunning && (
        <button
          onClick={onSaveComparison}
          className={`btn w-full text-xs font-bold uppercase tracking-wider
            ${currentMode === 'ai'
              ? 'btn-primary border-cyan-400/40 text-cyan-300'
              : 'btn-ghost border-white/20 text-white/60 hover:text-white'}`}
        >
          💾 Save {currentMode === 'static' ? 'Static' : currentMode === 'ai' ? 'AI' : 'Backpressure'} Run
        </button>
      )}

      {/* Mode status cards */}
      <div className="flex gap-2">
        <ModeCard label="Static"       color="muted"   data={s} saved={!!s} />
        <ModeCard label="Backpressure" color="yellow"  data={b} saved={!!b} />
        <ModeCard label="AI"           color="cyan"    data={a} saved={!!a} />
      </div>

      {/* Full comparison table — only shown when at least 2 modes saved */}
      {(s || b || a) && (
        <>
          {/* Column headers */}
          <div className="grid grid-cols-5 gap-2 pb-1 border-b border-white/10">
            <span className="col-span-1 font-mono text-[9px] text-white/30 uppercase">Metric</span>
            <span className="font-mono text-[9px] text-white/40 uppercase text-right">Static</span>
            <span className="font-mono text-[9px] text-yellow-400/70 uppercase text-right">BP</span>
            <span className="font-mono text-[9px] text-cyan-400/70 uppercase text-right">AI</span>
            <span className="font-mono text-[9px] text-white/30 uppercase text-right">Δ vs Static</span>
          </div>

          <div className="flex flex-col">
            <MetricRow
              label="Wait Time" unit="s" lowerIsBetter={true}
              staticVal={s?.total_waiting_time} bpVal={b?.total_waiting_time} aiVal={a?.total_waiting_time}
            />
            <MetricRow
              label="Arrived" unit="" lowerIsBetter={false}
              staticVal={s?.total_arrived} bpVal={b?.total_arrived} aiVal={a?.total_arrived}
            />
            <MetricRow
              label="Departed" unit="" lowerIsBetter={false}
              staticVal={s?.total_departed} bpVal={b?.total_departed} aiVal={a?.total_departed}
            />
            <MetricRow
              label="Steps" unit="" lowerIsBetter={false}
              staticVal={s?.total_steps} bpVal={b?.total_steps} aiVal={a?.total_steps}
            />
          </div>

          {/* Summary callout */}
          {aiImprovement && (
            <div className={`rounded-xl p-3 border ${
              parseFloat(aiImprovement) > 0 && a?.total_waiting_time < (s?.total_waiting_time ?? Infinity)
                ? 'bg-emerald-500/8 border-emerald-500/25'
                : 'bg-red-500/8 border-red-500/25'
            }`}>
              <p className="font-display text-[11px] font-bold text-white mb-1 uppercase tracking-wider">
                AI vs Static
              </p>
              <p className="font-mono text-[11px] text-white/60 leading-relaxed">
                {a && s
                  ? a.total_waiting_time <= s.total_waiting_time
                    ? `🟢 AI reduced wait time by ${aiImprovement}%`
                    : `🔴 AI increased wait time by ${aiImprovement}%`
                  : 'Run both modes to see improvement.'
                }
              </p>
            </div>
          )}
        </>
      )}

      {!s && !b && !a && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-white/[0.02] border border-white/10">
          <AlertCircle size={14} className="text-white/30 shrink-0"/>
          <p className="font-mono text-[10px] text-white/30">
            No runs saved yet. Start a simulation, let it run, then click Save Run.
          </p>
        </div>
      )}
    </div>
  )
}

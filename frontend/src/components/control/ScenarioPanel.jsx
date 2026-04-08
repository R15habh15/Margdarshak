/**
 * ScenarioPanel.jsx
 * Interactive Scenario Builder — lets users inject chaos into the simulation
 * and watch the AI (or static mode) respond.
 *
 * Scenarios:
 *  1. 🚨 Emergency Vehicle — spawns a priority vehicle with green-wave preemption
 *  2. 🌊 Rush Hour Surge   — injects extra vehicles to simulate peak traffic
 *  3. 🚧 Road Closure      — blocks a lane segment (simulates accident / construction)
 *  4. 🌧️  Rain / Wet Road   — slows all vehicles to 60% speed
 *  5. ✅ Clear All          — restores normal conditions
 */

import { useState, useCallback } from 'react'
import { scenarioApi } from '../../services/api'
import {
  Siren, Waves, Construction, CloudRain,
  RotateCcw, Loader2, CheckCircle, AlertCircle,
} from 'lucide-react'

// ── Individual scenario card ──────────────────────────────────────────
function ScenarioCard({ icon: Icon, label, description, color, onClick, loading, active, disabled }) {
  const colorMap = {
    red:    { bg: 'bg-red-500/10',    border: 'border-red-500/40',    text: 'text-red-400',    glow: 'shadow-[0_0_20px_rgba(239,68,68,0.25)]' },
    orange: { bg: 'bg-orange-500/10', border: 'border-orange-500/40', text: 'text-orange-400', glow: 'shadow-[0_0_20px_rgba(249,115,22,0.25)]' },
    yellow: { bg: 'bg-yellow-500/10', border: 'border-yellow-500/40', text: 'text-yellow-400', glow: 'shadow-[0_0_20px_rgba(234,179,8,0.25)]'  },
    blue:   { bg: 'bg-blue-500/10',   border: 'border-blue-500/40',   text: 'text-blue-400',   glow: 'shadow-[0_0_20px_rgba(59,130,246,0.25)]' },
  }
  const c = colorMap[color] || colorMap.red

  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`
        relative w-full flex items-start gap-3 p-3 rounded-xl border transition-all duration-200 text-left
        ${active
          ? `${c.bg} ${c.border} ${c.glow}`
          : 'bg-surface/60 border-border hover:border-muted/50 hover:bg-white/5'
        }
        disabled:opacity-40 disabled:cursor-not-allowed
      `}
    >
      {/* Icon */}
      <div className={`mt-0.5 shrink-0 ${active ? c.text : 'text-muted'} transition-colors`}>
        {loading
          ? <Loader2 size={18} className="animate-spin" />
          : <Icon size={18} />
        }
      </div>

      {/* Text */}
      <div className="flex-1 min-w-0">
        <p className={`font-display text-xs font-bold uppercase tracking-wider ${active ? c.text : 'text-white/80'}`}>
          {label}
        </p>
        <p className="font-mono text-[10px] text-muted leading-relaxed mt-0.5">
          {description}
        </p>
      </div>

      {/* Active dot */}
      {active && (
        <span className={`absolute top-2 right-2 w-2 h-2 rounded-full ${c.text.replace('text-', 'bg-')} animate-pulse`} />
      )}
    </button>
  )
}

// ── Toast-style feedback line ─────────────────────────────────────────
function FeedbackLine({ msg, type }) {
  if (!msg) return null
  const isErr = type === 'error'
  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-mono
      ${isErr
        ? 'bg-red-500/10 border-red-500/30 text-red-400'
        : 'bg-green-500/10 border-green-500/30 text-green-400'
      }`}
    >
      {isErr
        ? <AlertCircle size={12} className="shrink-0" />
        : <CheckCircle size={12} className="shrink-0" />
      }
      <span className="truncate">{msg}</span>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────
export default function ScenarioPanel({ simRunning }) {
  const [loading,  setLoading]  = useState(null)   // which scenario is loading
  const [feedback, setFeedback] = useState(null)   // { msg, type }

  // Active flags returned from backend (kept locally for instant UI)
  const [active, setActive] = useState({
    emergency: false,
    rush_hour: false,
    road_closure: false,
    rain: false,
  })

  const toast = (msg, type = 'success') => {
    setFeedback({ msg, type })
    setTimeout(() => setFeedback(null), 4000)
  }

  const run = useCallback(async (key, apiFn, label) => {
    if (loading || !simRunning) return
    setLoading(key)
    try {
      const res = await apiFn()
      setActive(prev => ({ ...prev, [key]: true }))
      const detail = res?.vehicle_id
        ? `Vehicle ${res.vehicle_id} spawned`
        : res?.injected
        ? `${res.injected} vehicles injected`
        : res?.edge_id
        ? `Edge ${res.edge_id} closed`
        : res?.vehicles_affected !== undefined
        ? `${res.vehicles_affected} vehicles slowed`
        : 'Activated'
      toast(`${label}: ${detail}`)
    } catch (e) {
      toast(e.message || `${label} failed`, 'error')
    } finally {
      setLoading(null)
    }
  }, [loading, simRunning])

  const handleClear = useCallback(async () => {
    if (loading || !simRunning) return
    setLoading('clear')
    try {
      await scenarioApi.clearAll()
      setActive({ emergency: false, rush_hour: false, road_closure: false, rain: false })
      toast('All scenarios cleared — normal conditions restored')
    } catch (e) {
      toast(e.message || 'Clear failed', 'error')
    } finally {
      setLoading(null)
    }
  }, [loading, simRunning])

  const anyActive = Object.values(active).some(Boolean)

  return (
    <div className="panel p-4 flex flex-col gap-3">

      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="font-display text-sm font-bold uppercase tracking-widest text-white">
          ⚡ Scenario Builder
        </h2>
        {anyActive && (
          <span className="text-[9px] font-mono text-yellow-400 animate-pulse uppercase tracking-wider">
            ACTIVE
          </span>
        )}
      </div>

      {!simRunning && (
        <p className="font-mono text-[10px] text-muted text-center py-2 px-1 rounded-lg bg-white/5 border border-border">
          Start a simulation first to use scenarios
        </p>
      )}

      {/* Scenario cards */}
      <div className="flex flex-col gap-2">

        <ScenarioCard
          icon={Siren}
          label="Emergency Vehicle"
          description="Spawns an ambulance with green-wave signal preemption along its path."
          color="red"
          active={active.emergency}
          loading={loading === 'emergency'}
          disabled={!simRunning}
          onClick={() => run('emergency', () => scenarioApi.spawnEmergency(), '🚨 Emergency')}
        />

        <ScenarioCard
          icon={Waves}
          label="Rush Hour Surge"
          description="Injects 50 extra vehicles — watch the AI handle congestion spikes."
          color="orange"
          active={active.rush_hour}
          loading={loading === 'rush_hour'}
          disabled={!simRunning}
          onClick={() => run('rush_hour', () => scenarioApi.rushHour(50), '🌊 Rush Hour')}
        />

        <ScenarioCard
          icon={Construction}
          label="Road Closure"
          description="Blocks a lane segment to ~0 speed, forcing rerouting."
          color="yellow"
          active={active.road_closure}
          loading={loading === 'road_closure'}
          disabled={!simRunning}
          onClick={() => run('road_closure', () => scenarioApi.roadClosure(null), '🚧 Road Closure')}
        />

        <ScenarioCard
          icon={CloudRain}
          label="Rain / Wet Roads"
          description="Reduces all vehicle speeds to 60%, simulating adverse weather."
          color="blue"
          active={active.rain}
          loading={loading === 'rain'}
          disabled={!simRunning}
          onClick={() => run('rain', () => scenarioApi.rain(0.6), '🌧️ Rain')}
        />

      </div>

      {/* Feedback */}
      <FeedbackLine msg={feedback?.msg} type={feedback?.type} />

      {/* Clear button */}
      {anyActive && (
        <button
          onClick={handleClear}
          disabled={!!loading || !simRunning}
          className="btn btn-ghost w-full text-xs mt-1 border-border"
        >
          {loading === 'clear'
            ? <Loader2 size={12} className="animate-spin" />
            : <RotateCcw size={12} />
          }
          Clear All Scenarios
        </button>
      )}
    </div>
  )
}

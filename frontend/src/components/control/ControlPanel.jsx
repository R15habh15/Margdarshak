import { useState } from 'react'
import {
  Play, Square, RotateCcw, Download, RefreshCw,
  Zap, Clock, GitCompare, ChevronDown, ChevronUp, Loader2
} from 'lucide-react'
import { mapApi, simulationApi } from '../../services/api'

export default function ControlPanel({
  simStatus, isLoading,
  onStart, onStop, onReset, onSwitchMode, onSaveComparison,
  onMapImported,
}) {
  const [placeName, setPlaceName]   = useState('')
  const [configFile, setConfigFile] = useState('')
  const [mode, setMode]             = useState('static')
  const [pipelineStep, setPipelineStep] = useState(null)
  const [pipelineMsg, setPipelineMsg]   = useState('')
  const [expanded, setExpanded]     = useState(true)
  const [simSpeed, setSimSpeed]     = useState(5)

  const isRunning = simStatus?.running

  // ── OSM full pipeline ──
  const handleImport = async () => {
  if (!placeName.trim()) return

  try {
    setPipelineStep('downloading')
    setPipelineMsg('Downloading OSM map, converting, and generating routes… (this may take 1–2 minutes)')

    // The backend /api/map/download/place already runs the FULL pipeline:
    // OSM download → netconvert → route generation in one call.
    // It returns { osm_file, network_file, config, ... }
    const result = await mapApi.downloadByPlace(placeName)

    // Notify parent about new coordinates
    if (onMapImported) onMapImported(result)

    // Extract the config filename from the backend response.
    // Backend returns both `config` (full path) and `config_file` (basename only).
    const cfg = result?.config_file
      || (result?.config ? result.config.split(/[/\\]/).pop() : null)
      || (result?.network_file ? result.network_file.replace('.net.xml', '.sumocfg') : null)


    if (!cfg) {
      throw new Error('Backend did not return a config filename. Check server logs.')
    }

    setConfigFile(cfg)

    setPipelineStep('done')
    setPipelineMsg(`✅ Ready: ${cfg}. Launching simulation…`)

    // Auto-start simulation
    onStart(cfg, mode)

  } catch (e) {
    setPipelineStep('error')
    setPipelineMsg(`Error: ${e.message}`)
  }
}

  const handleRandomize = async () => {
    if (!configFile) return
    try {
      setPipelineStep('routes')
      setPipelineMsg('Re-randomizing traffic flows...')
      const netFile = configFile.replace('.sumocfg', '.net.xml')
      const numVehicles = Math.floor(Math.random() * 400) + 100 // 100-500 vehicles
      await mapApi.generateRoutes(netFile, { numVehicles })
      setPipelineStep('done')
      setPipelineMsg(`Traffic randomized! (${numVehicles} vehicles)`)
    } catch (e) {
      setPipelineStep('error')
      setPipelineMsg(`Randomization failed: ${e.message}`)
    }
  }

  const handleStart = () => {
    if (!configFile) return
    onStart(configFile, mode)
  }

  const handleSpeed = async (speed) => {
    try {
      await simulationApi.setSpeed(speed)
      setSimSpeed(speed)
    } catch (e) {
      console.error('Failed to set speed:', e)
    }
  }

  return (
    <div className="panel p-4 flex flex-col gap-4">

      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="font-display text-sm font-bold uppercase tracking-widest text-white">
          Control Panel
        </h2>
        <button onClick={() => setExpanded(e => !e)} className="text-muted hover:text-white">
          {expanded ? <ChevronUp size={14}/> : <ChevronDown size={14}/>}
        </button>
      </div>

      {expanded && <>
        {/* Map Import */}
        <div className="flex flex-col gap-2">
          <label className="text-[10px] font-mono text-muted uppercase tracking-wider">
            Import Map
          </label>
          <div className="flex gap-2">
            <input
              value={placeName}
              onChange={e => setPlaceName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleImport()}
              placeholder="e.g. Connaught Place, Delhi"
              className="flex-1 bg-surface border border-border rounded px-3 py-2 text-xs text-white placeholder-muted/50 focus:outline-none focus:border-accent/50"
            />
            <button
              onClick={handleImport}
              disabled={!placeName || !!pipelineStep && pipelineStep !== 'done' && pipelineStep !== 'error'}
              className="btn btn-primary"
            >
              {pipelineStep && pipelineStep !== 'done' && pipelineStep !== 'error'
                ? <Loader2 size={13} className="animate-spin" />
                : <Download size={13} />
              }
            </button>
            <button
              onClick={handleRandomize}
              disabled={!configFile || (!!pipelineStep && pipelineStep !== 'done')}
              className="btn btn-ghost px-2 border-border"
              title="Randomize Traffic"
            >
              <RefreshCw size={13} className={pipelineStep === 'routes' ? 'animate-spin' : ''}/>
            </button>
          </div>

          {/* Pipeline status */}
          {pipelineMsg && (
            <p className={`text-[11px] font-mono px-2 py-1 rounded border
              ${pipelineStep === 'error' ? 'bg-danger/10 border-danger/30 text-danger'
              : pipelineStep === 'done'  ? 'bg-success/10 border-success/30 text-success'
              : 'bg-accent/10 border-accent/30 text-accent'}`}>
              {pipelineMsg}
            </p>
          )}
        </div>

        {/* Config file */}
        <div className="flex flex-col gap-2">
          <label className="text-[10px] font-mono text-muted uppercase tracking-wider">
            Config File
          </label>
          <input
            value={configFile}
            onChange={e => setConfigFile(e.target.value)}
            placeholder="e.g. delhi.sumocfg"
            className="bg-surface border border-border rounded px-3 py-2 text-xs text-white placeholder-muted/50 focus:outline-none focus:border-accent/50"
          />
        </div>

        {/* Mode selector */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <label className="text-[10px] font-mono text-muted uppercase tracking-wider">
              Signal Mode
            </label>
            {mode === 'ai' && (
               <span className="text-[9px] font-mono text-accent animate-pulse">● AI OPTIMIZED</span>
            )}
          </div>
          <div className="grid grid-cols-3 gap-1.5">
            {['static','ai','backpressure'].map(m => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`py-1.5 rounded text-[11px] font-display font-semibold uppercase tracking-wider border transition-all flex items-center justify-center gap-1.5
                  ${mode === m
                    ? m === 'ai' ? 'bg-accent/15 text-accent border-accent/40'
                      : m === 'backpressure' ? 'bg-warning/15 text-warning border-warning/40'
                      : 'bg-muted/15 text-white border-muted/40'
                    : 'bg-transparent text-muted border-border hover:border-muted/40'
                  }`}
              >
                {m === 'ai' ? <Zap size={11}/> : m === 'static' ? <Clock size={11}/> : null}
                {m === 'backpressure' ? 'BP' : m}
              </button>
            ))}
          </div>
        </div>

        {/* Action buttons */}
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={handleStart}
            disabled={isLoading || isRunning || !configFile}
            className="btn btn-success col-span-2"
          >
            {isLoading ? <Loader2 size={13} className="animate-spin"/> : <Play size={13}/>}
            Start Simulation
          </button>

          <button onClick={onStop}  disabled={isLoading || !isRunning} className="btn btn-danger">
            <Square size={13}/> Stop
          </button>
          <button onClick={onReset} disabled={isLoading || !isRunning} className="btn btn-warning">
            <RotateCcw size={13}/> Reset
          </button>
        </div>




        {/* Save comparison */}
        <button
          onClick={onSaveComparison}
          className="btn btn-ghost w-full"
        >
          <GitCompare size={13}/> Save Run for Comparison
        </button>
      </>}
    </div>
  )
}

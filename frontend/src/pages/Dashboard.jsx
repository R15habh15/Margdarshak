import { useState } from 'react'
import { useTrafficData } from '../hooks/useTrafficData'

import Header              from '../components/layout/Header'
import Sidebar             from '../components/layout/Sidebar'
import ControlPanel        from '../components/control/ControlPanel'
import TrafficMap          from '../components/map/TrafficMap'
import StatsPanel          from '../components/metrics/StatsPanel'
import MetricCard          from '../components/metrics/MetricCard'
import CongestionChart     from '../components/charts/CongestionChart'
import WaitTimeChart       from '../components/charts/WaitTimeChart'
import PerformanceComparison from '../components/comparison/PerformanceComparison'
import { AlertTriangle, X } from 'lucide-react'

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState('map')

  const {
    simStatus, liveState, streamActive,
    currentMetrics, metricsHistory, comparison,
    tlStates, isLoading, error,
    startSimulation, stopSimulation, resetSimulation,
    switchMode, saveComparison, clearError,
  } = useTrafficData()

  return (
    <div className="flex flex-col h-screen bg-surface overflow-hidden">

      {/* Header */}
      <Header simStatus={simStatus} streamActive={streamActive} />

      <div className="flex flex-1 overflow-hidden">

        {/* Sidebar */}
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

        {/* Main content */}
        <main className="flex flex-1 overflow-hidden gap-3 p-3">

          {/* Left column — Control + Stats */}
          <div className="flex flex-col gap-3 w-72 shrink-0 overflow-y-auto">

            <ControlPanel
              simStatus       = {simStatus}
              isLoading       = {isLoading}
              onStart         = {startSimulation}
              onStop          = {stopSimulation}
              onReset         = {resetSimulation}
              onSwitchMode    = {switchMode}
              onSaveComparison= {saveComparison}
            />

            <StatsPanel
              currentMetrics = {currentMetrics}
              simStatus      = {simStatus}
            />

          </div>

          {/* Centre/Right — Tab content */}
          <div className="flex flex-col flex-1 gap-3 overflow-hidden min-w-0">

            {/* Error banner */}
            {error && (
              <div className="flex items-center justify-between px-4 py-2.5 rounded-lg bg-danger/10 border border-danger/30 fade-in">
                <div className="flex items-center gap-2">
                  <AlertTriangle size={14} className="text-danger" />
                  <span className="font-mono text-xs text-danger">{error}</span>
                </div>
                <button onClick={clearError} className="text-muted hover:text-white">
                  <X size={13} />
                </button>
              </div>
            )}

            {/* Map tab */}
            {activeTab === 'map' && (
              <div className="flex flex-col flex-1 gap-3 overflow-hidden">
                <div className="flex-1 min-h-0">
                  <TrafficMap tlStates={tlStates} liveState={liveState} />
                </div>
                <div className="grid grid-cols-2 gap-3 shrink-0">
                  <CongestionChart history={metricsHistory} />
                  <WaitTimeChart   history={metricsHistory} />
                </div>
              </div>
            )}

            {/* Metrics tab */}
            {activeTab === 'metrics' && (
              <div className="flex flex-col gap-3 overflow-y-auto fade-in">
                <StatsPanel currentMetrics={currentMetrics} simStatus={simStatus} />
                <CongestionChart history={metricsHistory} />
                <WaitTimeChart   history={metricsHistory} />
              </div>
            )}

            {/* Comparison tab */}
            {activeTab === 'comparison' && (
              <div className="fade-in">
                <PerformanceComparison comparison={comparison} />
              </div>
            )}

          </div>
        </main>
      </div>
    </div>
  )
}

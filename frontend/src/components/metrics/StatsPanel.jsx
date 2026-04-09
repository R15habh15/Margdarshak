import { Car, Clock, ArrowUpRight, Gauge, AlertTriangle, Layers } from 'lucide-react'
import MetricCard from './MetricCard'

export default function StatsPanel({ currentMetrics, simStatus }) {
  if (!currentMetrics) {
    return (
      <div className="panel p-4 flex items-center justify-center h-40">
        <p className="text-muted font-mono text-xs">No data — start a simulation</p>
      </div>
    )
  }

  const {
    active_vehicles, total_queue, total_wait,
    avg_speed_kmh, departed, arrived,
  } = currentMetrics

  const throughputRate = departed > 0 ? ((arrived / departed) * 100).toFixed(1) : '0.0'

  return (
    <div className="flex flex-col gap-3">
      <h3 className="font-display text-xs font-bold uppercase tracking-widest text-muted px-1">
        Live Metrics
      </h3>
      <div className="grid grid-cols-2 gap-2">
        <MetricCard label="Active Vehicles" value={active_vehicles}  color="accent"   icon={Car}          />
        <MetricCard label="Queue Length"    value={total_queue}      color="warning"  icon={Layers}       />
        <MetricCard label="Avg Wait Time"    value={currentMetrics.avg_wait?.toFixed(1)} unit="s/veh" color="danger" icon={Clock} />
        <MetricCard label="Avg Speed"       value={avg_speed_kmh}    unit="km/h"      color="success"  icon={Gauge}  />
        {/* <MetricCard label="Commute Score"   value={(avg_speed_kmh / 50 * 100).toFixed(0)} unit="%" color="accent" icon={ArrowUpRight} /> */}
        {/* <MetricCard label="Efficiency"      value={throughputRate}   unit="%"         color="success"  icon={Layers}  /> */}
      </div>
    </div>
  )
}

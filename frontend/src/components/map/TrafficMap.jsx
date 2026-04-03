import { useRef, useEffect, useState } from 'react'
import MapLayers from './MapLayers'
import VehicleLayer from './VehicleLayer'

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || ''

export default function TrafficMap({ tlStates, liveState }) {
  const mapContainer = useRef(null)
  const mapRef       = useRef(null)
  const [mapReady, setMapReady]   = useState(false)
  const [mapError, setMapError]   = useState(false)

  useEffect(() => {
    if (!mapContainer.current) return

    // If no Mapbox token, show placeholder
    if (!MAPBOX_TOKEN) {
      setMapError(true)
      return
    }

    import('mapbox-gl').then(({ default: mapboxgl }) => {
      mapboxgl.accessToken = MAPBOX_TOKEN

      mapRef.current = new mapboxgl.Map({
        container: mapContainer.current,
        style:     'mapbox://styles/mapbox/dark-v11',
        center:    [77.209, 28.6139],   // Default: New Delhi
        zoom:      13,
      })

      mapRef.current.on('load', () => setMapReady(true))
      mapRef.current.addControl(new mapboxgl.NavigationControl(), 'top-right')
    }).catch(() => setMapError(true))

    return () => { mapRef.current?.remove() }
  }, [])

  if (mapError || !MAPBOX_TOKEN) {
    return <MapPlaceholder tlStates={tlStates} liveState={liveState} />
  }

  return (
    <div className="relative w-full h-full rounded-lg overflow-hidden border border-border">
      <div ref={mapContainer} className="w-full h-full" />
      {mapReady && mapRef.current && (
        <>
          <MapLayers   map={mapRef.current} tlStates={tlStates} />
          <VehicleLayer map={mapRef.current} liveState={liveState} />
        </>
      )}
    </div>
  )
}

// ── Fallback when Mapbox token not set ──
function MapPlaceholder({ tlStates, liveState }) {
  const tlCount  = Object.keys(tlStates || {}).length
  const vehicles = liveState?.active_vehicles ?? 0

  return (
    <div className="w-full h-full rounded-lg border border-border bg-surface flex flex-col items-center justify-center gap-4 relative overflow-hidden">
      {/* Grid background */}
      <div className="absolute inset-0 opacity-10"
        style={{
          backgroundImage: 'linear-gradient(#00e5ff 1px, transparent 1px), linear-gradient(90deg, #00e5ff 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />
      {/* Intersection dots */}
      {Array.from({ length: 20 }).map((_, i) => {
        const x = (i % 5) * 20 + 10
        const y = Math.floor(i / 5) * 25 + 12.5
        const tl = Object.values(tlStates || {})[i]
        const active = tl?.total_vehicles > 0
        return (
          <div
            key={i}
            className={`absolute w-3 h-3 rounded-full border-2 transition-colors duration-500 ${
              active ? 'bg-warning border-warning glow-warning' : 'bg-surface border-accent/40'
            }`}
            style={{ left: `${x}%`, top: `${y}%`, transform: 'translate(-50%,-50%)' }}
          />
        )
      })}

      <div className="relative z-10 text-center">
        <p className="font-display text-lg font-bold text-accent tracking-widest uppercase">
          Network View
        </p>
        <p className="font-mono text-xs text-muted mt-1">
          Set VITE_MAPBOX_TOKEN for live map
        </p>
        <div className="flex gap-6 mt-4 justify-center">
          <div className="text-center">
            <p className="font-display text-2xl font-bold text-accent">{tlCount}</p>
            <p className="font-mono text-[10px] text-muted uppercase">Junctions</p>
          </div>
          <div className="text-center">
            <p className="font-display text-2xl font-bold text-warning">{vehicles}</p>
            <p className="font-mono text-[10px] text-muted uppercase">Vehicles</p>
          </div>
        </div>
      </div>
    </div>
  )
}

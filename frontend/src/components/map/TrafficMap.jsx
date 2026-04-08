import { useRef, useEffect, useState } from 'react'
import MapLayers from './MapLayers'
import VehicleLayer from './VehicleLayer'
import EmergencyLayer from './EmergencyLayer'
import MapLegend from './MapLegend'

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || ''

export default function TrafficMap({ tlStates, liveState, simRunning, center }) {
  const mapContainer = useRef(null)
  const mapRef       = useRef(null)
  const [mapReady, setMapReady]   = useState(false)
  const [mapError, setMapError]   = useState(false)
  const hasFocused = useRef(false)

  const [viewMode, setViewMode] = useState('3d'); // '2d' or '3d'
  
  const toggleViewMode = () => {
    const next = viewMode === '2d' ? '3d' : '2d';
    setViewMode(next);
    
    if (mapRef.current) {
      mapRef.current.easeTo({
        pitch:   next === '3d' ? 60 : 0,
        bearing: next === '3d' ? -20 : 0,
        duration: 1000
      });

      if (mapRef.current.getLayer('3d-buildings')) {
        mapRef.current.setLayoutProperty(
          '3d-buildings',
          'visibility',
          next === '3d' ? 'visible' : 'none'
        );
      }
    }
  };

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
        center:    [72.8258, 18.9220], // Colaba, Mumbai
        zoom:      16.5,
        pitch:     60,
        bearing:   -20,
        antialias: true,
      })

      mapRef.current.on('load', () => {
        setMapReady(true)
        
        // Add 3D building extrusion
        const layers = mapRef.current.getStyle().layers
        const labelLayerId = layers.find(l => l.type === 'symbol' && l.layout['text-field'])?.id

        mapRef.current.addLayer({
          'id': '3d-buildings',
          'source': 'composite',
          'source-layer': 'building',
          'filter': ['==', 'extrude', 'true'],
          'type': 'fill-extrusion',
          'minzoom': 15,
          'paint': {
            'fill-extrusion-color': '#aaa',
            'fill-extrusion-height': ['get', 'height'],
            'fill-extrusion-base': ['get', 'min_height'],
            'fill-extrusion-opacity': 0.6
          },
          'layout': {
             'visibility': viewMode === '3d' ? 'visible' : 'none'
          }
        }, labelLayerId)
      })
      mapRef.current.addControl(new mapboxgl.NavigationControl(), 'top-right')
    }).catch(() => setMapError(true))

    return () => { mapRef.current?.remove() }
  }, [])

  // ── Auto-center when map is imported ──
  useEffect(() => {
    if (mapReady && mapRef.current && center) {
      mapRef.current.flyTo({ center: center, zoom: 16, duration: 3000 });
      hasFocused.current = true; // prevent vehicle-follow if we just manually imported
    }
  }, [mapReady, center])

  // Auto-center the camera to the simulation area if vehicles are actively moving
  useEffect(() => {
    if (mapReady && mapRef.current && liveState?.vehicles?.length > 0 && !hasFocused.current) {
      const firstCar = liveState.vehicles[0];
      mapRef.current.flyTo({ center: [firstCar.lng, firstCar.lat], zoom: 15, duration: 2000 });
      hasFocused.current = true;
    }
  }, [mapReady, liveState])

  if (mapError || !MAPBOX_TOKEN) {
    return <MapPlaceholder tlStates={tlStates} liveState={liveState} />
  }

  return (
    <div className="relative w-full h-full rounded-lg overflow-hidden border border-border">
      <div ref={mapContainer} className="w-full h-full" />

      {/* Floating 2D/3D Toggle */}
      {mapReady && (
        <div className="absolute top-4 left-4 flex gap-2 z-10">
          <button 
            onClick={toggleViewMode}
            className={`px-3 py-1.5 rounded-md font-display text-xs font-bold uppercase tracking-wider backdrop-blur-md border transition-all
              ${viewMode === '3d' 
                ? 'bg-accent/40 text-white border-accent/50 shadow-[0_0_15px_rgba(0,229,255,0.3)]' 
                : 'bg-surface/80 text-muted border-border hover:text-white'
              }`}
          >
            {viewMode === '3d' ? '3D VIEW' : '2D VIEW'}
          </button>
        </div>
      )}

      {mapReady && mapRef.current && (
        <>
          <MapLayers      map={mapRef.current} tlStates={tlStates} />
          <VehicleLayer   map={mapRef.current} liveState={liveState} />
          <EmergencyLayer map={mapRef.current} liveState={liveState} />
          <MapLegend simRunning={simRunning} />
        </>
      )}
    </div>
  )
}

// ── Hook to auto-center bounds based on active vehicle coordinates ──
function useMapBounds(vehicles) {
  const [bounds, setBounds] = useState(null)
  
  useEffect(() => {
    if (!vehicles || vehicles.length === 0) return
    
    let changed = false
    const next = bounds ? { ...bounds } : { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity }
    
    vehicles.forEach(v => {
      if (v.lng < next.minX) { next.minX = v.lng; changed = true }
      if (v.lng > next.maxX) { next.maxX = v.lng; changed = true }
      if (v.lat < next.minY) { next.minY = v.lat; changed = true }
      if (v.lat > next.maxY) { next.maxY = v.lat; changed = true }
    })

    if (next.maxX === next.minX) { next.maxX += 0.01; next.minX -= 0.01 }
    if (next.maxY === next.minY) { next.maxY += 0.01; next.minY -= 0.01 }

    if (changed || !bounds) setBounds(next)
  }, [vehicles])

  return bounds
}

// ── Fallback when Mapbox token not set ──
function MapPlaceholder({ tlStates, liveState }) {
  const tlCount  = Object.keys(tlStates || {}).length
  const vehicleCount = liveState?.active_vehicles ?? 0
  const activeVehicles = liveState?.vehicles ?? []
  
  const bounds = useMapBounds(activeVehicles)

  return (
    <div className="w-full h-full rounded-lg border border-border bg-surface flex flex-col items-center justify-center gap-4 relative overflow-hidden">
      {/* Grid background */}
      <div className="absolute inset-0 opacity-10 pointer-events-none"
        style={{
          backgroundImage: 'linear-gradient(#00e5ff 1px, transparent 1px), linear-gradient(90deg, #00e5ff 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />
      
      {/* Dynamic Moving Vehicles */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        {bounds && activeVehicles.map(v => {
          const xRange = bounds.maxX - bounds.minX;
          const yRange = bounds.maxY - bounds.minY;
          
          // 10% padding so they don't ride the very edge
          const left = 10 + ((v.lng - bounds.minX) / xRange) * 80;
          const top = 10 + (1 - ((v.lat - bounds.minY) / yRange)) * 80; // invert lat

          return (
            <div
              key={v.id}
              className="absolute rounded-full"
              style={{
                left: `${left}%`,
                top: `${top}%`,
                width: '6px',
                height: '6px',
                backgroundColor: '#00e5ff',
                boxShadow: '0 0 10px #00e5ff',
                transform: 'translate(-50%, -50%)',
                transition: 'left 1s linear, top 1s linear' // Super smooth 60fps interpolation!
              }}
            />
          )
        })}
      </div>

      <div className="relative z-10 text-center pointer-events-none bg-surface/80 p-6 rounded-lg backdrop-blur shadow-2xl border border-border">
        <p className="font-display text-lg font-bold text-accent tracking-widest uppercase">
          Live Traffic Render
        </p>
        <p className="font-mono text-xs text-muted mt-1 max-w-[200px] mx-auto leading-relaxed">
          Set VITE_MAPBOX_TOKEN for full satellite roads view.
        </p>
        <div className="flex gap-6 mt-6 justify-center">
          <div className="text-center">
            <p className="font-display text-2xl font-bold text-accent">{tlCount}</p>
            <p className="font-mono text-[10px] text-muted uppercase">Junctions</p>
          </div>
          <div className="text-center">
            <p className="font-display text-2xl font-bold text-warning">{vehicleCount}</p>
            <p className="font-mono text-[10px] text-muted uppercase">Vehicles</p>
          </div>
        </div>
      </div>
    </div>
  )
}


import { useEffect, useRef } from 'react'

/**
 * EmergencyLayer — dramatic siren marker for emergency vehicles.
 * Renders a pulsing red beacon with rotating siren effect + "EMERGENCY" label.
 * Tracks the vehicle's position in real-time from liveState.
 */
export default function EmergencyLayer({ map, liveState }) {
  const markersRef = useRef({})

  useEffect(() => {
    // Inject siren CSS once
    if (!document.getElementById('siren-styles')) {
      const style = document.createElement('style')
      style.id = 'siren-styles'
      style.textContent = `
        .siren-wrapper {
          position: relative;
          width: 24px;
          height: 24px;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .siren-pulse1, .siren-pulse2 {
          position: absolute;
          border-radius: 50%;
          border: 2px solid rgba(255, 40, 40, 0.7);
          animation: siren-ring 1.2s ease-out infinite;
        }
        .siren-pulse2 { animation-delay: 0.4s; }
        @keyframes siren-ring {
          0%   { width: 18px; height: 18px; opacity: 0.9; }
          100% { width: 54px; height: 54px; opacity: 0; }
        }
        .siren-dot {
          position: relative;
          width: 16px;
          height: 16px;
          border-radius: 50%;
          background: radial-gradient(circle, #ff6060 0%, #ff1744 60%);
          box-shadow: 0 0 10px #ff1744, 0 0 20px rgba(255,23,68,0.6);
          border: 2px solid rgba(255,255,255,0.5);
          z-index: 2;
          animation: siren-flash 0.6s ease-in-out infinite alternate;
        }
        @keyframes siren-flash {
          from { box-shadow: 0 0 8px #ff1744, 0 0 16px rgba(255,23,68,0.5); }
          to   { box-shadow: 0 0 18px #ff6060, 0 0 36px rgba(255,40,40,0.8); }
        }
        .siren-label {
          position: absolute;
          top: -20px;
          left: 50%;
          transform: translateX(-50%);
          font-size: 9px;
          font-family: monospace;
          font-weight: bold;
          letter-spacing: 0.08em;
          color: #ff4444;
          text-shadow: 0 0 6px rgba(255,40,40,0.9);
          white-space: nowrap;
          pointer-events: none;
        }
        .siren-icon {
          position: absolute;
          top: -32px;
          left: 50%;
          transform: translateX(-50%);
          font-size: 14px;
        }
      `
      document.head.appendChild(style)
    }
  }, [])

  useEffect(() => {
    if (!map || !liveState?.vehicles) return

    import('mapbox-gl').then(({ default: mapboxgl }) => {
      const evVehicles = (liveState.vehicles || []).filter(v => v.id?.startsWith('emergency_'))

      // Remove stale
      Object.keys(markersRef.current).forEach(id => {
        if (!evVehicles.find(v => v.id === id)) {
          markersRef.current[id].remove()
          delete markersRef.current[id]
        }
      })

      evVehicles.forEach(v => {
        if (!v.lng || !v.lat) return

        if (markersRef.current[v.id]) {
          markersRef.current[v.id].setLngLat([v.lng, v.lat])
        } else {
          const wrapper = document.createElement('div')
          wrapper.className = 'siren-wrapper'

          const icon  = document.createElement('div'); icon.className  = 'siren-icon';   icon.textContent = '🚑'
          const label = document.createElement('div'); label.className = 'siren-label';  label.textContent = '▲ EMERGENCY'
          const p1    = document.createElement('div'); p1.className    = 'siren-pulse1'
          const p2    = document.createElement('div'); p2.className    = 'siren-pulse2'
          const dot   = document.createElement('div'); dot.className   = 'siren-dot'

          wrapper.appendChild(icon)
          wrapper.appendChild(label)
          wrapper.appendChild(p1)
          wrapper.appendChild(p2)
          wrapper.appendChild(dot)

          const marker = new mapboxgl.Marker({ element: wrapper, anchor: 'center' })
            .setLngLat([v.lng, v.lat])
            .addTo(map)

          markersRef.current[v.id] = marker
        }
      })
    })
  }, [map, liveState])

  useEffect(() => {
    return () => {
      Object.values(markersRef.current).forEach(m => m.remove())
      markersRef.current = {}
    }
  }, [])

  return null
}

/**
 * MapLegend — fixed overlay showing what map symbols mean.
 * Always visible in top-right corner of the map.
 */
export default function MapLegend({ simRunning }) {
  if (!simRunning) return null

  return (
    <div
      style={{
        position: 'absolute',
        bottom: '28px',
        right: '12px',
        zIndex: 10,
        background: 'rgba(10, 14, 26, 0.88)',
        backdropFilter: 'blur(12px)',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: '10px',
        padding: '10px 14px',
        minWidth: '175px',
        pointerEvents: 'none',
      }}
    >
      <p style={{ fontFamily: 'Rajdhani, sans-serif', fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#00e5ff', marginBottom: '8px' }}>
        MAP LEGEND
      </p>

      {/* Vehicles */}
      <p style={{ fontFamily: 'monospace', fontSize: '9px', color: 'rgba(255,255,255,0.4)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        Vehicles
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '8px' }}>
        {[
          { color: '#00e5ff', label: 'Free-flowing  (>29 km/h)' },
          { color: '#a3e635', label: 'Slow moving   (10–29 km/h)' },
          { color: '#ff8c00', label: 'Waiting at red light ✓' },
        ].map(({ color, label }) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: color, boxShadow: `0 0 6px ${color}` }} />
            <span style={{ fontFamily: 'monospace', fontSize: '9px', color: 'rgba(255,255,255,0.65)' }}>{label}</span>
          </div>
        ))}
        <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
          <span style={{ fontSize: '11px' }}>🚑</span>
          <span style={{ fontFamily: 'monospace', fontSize: '9px', color: 'rgba(255,255,255,0.65)' }}>Emergency — green wave active</span>
        </div>
      </div>

     
    
      </div>
  )
}

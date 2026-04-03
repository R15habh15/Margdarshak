import { useEffect } from 'react'

/**
 * VehicleLayer — renders a heatmap layer showing vehicle density.
 * Intensity is derived from per-junction vehicle counts.
 */
export default function VehicleLayer({ map, liveState }) {
  useEffect(() => {
    if (!map || !liveState) return

    const SOURCE_ID = 'vehicle-density'
    const LAYER_ID  = 'vehicle-heat'

    const features = Object.entries(liveState.traffic_lights || {}).map(([id, data]) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [0, 0] }, // placeholder
      properties: {
        weight: Math.min((data.total_vehicles ?? 0) / 20, 1),
      },
    }))

    const geojson = { type: 'FeatureCollection', features }

    try {
      if (map.getSource(SOURCE_ID)) {
        map.getSource(SOURCE_ID).setData(geojson)
      } else {
        map.addSource(SOURCE_ID, { type: 'geojson', data: geojson })
        map.addLayer({
          id:     LAYER_ID,
          type:   'heatmap',
          source: SOURCE_ID,
          paint: {
            'heatmap-weight':     ['get', 'weight'],
            'heatmap-intensity':  1.2,
            'heatmap-radius':     30,
            'heatmap-opacity':    0.7,
            'heatmap-color': [
              'interpolate', ['linear'], ['heatmap-density'],
              0,   'rgba(0,229,255,0)',
              0.3, 'rgba(0,229,255,0.6)',
              0.6, 'rgba(255,183,0,0.8)',
              1.0, 'rgba(255,68,68,1)',
            ],
          },
        })
      }
    } catch (e) {}

    return () => {
      try {
        if (map.getLayer(LAYER_ID))  map.removeLayer(LAYER_ID)
        if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID)
      } catch (_) {}
    }
  }, [map, liveState])

  return null
}

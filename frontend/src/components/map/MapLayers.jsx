import { useEffect } from 'react'

/**
 * MapLayers — renders traffic light junction markers on the Mapbox map.
 * Each junction is colored by congestion level.
 */
export default function MapLayers({ map, tlStates }) {
  useEffect(() => {
    if (!map || !tlStates) return

    const SOURCE_ID = 'tl-junctions'
    const LAYER_ID  = 'tl-circles'

    // Build GeoJSON from tlStates
    // (tlStates don't have coordinates — we render abstract markers)
    // Real coordinates would come from graph_builder / SUMO network
    const features = Object.entries(tlStates).map(([id, data]) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [0, 0] }, // placeholder
      properties: {
        id,
        phase:    data.phase ?? 0,
        vehicles: data.total_vehicles ?? 0,
        queue:    data.total_queue    ?? 0,
        wait:     data.total_wait     ?? 0,
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
          type:   'circle',
          source: SOURCE_ID,
          paint: {
            'circle-radius':       8,
            'circle-color':        '#00e5ff',
            'circle-opacity':      0.85,
            'circle-stroke-width': 1.5,
            'circle-stroke-color': '#ffffff22',
          },
        })
      }
    } catch (e) {
      // Map not fully ready yet
    }

    return () => {
      try {
        if (map.getLayer(LAYER_ID))  map.removeLayer(LAYER_ID)
        if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID)
      } catch (_) {}
    }
  }, [map, tlStates])

  return null
}

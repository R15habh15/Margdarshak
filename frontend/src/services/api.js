/**
 * api.js
 * Centralised HTTP + WebSocket client for the Margadarshak backend.
 */

import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WS_URL   = import.meta.env.VITE_WS_URL  || 'ws://localhost:8000'

const http = axios.create({
  baseURL: BASE_URL,
  timeout: 300_000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Response interceptor — unwrap data ──
http.interceptors.response.use(
  res => res.data,
  err => {
    const msg = err.response?.data?.detail || err.message || 'Unknown error'
    return Promise.reject(new Error(msg))
  }
)

// ================================================================
// Map API
// ================================================================
export const mapApi = {
  downloadByPlace: (placeName) =>
    http.post('/api/map/download/place', { place_name: placeName }),

  downloadByBbox: (north, south, east, west, name = 'custom') =>
    http.post('/api/map/download/bbox', { north, south, east, west, name }),

  convertToSumo: (osmFilename) =>
    http.post('/api/map/convert', { osm_filename: osmFilename }),

  generateRoutes: (networkFilename, opts = {}) =>
    http.post('/api/map/generate-routes', {
      network_filename:       networkFilename,
      num_vehicles:           opts.numVehicles           ?? 200,
      simulation_duration:    opts.simulationDuration    ?? 3600,
      vehicle_density_period: opts.vehicleDensityPeriod  ?? 2.0,
    }),

  listMaps: () => http.get('/api/map/list'),
}

// ================================================================
// Simulation API
// ================================================================
export const simulationApi = {
  start: (configPath, mode = 'static', useGui = false, port = 8813) =>
    http.post('/api/simulation/start', { config_path: configPath, mode, use_gui: useGui, port }),

  stop: () => http.post('/api/simulation/stop'),

  reset: () => http.post('/api/simulation/reset'),

  setMode: (mode) => http.post('/api/simulation/set-mode', { mode }),

  getStatus: () => http.get('/api/simulation/status'),
}

// ================================================================
// Metrics API
// ================================================================
export const metricsApi = {
  getCurrent:    () => http.get('/api/metrics/current'),
  getSummary:    () => http.get('/api/metrics/summary'),
  getHistory:    () => http.get('/api/metrics/history'),
  saveComparison: () => http.post('/api/metrics/comparison/save'),
  getComparison: () => http.get('/api/metrics/comparison'),
}

// ================================================================
// Training API
// ================================================================
export const trainingApi = {
  start:      (config) => http.post('/api/training/start', config),
  stop:       ()       => http.post('/api/training/stop'),
  getStatus:  ()       => http.get('/api/training/status'),
  getHistory: ()       => http.get('/api/training/history'),
  getModels:  ()       => http.get('/api/training/models'),
  loadModel:  (filename) => http.post('/api/training/load', { filename }),
}

// ================================================================
// WebSocket — simulation live stream
// ================================================================
export function createSimulationSocket(onMessage, onError, onClose) {
  const ws = new WebSocket(`${WS_URL}/api/simulation/stream`)

  ws.onopen    = () => console.log('[WS] Connected to simulation stream')
  ws.onmessage = (e) => { try { onMessage(JSON.parse(e.data)) } catch {} }
  ws.onerror   = (e) => { console.error('[WS] Error', e); onError?.(e) }
  ws.onclose   = (e) => { console.log('[WS] Closed', e.code); onClose?.(e) }

  return {
    send:  (data) => ws.readyState === WebSocket.OPEN && ws.send(JSON.stringify(data)),
    close: ()     => ws.close(),
    get readyState() { return ws.readyState },
  }
}

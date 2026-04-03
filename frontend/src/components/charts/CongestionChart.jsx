import { useEffect, useRef } from 'react'
import { Chart, registerables } from 'chart.js'
Chart.register(...registerables)

export default function CongestionChart({ history }) {
  const ref = useRef(null)
  const chartRef = useRef(null)

  useEffect(() => {
    if (!ref.current) return

    const labels = history.map(h => `${Math.floor(h.sim_time / 60)}m`)
    const data   = history.map(h => h.active_vehicles)

    if (chartRef.current) {
      chartRef.current.data.labels        = labels
      chartRef.current.data.datasets[0].data = data
      chartRef.current.update('none')
      return
    }

    chartRef.current = new Chart(ref.current, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Active Vehicles',
          data,
          borderColor:     '#00e5ff',
          backgroundColor: 'rgba(0,229,255,0.06)',
          borderWidth: 1.5,
          pointRadius: 0,
          fill: true,
          tension: 0.4,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: { legend: { display: false } },
        scales: {
          x: {
            ticks: { color: '#8b949e', font: { family: 'JetBrains Mono', size: 9 }, maxTicksLimit: 6 },
            grid:  { color: '#21262d' },
          },
          y: {
            ticks: { color: '#8b949e', font: { family: 'JetBrains Mono', size: 9 } },
            grid:  { color: '#21262d' },
          },
        },
      },
    })

    return () => { chartRef.current?.destroy(); chartRef.current = null }
  }, [history])

  return (
    <div className="panel p-4 flex flex-col gap-3">
      <h3 className="font-display text-xs font-bold uppercase tracking-widest text-muted">
        Vehicle Count Over Time
      </h3>
      <div className="h-36 relative">
        {(!history || history.length === 0)
          ? <div className="absolute inset-0 flex items-center justify-center">
              <p className="text-muted font-mono text-xs">Waiting for data…</p>
            </div>
          : <canvas ref={ref} />
        }
      </div>
    </div>
  )
}

import { useEffect, useRef } from 'react'
import { Chart, registerables } from 'chart.js'
Chart.register(...registerables)

export default function WaitTimeChart({ history }) {
  const ref      = useRef(null)
  const chartRef = useRef(null)

  useEffect(() => {
    if (!ref.current) return

    const labels = history.map(h => `${Math.floor(h.sim_time / 60)}m`)
    const data   = history.map(h => h.total_waiting_time)

    if (chartRef.current) {
      chartRef.current.data.labels           = labels
      chartRef.current.data.datasets[0].data = data
      chartRef.current.update('none')
      return
    }

    chartRef.current = new Chart(ref.current, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Cumulative Wait (s)',
          data,
          backgroundColor: 'rgba(255,183,0,0.25)',
          borderColor:     '#ffb700',
          borderWidth:     1,
          borderRadius:    2,
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
            grid:  { display: false },
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
        Cumulative Wait Time
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

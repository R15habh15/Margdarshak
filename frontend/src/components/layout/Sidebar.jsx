import { Map, BarChart2, GitCompare, Settings, Radio } from 'lucide-react'

const NAV = [
  { id: 'map',        icon: Map,        label: 'Map' },
  { id: 'metrics',    icon: BarChart2,   label: 'Metrics' },
  { id: 'comparison', icon: GitCompare,  label: 'Compare' },
]

export default function Sidebar({ activeTab, onTabChange }) {
  return (
    <aside className="w-14 flex flex-col items-center py-4 gap-2 border-r border-border bg-panel">
      {NAV.map(({ id, icon: Icon, label }) => (
        <button
          key={id}
          title={label}
          onClick={() => onTabChange(id)}
          className={`w-9 h-9 rounded-lg flex items-center justify-center transition-all
            ${activeTab === id
              ? 'bg-accent/15 text-accent border border-accent/30'
              : 'text-muted hover:text-white hover:bg-white/5'
            }`}
        >
          <Icon size={16} />
        </button>
      ))}
    </aside>
  )
}

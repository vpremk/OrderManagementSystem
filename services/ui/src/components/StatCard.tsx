interface Props {
  label: string
  value: string | number
  sub?: string
  accent?: 'green' | 'red' | 'amber' | 'slate'
}

const accents = {
  green: 'text-emerald-400',
  red:   'text-red-400',
  amber: 'text-amber-400',
  slate: 'text-slate-300',
}

export default function StatCard({ label, value, sub, accent = 'slate' }: Props) {
  return (
    <div className="bg-card border border-border rounded-lg p-5">
      <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-3xl font-bold ${accents[accent]}`}>{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  )
}

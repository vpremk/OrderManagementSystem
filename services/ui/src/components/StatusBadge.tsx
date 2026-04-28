const STATUS: Record<string, { label: string; cls: string }> = {
  '0': { label: 'New',          cls: 'bg-blue-500/15 text-blue-300' },
  '1': { label: 'Part. Filled', cls: 'bg-amber-500/15 text-amber-300' },
  '2': { label: 'Filled',       cls: 'bg-emerald-500/15 text-emerald-400' },
  '4': { label: 'Canceled',     cls: 'bg-slate-500/15 text-slate-400' },
  '8': { label: 'Rejected',     cls: 'bg-red-500/15 text-red-400' },
  'A': { label: 'Pending',      cls: 'bg-purple-500/15 text-purple-300' },
}

export default function StatusBadge({ status }: { status: string }) {
  const s = STATUS[status] ?? { label: status, cls: 'bg-slate-500/15 text-slate-400' }
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${s.cls}`}>
      {s.label}
    </span>
  )
}

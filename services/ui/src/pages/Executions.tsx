import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchExecutions } from '../api'

export default function Executions() {
  const [filterSymbol, setFilterSymbol] = useState('')
  const [filterAccount, setFilterAccount] = useState('')

  const params: Record<string, string> = {}
  if (filterSymbol)  params.symbol  = filterSymbol
  if (filterAccount) params.account = filterAccount

  const { data: executions = [], isFetching } = useQuery({
    queryKey: ['executions', params],
    queryFn: () => fetchExecutions(params),
    refetchInterval: 3000,
  })

  const totalVolume = executions.reduce((sum, e) => sum + Number(e.last_qty) * Number(e.last_px), 0)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-100">Executions</h1>
        <div className="text-sm text-slate-400">
          Volume: <span className="text-slate-200 font-semibold">
            {totalVolume.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
          {isFetching && <span className="text-slate-600 ml-3">refreshing…</span>}
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <input
          className={filter}
          placeholder="Symbol"
          value={filterSymbol}
          onChange={e => setFilterSymbol(e.target.value.toUpperCase())}
        />
        <input
          className={filter}
          placeholder="Account"
          value={filterAccount}
          onChange={e => setFilterAccount(e.target.value)}
        />
      </div>

      <div className="bg-card border border-border rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              {['Exec ID', 'Order ID', 'Type', 'Last Qty', 'Last Px', 'Cum Qty', 'Avg Px', 'Leaves Qty', 'Time'].map(h => (
                <th key={h} className="px-4 py-3 text-left text-xs text-slate-500 uppercase tracking-wider whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {executions.length === 0 && (
              <tr>
                <td colSpan={9} className="text-center text-slate-600 py-10 text-xs">
                  No executions found
                </td>
              </tr>
            )}
            {executions.map(e => (
              <tr key={e.exec_id} className="border-b border-border/40 hover:bg-white/[0.02]">
                <td className="px-4 py-3 font-mono text-slate-500 text-xs">{e.exec_id.slice(0, 8)}…</td>
                <td className="px-4 py-3 font-mono text-slate-500 text-xs">{e.order_id.slice(0, 8)}…</td>
                <td className="px-4 py-3">
                  <ExecTypeBadge type={e.exec_type} />
                </td>
                <td className="px-4 py-3 text-emerald-400 font-semibold">{e.last_qty}</td>
                <td className="px-4 py-3 text-slate-200">{Number(e.last_px).toFixed(2)}</td>
                <td className="px-4 py-3 text-slate-300">{e.cum_qty}</td>
                <td className="px-4 py-3 text-slate-300">{Number(e.avg_px).toFixed(2)}</td>
                <td className="px-4 py-3 text-slate-400">{e.leaves_qty}</td>
                <td className="px-4 py-3 text-slate-500 text-xs whitespace-nowrap">
                  {new Date(e.created_at).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ExecTypeBadge({ type }: { type: string }) {
  const m: Record<string, { label: string; cls: string }> = {
    '0': { label: 'New',     cls: 'text-blue-300 bg-blue-500/10' },
    '1': { label: 'Partial', cls: 'text-amber-300 bg-amber-500/10' },
    '2': { label: 'Fill',    cls: 'text-emerald-400 bg-emerald-500/10' },
    '4': { label: 'Cancel',  cls: 'text-slate-400 bg-slate-500/10' },
    '8': { label: 'Reject',  cls: 'text-red-400 bg-red-500/10' },
  }
  const s = m[type] ?? { label: type, cls: 'text-slate-400 bg-slate-500/10' }
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${s.cls}`}>{s.label}</span>
  )
}

const filter = 'bg-surface border border-border rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 placeholder:text-slate-600'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchPositions } from '../api'

export default function Positions() {
  const [filterAccount, setFilterAccount] = useState('')

  const params: Record<string, string> = {}
  if (filterAccount) params.account = filterAccount

  const { data: positions = [], isFetching } = useQuery({
    queryKey: ['positions', params],
    queryFn: () => fetchPositions(params),
    refetchInterval: 3000,
  })

  const totalLong  = positions.filter(p => Number(p.net_qty) > 0).length
  const totalShort = positions.filter(p => Number(p.net_qty) < 0).length

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-100">Positions</h1>
        <div className="flex gap-4 text-sm">
          <span className="text-emerald-400">{totalLong} Long</span>
          <span className="text-red-400">{totalShort} Short</span>
          {isFetching && <span className="text-slate-600">refreshing…</span>}
        </div>
      </div>

      {/* Filter */}
      <input
        className="bg-surface border border-border rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 placeholder:text-slate-600 w-48"
        placeholder="Filter by account"
        value={filterAccount}
        onChange={e => setFilterAccount(e.target.value)}
      />

      <div className="bg-card border border-border rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              {['Account', 'Symbol', 'Net Qty', 'Avg Cost', 'Notional Value', 'Last Updated'].map(h => (
                <th key={h} className="px-4 py-3 text-left text-xs text-slate-500 uppercase tracking-wider">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {positions.length === 0 && (
              <tr>
                <td colSpan={6} className="text-center text-slate-600 py-10 text-xs">
                  No positions
                </td>
              </tr>
            )}
            {positions.map(p => {
              const qty  = Number(p.net_qty)
              const cost = Number(p.avg_cost)
              const notional = Math.abs(qty * cost)
              const isLong = qty >= 0
              return (
                <tr key={p.id} className="border-b border-border/40 hover:bg-white/[0.02]">
                  <td className="px-4 py-3 text-slate-400">{p.account}</td>
                  <td className="px-4 py-3 text-slate-100 font-semibold">{p.symbol}</td>
                  <td className={`px-4 py-3 font-semibold ${isLong ? 'text-emerald-400' : 'text-red-400'}`}>
                    {isLong ? '+' : ''}{qty.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-slate-300">{cost.toFixed(2)}</td>
                  <td className="px-4 py-3 text-slate-300">
                    {notional.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-3 text-slate-500 text-xs">
                    {new Date(p.updated_at).toLocaleString()}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

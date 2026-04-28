import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchOrders, cancelOrder, fetchOrderExecutions } from '../api'
import StatusBadge from '../components/StatusBadge'
import SideTag from '../components/SideTag'
import NewOrderModal from '../components/NewOrderModal'
import type { Order, Execution } from '../types'

const STATUSES = [
  { value: '', label: 'All Statuses' },
  { value: '0', label: 'New' },
  { value: '1', label: 'Part. Filled' },
  { value: '2', label: 'Filled' },
  { value: '4', label: 'Canceled' },
  { value: '8', label: 'Rejected' },
]

export default function Orders() {
  const qc = useQueryClient()
  const [showModal, setShowModal] = useState(false)
  const [filterAccount, setFilterAccount] = useState('')
  const [filterSymbol, setFilterSymbol] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const params: Record<string, string> = {}
  if (filterAccount) params.account = filterAccount
  if (filterSymbol)  params.symbol  = filterSymbol
  if (filterStatus)  params.status  = filterStatus

  const { data: orders = [], isFetching } = useQuery({
    queryKey: ['orders', params],
    queryFn: () => fetchOrders(params),
    refetchInterval: 3000,
  })

  const { data: executions = [] } = useQuery({
    queryKey: ['executions', expandedId],
    queryFn: () => fetchOrderExecutions(expandedId!),
    enabled: !!expandedId,
    refetchInterval: 3000,
  })

  const cancelMutation = useMutation({
    mutationFn: cancelOrder,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['orders'] }),
  })

  const canCancel = (o: Order) => ['0', '1', 'A'].includes(o.status)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-100">Orders</h1>
        <button
          onClick={() => setShowModal(true)}
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold rounded transition-colors"
        >
          + New Order
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <input
          className={filter}
          placeholder="Account"
          value={filterAccount}
          onChange={e => setFilterAccount(e.target.value)}
        />
        <input
          className={filter}
          placeholder="Symbol"
          value={filterSymbol}
          onChange={e => setFilterSymbol(e.target.value.toUpperCase())}
        />
        <select
          className={filter}
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
        >
          {STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        {isFetching && <span className="text-xs text-slate-600 self-center">refreshing…</span>}
      </div>

      {/* Table */}
      <div className="bg-card border border-border rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              {['Cl. Ord ID', 'Account', 'Symbol', 'Side', 'Type', 'Qty', 'Price', 'Status', 'Time', ''].map(h => (
                <th key={h} className="px-4 py-3 text-left text-xs text-slate-500 uppercase tracking-wider whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {orders.length === 0 && (
              <tr>
                <td colSpan={10} className="text-center text-slate-600 py-10 text-xs">
                  No orders found
                </td>
              </tr>
            )}
            {orders.map(o => (
              <>
                <tr
                  key={o.order_id}
                  className="border-b border-border/40 hover:bg-white/[0.02] cursor-pointer"
                  onClick={() => setExpandedId(expandedId === o.order_id ? null : o.order_id)}
                >
                  <td className="px-4 py-3 text-slate-300 font-mono text-xs">{o.cl_ord_id}</td>
                  <td className="px-4 py-3 text-slate-400">{o.account}</td>
                  <td className="px-4 py-3 text-slate-100 font-semibold">{o.symbol}</td>
                  <td className="px-4 py-3"><SideTag side={o.side} /></td>
                  <td className="px-4 py-3 text-slate-400">{o.ord_type === '2' ? 'Limit' : 'Market'}</td>
                  <td className="px-4 py-3 text-slate-200">{Number(o.quantity).toLocaleString()}</td>
                  <td className="px-4 py-3 text-slate-300">{o.price ? Number(o.price).toFixed(2) : '—'}</td>
                  <td className="px-4 py-3"><StatusBadge status={o.status} /></td>
                  <td className="px-4 py-3 text-slate-500 text-xs whitespace-nowrap">
                    {new Date(o.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    {canCancel(o) && (
                      <button
                        onClick={e => { e.stopPropagation(); cancelMutation.mutate(o.order_id) }}
                        disabled={cancelMutation.isPending}
                        className="px-2 py-1 text-xs bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded transition-colors disabled:opacity-40"
                      >
                        Cancel
                      </button>
                    )}
                  </td>
                </tr>

                {/* Expanded executions row */}
                {expandedId === o.order_id && (
                  <tr key={`${o.order_id}-exec`} className="bg-surface">
                    <td colSpan={10} className="px-8 py-4">
                      <ExecutionSubTable executions={executions} />
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && <NewOrderModal onClose={() => setShowModal(false)} />}
    </div>
  )
}

function ExecutionSubTable({ executions }: { executions: Execution[] }) {
  if (executions.length === 0) {
    return <p className="text-xs text-slate-600">No executions yet</p>
  }
  return (
    <div>
      <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Executions</p>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border">
            {['Exec ID', 'Type', 'Last Qty', 'Last Px', 'Cum Qty', 'Avg Px', 'Leaves Qty', 'Time'].map(h => (
              <th key={h} className="pr-6 pb-2 text-left text-slate-500 uppercase tracking-wider">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {executions.map(e => (
            <tr key={e.exec_id} className="border-b border-border/30">
              <td className="pr-6 py-1.5 font-mono text-slate-500">{e.exec_id.slice(0, 8)}…</td>
              <td className="pr-6 py-1.5 text-slate-400">{execTypeName(e.exec_type)}</td>
              <td className="pr-6 py-1.5 text-emerald-400">{e.last_qty}</td>
              <td className="pr-6 py-1.5 text-slate-200">{Number(e.last_px).toFixed(2)}</td>
              <td className="pr-6 py-1.5 text-slate-300">{e.cum_qty}</td>
              <td className="pr-6 py-1.5 text-slate-300">{Number(e.avg_px).toFixed(2)}</td>
              <td className="pr-6 py-1.5 text-slate-400">{e.leaves_qty}</td>
              <td className="pr-6 py-1.5 text-slate-500">{new Date(e.created_at).toLocaleTimeString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function execTypeName(t: string) {
  const m: Record<string, string> = { '0': 'New', '1': 'Partial', '2': 'Fill', '4': 'Cancel', '8': 'Reject' }
  return m[t] ?? t
}

const filter = 'bg-surface border border-border rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 placeholder:text-slate-600'

import { useQuery } from '@tanstack/react-query'
import { fetchOrders, fetchExecutions, fetchPositions } from '../api'
import StatCard from '../components/StatCard'
import SideTag from '../components/SideTag'
import StatusBadge from '../components/StatusBadge'

export default function Dashboard() {
  const { data: orders = [] } = useQuery({
    queryKey: ['orders'],
    queryFn: () => fetchOrders(),
    refetchInterval: 3000,
  })
  const { data: executions = [] } = useQuery({
    queryKey: ['executions'],
    queryFn: () => fetchExecutions(),
    refetchInterval: 3000,
  })
  const { data: positions = [] } = useQuery({
    queryKey: ['positions'],
    queryFn: () => fetchPositions(),
    refetchInterval: 3000,
  })

  const total    = orders.length
  const open     = orders.filter(o => ['0', '1', 'A'].includes(o.status)).length
  const filled   = orders.filter(o => o.status === '2').length
  const rejected = orders.filter(o => o.status === '8').length

  const recentFills = executions.filter(e => ['1', '2'].includes(e.exec_type)).slice(0, 10)

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-100">Dashboard</h1>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Orders"  value={total}    accent="slate" />
        <StatCard label="Open"          value={open}     accent="amber" />
        <StatCard label="Filled"        value={filled}   accent="green" />
        <StatCard label="Rejected"      value={rejected} accent="red"   />
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Recent fills */}
        <section>
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">
            Recent Fills
          </h2>
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <Tr header>
                  <Th>Symbol</Th><Th>Side</Th><Th>Qty</Th><Th>Price</Th><Th>Time</Th>
                </Tr>
              </thead>
              <tbody>
                {recentFills.length === 0 && (
                  <tr><td colSpan={5} className="text-center text-slate-600 py-6 text-xs">No fills yet</td></tr>
                )}
                {recentFills.map(e => (
                  <Tr key={e.exec_id}>
                    <Td className="text-slate-200">{/* symbol via order join not available here */}—</Td>
                    <Td><span className="text-emerald-400">{Number(e.last_qty).toLocaleString()}</span></Td>
                    <Td>{e.last_qty}</Td>
                    <Td className="text-emerald-300">{Number(e.last_px).toFixed(2)}</Td>
                    <Td className="text-slate-500">{new Date(e.created_at).toLocaleTimeString()}</Td>
                  </Tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Positions */}
        <section>
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">
            Open Positions
          </h2>
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <Tr header>
                  <Th>Account</Th><Th>Symbol</Th><Th>Net Qty</Th><Th>Avg Cost</Th>
                </Tr>
              </thead>
              <tbody>
                {positions.length === 0 && (
                  <tr><td colSpan={4} className="text-center text-slate-600 py-6 text-xs">No positions</td></tr>
                )}
                {positions.map(p => (
                  <Tr key={p.id}>
                    <Td className="text-slate-400">{p.account}</Td>
                    <Td className="text-slate-200 font-medium">{p.symbol}</Td>
                    <Td className={Number(p.net_qty) >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                      {Number(p.net_qty).toLocaleString()}
                    </Td>
                    <Td className="text-slate-300">{Number(p.avg_cost).toFixed(2)}</Td>
                  </Tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  )
}

function Tr({ children, header }: { children: React.ReactNode; header?: boolean }) {
  return (
    <tr className={header ? 'border-b border-border' : 'border-b border-border/50 hover:bg-white/[0.02]'}>
      {children}
    </tr>
  )
}
function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-4 py-2.5 text-left text-xs text-slate-500 uppercase tracking-wider">{children}</th>
}
function Td({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-4 py-2.5 ${className}`}>{children}</td>
}

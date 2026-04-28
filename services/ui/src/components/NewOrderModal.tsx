import { useState, FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createOrder } from '../api'

const SYMBOLS = ['AAPL', 'MSFT', 'GOOG', 'TSLA', 'AMZN', 'NVDA']

interface Props {
  onClose: () => void
}

export default function NewOrderModal({ onClose }: Props) {
  const qc = useQueryClient()
  const [form, setForm] = useState({
    account: 'ACC1',
    symbol: 'AAPL',
    side: '1',
    ord_type: '2',
    quantity: '',
    price: '',
  })
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: createOrder,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['orders'] })
      onClose()
    },
    onError: (e: any) => {
      setError(e.response?.data?.detail ?? 'Failed to submit order')
    },
  })

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  const submit = (e: FormEvent) => {
    e.preventDefault()
    setError('')
    if (!form.quantity || Number(form.quantity) <= 0) {
      setError('Quantity must be positive')
      return
    }
    if (form.ord_type === '2' && (!form.price || Number(form.price) <= 0)) {
      setError('Price is required for limit orders')
      return
    }
    mutation.mutate({
      account: form.account,
      symbol: form.symbol,
      side: form.side,
      ord_type: form.ord_type,
      quantity: form.quantity,
      price: form.ord_type === '2' ? form.price : undefined,
    })
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-card border border-border rounded-xl w-full max-w-md p-6 shadow-2xl">
        <h2 className="text-lg font-semibold mb-5 text-slate-100">New Order</h2>

        <form onSubmit={submit} className="space-y-4">
          {/* Account */}
          <Field label="Account">
            <input
              className={input}
              value={form.account}
              onChange={e => set('account', e.target.value)}
              required
            />
          </Field>

          {/* Symbol */}
          <Field label="Symbol">
            <select className={input} value={form.symbol} onChange={e => set('symbol', e.target.value)}>
              {SYMBOLS.map(s => <option key={s}>{s}</option>)}
            </select>
          </Field>

          {/* Side */}
          <Field label="Side">
            <div className="flex gap-2">
              {[['1', 'Buy'], ['2', 'Sell']].map(([v, l]) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => set('side', v)}
                  className={`flex-1 py-2 rounded text-sm font-semibold transition-colors ${
                    form.side === v
                      ? v === '1' ? 'bg-emerald-600 text-white' : 'bg-red-600 text-white'
                      : 'bg-white/5 text-slate-400 hover:bg-white/10'
                  }`}
                >
                  {l}
                </button>
              ))}
            </div>
          </Field>

          {/* Order type */}
          <Field label="Order Type">
            <select className={input} value={form.ord_type} onChange={e => set('ord_type', e.target.value)}>
              <option value="2">Limit</option>
              <option value="1">Market</option>
            </select>
          </Field>

          {/* Quantity */}
          <Field label="Quantity">
            <input
              className={input}
              type="number"
              min="1"
              step="1"
              placeholder="100"
              value={form.quantity}
              onChange={e => set('quantity', e.target.value)}
              required
            />
          </Field>

          {/* Price — limit only */}
          {form.ord_type === '2' && (
            <Field label="Price">
              <input
                className={input}
                type="number"
                min="0.01"
                step="0.01"
                placeholder="150.00"
                value={form.price}
                onChange={e => set('price', e.target.value)}
                required
              />
            </Field>
          )}

          {error && <p className="text-red-400 text-sm">{error}</p>}

          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={mutation.isPending}
              className="flex-1 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded font-semibold text-sm transition-colors"
            >
              {mutation.isPending ? 'Submitting…' : 'Submit Order'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 bg-white/5 hover:bg-white/10 text-slate-300 rounded text-sm transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

const input = 'w-full bg-surface border border-border rounded px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-emerald-500'

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs text-slate-500 mb-1.5 uppercase tracking-wider">{label}</label>
      {children}
    </div>
  )
}

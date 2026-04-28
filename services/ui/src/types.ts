export interface Order {
  order_id: string
  cl_ord_id: string
  account: string
  symbol: string
  side: string        // "1"=Buy "2"=Sell
  ord_type: string    // "1"=Market "2"=Limit
  quantity: string
  price: string | null
  status: string      // "0"=New "1"=PartFill "2"=Filled "4"=Canceled "8"=Rejected "A"=Pending
  session_id: string | null
  created_at: string
  updated_at: string
}

export interface Execution {
  exec_id: string
  order_id: string
  exec_type: string
  last_qty: string
  last_px: string
  cum_qty: string
  avg_px: string
  leaves_qty: string
  created_at: string
}

export interface Position {
  id: string
  account: string
  symbol: string
  net_qty: string
  avg_cost: string
  updated_at: string
}

export interface CreateOrderPayload {
  account: string
  symbol: string
  side: string
  ord_type: string
  quantity: string
  price?: string
  cl_ord_id?: string
}

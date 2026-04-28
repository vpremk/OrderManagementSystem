import axios from 'axios'
import type { Order, Execution, Position, CreateOrderPayload } from './types'

const http = axios.create({ baseURL: '/api' })

export const fetchOrders = (params?: Record<string, string>) =>
  http.get<Order[]>('/orders', { params }).then(r => r.data)

export const fetchOrder = (id: string) =>
  http.get<Order>(`/orders/${id}`).then(r => r.data)

export const createOrder = (payload: CreateOrderPayload) =>
  http.post<{ order_id: string; cl_ord_id: string }>('/orders', payload).then(r => r.data)

export const cancelOrder = (order_id: string) =>
  http.delete<{ order_id: string; status: string }>(`/orders/${order_id}`).then(r => r.data)

export const fetchOrderExecutions = (order_id: string) =>
  http.get<Execution[]>(`/orders/${order_id}/executions`).then(r => r.data)

export const fetchExecutions = (params?: Record<string, string>) =>
  http.get<Execution[]>('/executions', { params }).then(r => r.data)

export const fetchPositions = (params?: Record<string, string>) =>
  http.get<Position[]>('/positions', { params }).then(r => r.data)

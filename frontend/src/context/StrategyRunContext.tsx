// context/StrategyRunContext.tsx
import React, { createContext, useContext, useState } from 'react'

export interface EquityCurvePoint {
  timestamp: number
  date: string          // ISO string as serialized by FastAPI/Pydantic
  price: Record<string, number>
  portfolio_value: number
  position: Record<string, number>
}

export interface StrategyResult {
  strategy: string
  signal_count: number
  notes: string | null
  history: EquityCurvePoint[]
}

// The exact body shape POSTed to /strategy/{strategy_name} — reused as the
// "strategy" field inside NoiseOHLCRequest / BootstrapRequest.
export interface GenericStrategyRequestBody {
  params: Record<string, any>
  enhancements: any
  portfolio: any
}

export interface LastStrategyRequest {
  strategyName: string // registry key, e.g. "cross_asset/equity_bonds"
  body: GenericStrategyRequestBody
}

interface StrategyRunState {
  loading: boolean
  error: string | null
  result: StrategyResult | null
  lastRequest: LastStrategyRequest | null
  setLoading: (v: boolean) => void
  setError: (v: string | null) => void
  setResult: (v: StrategyResult | null) => void
  setLastRequest: (v: LastStrategyRequest | null) => void
}

const StrategyRunContext = createContext<StrategyRunState | null>(null)

export const StrategyRunProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<StrategyResult | null>(null)
  const [lastRequest, setLastRequest] = useState<LastStrategyRequest | null>(null)

  return (
    <StrategyRunContext.Provider
      value={{ loading, error, result, lastRequest, setLoading, setError, setResult, setLastRequest }}
    >
      {children}
    </StrategyRunContext.Provider>
  )
}

export function useStrategyRun() {
  const ctx = useContext(StrategyRunContext)
  if (!ctx) throw new Error('useStrategyRun must be used within a StrategyRunProvider')
  return ctx
}

export interface BackendMetrics {
  final_portfolio_value: number
  total_return: number
  annual_return: number
  sharpe: number | null
  max_drawdown: number | null
  volatility: number | null
  annual_volatility: number
  information_ratio: number
  sortino_ratio: number
  consistency: {
    pos_month_pct: number
    pos_year_pct: number
    median_monthly_returns: number
    median_yearly_returns: number
    std_monthly_returns: number
    std_yearly_returns: number
  }
}
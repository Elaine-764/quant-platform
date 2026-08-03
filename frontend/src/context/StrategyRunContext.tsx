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

interface StrategyRunState {
  loading: boolean
  error: string | null
  result: StrategyResult | null
  setLoading: (v: boolean) => void
  setError: (v: string | null) => void
  setResult: (v: StrategyResult | null) => void
}

const StrategyRunContext = createContext<StrategyRunState | null>(null)

export const StrategyRunProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<StrategyResult | null>(null)

  return (
    <StrategyRunContext.Provider value={{ loading, error, result, setLoading, setError, setResult }}>
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
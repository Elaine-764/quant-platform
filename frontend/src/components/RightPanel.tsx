import React, { useState, useMemo, useEffect } from 'react'
import { useStrategyRun, type EquityCurvePoint, type BackendMetrics} from '../context/StrategyRunContext'
import Modal from './Modal'
import './RightPanel.css'

function computeBuyAndHold(history: EquityCurvePoint[], initialCash: number): number[] {
  if (history.length === 0) return []
  const assets = Object.keys(history[0].price)
  const perAssetCash = initialCash / assets.length
  const shares: Record<string, number> = {}
  for (const a of assets) {
    shares[a] = history[0].price[a] > 0 ? perAssetCash / history[0].price[a] : 0
  }
  return history.map((h) => assets.reduce((sum, a) => sum + shares[a] * h.price[a], 0))
}

function EquityCurveChart({
  history,
  buyHoldValues,
  showBuyHold,
  width = 600,
  height = 375,
}: {
  history: EquityCurvePoint[]
  buyHoldValues: number[]
  showBuyHold: boolean
  width?: number
  height?: number
}) {
  const margin = { top: 32, right: 16, bottom: 24, left: 56 }
  const innerWidth = width - margin.left - margin.right
  const innerHeight = height - margin.top - margin.bottom

  if (history.length === 0) {
    return (
      <div className="chart-placeholder">
        <div className="chart-placeholder-content">
          <svg viewBox={`0 0 ${width} ${height}`} className="chart-svg">
            <polyline
              fill="none"
              stroke="#bfdbfe"
              strokeWidth={2}
              points="0,150 50,120 100,110 150,90 200,70 250,80 300,60 350,40 400,55 450,30 500,20 550,10 600,5"
            />
          </svg>
          <p className="chart-placeholder-text">Run strategy to view equity curve</p>
        </div>
      </div>
    )
  }

  const strategyValues = history.map((h) => h.portfolio_value)
  const allValues = showBuyHold ? [...strategyValues, ...buyHoldValues] : strategyValues
  const minV = Math.min(...allValues)
  const maxV = Math.max(...allValues)
  const rangeV = maxV - minV || 1

  // x-axis now keyed off real dates (see backend section below)
  const dateNums = history.map((h) => new Date(h.date).getTime())
  const minT = dateNums[0]
  const maxT = dateNums[dateNums.length - 1]
  const rangeT = maxT - minT || 1

  const xFor = (t: number) => margin.left + ((t - minT) / rangeT) * innerWidth
  const yFor = (v: number) => margin.top + innerHeight - ((v - minV) / rangeV) * innerHeight

  const strategyPoints = history
    .map((h, i) => `${xFor(dateNums[i]).toFixed(1)},${yFor(h.portfolio_value).toFixed(1)}`)
    .join(' ')

  const buyHoldPoints = buyHoldValues
    .map((v, i) => `${xFor(dateNums[i]).toFixed(1)},${yFor(v).toFixed(1)}`)
    .join(' ')

  const yTicks = Array.from({ length: 4 }, (_, i) => minV + (rangeV * i) / 3)
  const xTickIdxs = Array.from({ length: 5 }, (_, i) => Math.round((i / 4) * (history.length - 1)))

  const formatValue = (v: number) => (v >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v.toFixed(0)}`)
  const formatDate = (ms: number) => new Date(ms).toLocaleDateString(undefined, { year: '2-digit', month: 'short' })

  return (
    <div className="chart-container-fluid">
      <svg viewBox={`0 0 ${width} ${height}`} className="chart-svg-fluid">
        {/* Dynamic SVG Legend positioned at the top left */}
        <g transform={`translate(${margin.left}, 16)`} className="chart-legend-text">
          {/* Strategy Indicator */}
          <line x1={0} y1={0} x2={20} y2={0} stroke="#60a5fa" strokeWidth={2} />
          <text x={26} y={4} textAnchor="start">Strategy</text>

          {/* Buy & Hold Indicator */}
          {showBuyHold && (
            <g transform="translate(100, 0)">
              <line x1={0} y1={0} x2={20} y2={0} stroke="#f59e0b" strokeDasharray="4 3" strokeWidth={1.5} />
              <text x={26} y={4} textAnchor="start">Buy & Hold</text>
            </g>
          )}
        </g>

        {/* Grid Lines & Boundaries */}
        {yTicks.map((v, i) => (
          <line key={`grid-y-${i}`} x1={margin.left} x2={width - margin.right} y1={yFor(v)} y2={yFor(v)} stroke="rgba(0,0,0,0.1)" strokeWidth={1} />
        ))}

        <line x1={margin.left} x2={margin.left} y1={margin.top} y2={margin.top + innerHeight} stroke="rgba(0,0,0,0.3)" strokeWidth={1} />
        <line x1={margin.left} x2={width - margin.right} y1={margin.top + innerHeight} y2={margin.top + innerHeight} stroke="rgba(0,0,0,0.3)" strokeWidth={1} />

        {/* Labels */}
        {yTicks.map((v, i) => (
          <text key={`ylabel-${i}`} x={margin.left - 6} y={yFor(v)} textAnchor="end" dominantBaseline="middle" className="chart-axis-label">
            {formatValue(v)}
          </text>
        ))}

        {xTickIdxs.map((idx, i) => (
          <text key={`xlabel-${i}`} x={xFor(dateNums[idx])} y={margin.top + innerHeight + 16} textAnchor="middle" className="chart-axis-label">
            {formatDate(dateNums[idx])}
          </text>
        ))}

        {/* Chart Lines */}
        {showBuyHold && (
          <polyline fill="none" stroke="#f59e0b" strokeDasharray="4 3" strokeWidth={1.5} points={buyHoldPoints} />
        )}
        <polyline fill="none" stroke="#60a5fa" strokeWidth={2} points={strategyPoints} />
      </svg>
    </div>
  )
}

function computeMetrics(history: { portfolio_value: number }[]) {
  if (history.length === 0) {
    return { finalValue: null, totalReturn: null, sharpe: null, maxDrawdown: null }
  }

  const values = history.map((h) => h.portfolio_value)
  const initial = values[0]
  const final = values[values.length - 1]
  const totalReturn = initial !== 0 ? (final - initial) / initial : null

  const returns: number[] = []
  for (let i = 1; i < values.length; i++) {
    if (values[i - 1] !== 0) returns.push((values[i] - values[i - 1]) / values[i - 1])
  }
  let sharpe: number | null = null
  if (returns.length > 1) {
    const mean = returns.reduce((a, b) => a + b, 0) / returns.length
    const variance = returns.reduce((a, b) => a + (b - mean) ** 2, 0) / (returns.length - 1)
    const std = Math.sqrt(variance)
    sharpe = std !== 0 ? (mean / std) * Math.sqrt(252) : null // annualized, assuming daily bars
  }

  let peak = values[0]
  let maxDrawdown = 0
  for (const v of values) {
    if (v > peak) peak = v
    const dd = peak !== 0 ? (peak - v) / peak : 0
    if (dd > maxDrawdown) maxDrawdown = dd
  }

  return { finalValue: final, totalReturn, sharpe, maxDrawdown }
}

function formatPct(v: number | null) {
  return v === null ? '—' : `${(v * 100).toFixed(2)}%`
}

function formatNumber(v: number | null) {
  return v === null ? '—' : v.toFixed(2)
}

function formatCurrency(v: number | null) {
  return v === null ? '—' : `$${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
}

export default function RightPanel() {
  const { loading: strategyLoading, error: strategyError, result } = useStrategyRun()
  const history = result?.history ?? []

  // State elements to manage backend API metrics calculations
  const [metrics, setMetrics] = useState<BackendMetrics | null>(null)
  const [metricsLoading, setMetricsLoading] = useState(false)
  const [metricsError, setMetricsError] = useState<string | null>(null)

  const [showBuyHold, setShowBuyHold] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const initialCash = history[0]?.portfolio_value ?? 100000 // rough proxy; see note below
  const buyHoldValues = useMemo(() => computeBuyAndHold(history, initialCash), [history, initialCash])

  useEffect(() => {
    if (history.length === 0) {
      setMetrics(null)
      return
    }

    async function fetchBackendMetrics() {
      setMetricsLoading(true)
      setMetricsError(null)
      try {
        const response = await fetch('/api/backtest/metrics', {
          method: 'POST',
          headers: {
            'accept': 'application/json',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            strategy: (result as any)?.strategy_name ?? (result as any)?.strategyName ?? 'Default Strategy',
            signal_count: (result as any)?.signal_count ?? (result as any)?.signalCount ?? history.length,
            notes: null,
            history: history, 
          }),
        })

        if (!response.ok) {
          throw new Error(`Server metric processing error status: ${response.status}`)
        }

        const data: BackendMetrics = await response.json()
        setMetrics(data)
      } catch (err: any) {
        setMetricsError(err.message || 'Failed fetching metrics computation pipeline.')
      } finally {
        setMetricsLoading(false)
      }
    }

    fetchBackendMetrics()
  }, [history, result])

  return (
     <aside className="right-panel">
      <div className="pane-stack">
        <div className="pane">
          <div className="pane-header">
            <h4>Equity Curve</h4>
            <button className="btn ghost small" onClick={() => setExpanded(true)} disabled={history.length === 0}>
              Expand
            </button>
          </div>
          <div className="chart-wrap">
            <EquityCurveChart history={history} buyHoldValues={buyHoldValues} showBuyHold={showBuyHold} />
            {(strategyLoading || metricsLoading) && (
              <div className="chart-loading-overlay">
                <div className="spinner" />
                <span>{strategyLoading ? 'Running strategy…' : 'Computing backend metrics…'}</span>
              </div>
            )}
          </div>
          <div className="chart-controls">
            <label>
              <input type="checkbox" checked={showBuyHold} onChange={(e) => setShowBuyHold(e.target.checked)} /> Show buy & hold
            </label>
            <label>
              <input type="checkbox" /> Regime shading
            </label>
          </div>
          {(strategyError || metricsError) && (
            <div className="run-error">{strategyError || metricsError}</div>
          )}
        </div>

        <div className="pane metrics-pane">
          <h4>Metrics</h4>
          {metrics ? (
            <div className="metrics-grid">
              <div className="metrics-item"><strong>Final Value:</strong> {formatCurrency(metrics.final_portfolio_value)}</div>
              <div className="metrics-item"><strong>Total Return:</strong> {formatPct(metrics.total_return)}</div>
              <div className="metrics-item"><strong>Annual Return:</strong> {formatPct(metrics.annual_return)}</div>
              <div className="metrics-item"><strong>Volatility (Ann):</strong> {formatPct(metrics.annual_volatility)}</div>
              <div className="metrics-item"><strong>Sharpe Ratio:</strong> {formatNumber(metrics.sharpe)}</div>
              <div className="metrics-item"><strong>Sortino Ratio:</strong> {formatNumber(metrics.sortino_ratio)}</div>
              <div className="metrics-item"><strong>Max Drawdown:</strong> {formatPct(metrics.max_drawdown)}</div>
              <div className="metrics-item"><strong>Information Ratio:</strong> {formatNumber(metrics.information_ratio)}</div>
              
              <div className="metrics-section-divider">
                <h4 className="metrics-section-title">Consistency Parameters</h4>
              </div>
              
              <div className="metrics-item"><strong>Profitable Months:</strong> {formatPct(metrics.consistency.pos_month_pct)}</div>
              <div className="metrics-item"><strong>Profitable Years:</strong> {formatPct(metrics.consistency.pos_year_pct)}</div>
              <div className="metrics-item"><strong>Median Month Ret:</strong> {formatPct(metrics.consistency.median_monthly_returns)}</div>
              <div className="metrics-item"><strong>Std Dev Month Ret:</strong> {formatPct(metrics.consistency.std_monthly_returns)}</div>
            </div>
          ) : (
            <div className="metrics-placeholder">
              {metricsLoading ? 'Calculating backend parameters...' : 'No historical metrics generated.'}
            </div>
          )}
        </div>
      </div>

      {expanded && (
        <Modal onClose={() => setExpanded(false)}>
          <h4>Equity Curve</h4>
          <EquityCurveChart history={history} buyHoldValues={buyHoldValues} showBuyHold={showBuyHold} width={1000} height={625} />
        </Modal>
      )}

      <div className="bottom-half">
        <div className="pane">
          <h4>Robustness Tests</h4>
          <div className="tests-list">
            <div className="test-item">
              <div className="test-title">Bootstrap CI</div>
              <div className="test-actions">
                <button className="btn small">Adjust params</button>
                <button className="btn small">Rerun</button>
              </div>
            </div>
            <div className="test-item">
              <div className="test-title">Noise Injection</div>
              <div className="test-actions">
                <button className="btn small">Adjust params</button>
                <button className="btn small">Rerun</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </aside>
  )
}
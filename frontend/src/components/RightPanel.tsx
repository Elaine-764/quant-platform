import React, { useState, useMemo, useEffect } from 'react'
import { useStrategyRun, type EquityCurvePoint, type BackendMetrics, type LastStrategyRequest} from '../context/StrategyRunContext'
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

function formatPct(v: number | null) {
  return v === null ? '—' : `${(v * 100).toFixed(2)}%`
}

function formatNumber(v: number | null) {
  return v === null ? '—' : v.toFixed(2)
}

function formatCurrency(v: number | null) {
  return v === null ? '—' : `$${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
}

interface NoiseParams {
  noise_factor: number
  vol_window: number
  metric: string
  epsilon: number
  confidence: number
  k: number
}

interface BootstrapParams {
  n_bootstrap: number
  metric: string
  null_value: number
  min_threshold: number | null
  avg_block_length: number
  epsilon: number
  confidence: number
  k: number
}

const DEFAULT_NOISE_PARAMS: NoiseParams = {
  noise_factor: 0.05,
  vol_window: 20,
  metric: 'sharpe',
  epsilon: 0.01,
  confidence: 0.95,
  k: 30,
}

const DEFAULT_BOOTSTRAP_PARAMS: BootstrapParams = {
  n_bootstrap: 5000,
  metric: 'sharpe',
  null_value: 0.0,
  min_threshold: null,
  avg_block_length: 20,
  epsilon: 0.01,
  confidence: 0.95,
  k: 30,
}

// Generic renderer for whatever shape the backend returns — these response
// models weren't shown, so this renders any flat/nested numeric result sensibly
// without assuming exact field names.
function ResultSummary({ result }: { result: Record<string, any> }) {
  return (
    <div className="robustness-result">
      {Object.entries(result).map(([key, value]) => (
        <div key={key} className="robustness-result-row">
          <span className="robustness-result-key">{key.replace(/_/g, ' ')}</span>
          <span className="robustness-result-value">
            {typeof value === 'number' ? value.toFixed(4) : JSON.stringify(value)}
          </span>
        </div>
      ))}
    </div>
  )
}

function NoiseParamsForm({ params, onChange }: { params: NoiseParams; onChange: (p: NoiseParams) => void }) {
  return (
    <div className="params">
      <label className="param-row">
        <span className="param-label">noise factor</span>
        <input className="full" type="number" step="0.01" value={params.noise_factor}
          onChange={(e) => onChange({ ...params, noise_factor: Number(e.target.value) })} />
      </label>
      <label className="param-row">
        <span className="param-label">vol window</span>
        <input className="full" type="number" value={params.vol_window}
          onChange={(e) => onChange({ ...params, vol_window: Number(e.target.value) })} />
      </label>
      <label className="param-row">
        <span className="param-label">metric</span>
        <select className="full" value={params.metric} onChange={(e) => onChange({ ...params, metric: e.target.value })}>
          <option value="sharpe">sharpe</option>
          <option value="sortino">sortino</option>
          <option value="total_return">total_return</option>
        </select>
      </label>
      <label className="param-row">
        <span className="param-label">epsilon</span>
        <input className="full" type="number" step="0.001" value={params.epsilon}
          onChange={(e) => onChange({ ...params, epsilon: Number(e.target.value) })} />
      </label>
      <label className="param-row">
        <span className="param-label">confidence</span>
        <input className="full" type="number" step="0.01" min={0} max={1} value={params.confidence}
          onChange={(e) => onChange({ ...params, confidence: Number(e.target.value) })} />
      </label>
      <label className="param-row">
        <span className="param-label">k</span>
        <input className="full" type="number" value={params.k}
          onChange={(e) => onChange({ ...params, k: Number(e.target.value) })} />
      </label>
    </div>
  )
}

function BootstrapParamsForm({ params, onChange }: { params: BootstrapParams; onChange: (p: BootstrapParams) => void }) {
  return (
    <div className="params">
      <label className="param-row">
        <span className="param-label">n bootstrap</span>
        <input className="full" type="number" value={params.n_bootstrap}
          onChange={(e) => onChange({ ...params, n_bootstrap: Number(e.target.value) })} />
      </label>
      <label className="param-row">
        <span className="param-label">metric</span>
        <select className="full" value={params.metric} onChange={(e) => onChange({ ...params, metric: e.target.value })}>
          <option value="sharpe">sharpe</option>
          <option value="sortino">sortino</option>
          <option value="total_return">total_return</option>
        </select>
      </label>
      <label className="param-row">
        <span className="param-label">null value</span>
        <input className="full" type="number" step="0.01" value={params.null_value}
          onChange={(e) => onChange({ ...params, null_value: Number(e.target.value) })} />
      </label>
      <label className="param-row">
        <span className="param-label">min threshold</span>
        <input className="full" type="number" step="0.01" value={params.min_threshold ?? ''}
          placeholder="none"
          onChange={(e) => onChange({ ...params, min_threshold: e.target.value === '' ? null : Number(e.target.value) })} />
      </label>
      <label className="param-row">
        <span className="param-label">avg block length</span>
        <input className="full" type="number" value={params.avg_block_length}
          onChange={(e) => onChange({ ...params, avg_block_length: Number(e.target.value) })} />
      </label>
      <label className="param-row">
        <span className="param-label">epsilon</span>
        <input className="full" type="number" step="0.001" value={params.epsilon}
          onChange={(e) => onChange({ ...params, epsilon: Number(e.target.value) })} />
      </label>
      <label className="param-row">
        <span className="param-label">confidence</span>
        <input className="full" type="number" step="0.01" min={0} max={1} value={params.confidence}
          onChange={(e) => onChange({ ...params, confidence: Number(e.target.value) })} />
      </label>
      <label className="param-row">
        <span className="param-label">k</span>
        <input className="full" type="number" value={params.k}
          onChange={(e) => onChange({ ...params, k: Number(e.target.value) })} />
      </label>
    </div>
  )
}

function useRobustnessTest<TParams>(endpoint: string, buildBody: (lastReq: LastStrategyRequest, params: TParams) => any) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<Record<string, any> | null>(null)

  async function run(lastRequest: LastStrategyRequest | null, params: TParams) {
    if (!lastRequest) {
      setError('Run a strategy first — there is no strategy configuration to test.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`/api${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildBody(lastRequest, params)),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail ? JSON.stringify(err.detail) : `Request failed (${res.status})`)
      }
      setResult(await res.json())
    } catch (e: any) {
      setError(e.message ?? 'Robustness test failed')
    } finally {
      setLoading(false)
    }
  }

  return { loading, error, result, run }
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
  
  const { lastRequest } = useStrategyRun()

  const [noiseParams, setNoiseParams] = useState<NoiseParams>(DEFAULT_NOISE_PARAMS)
  const [bootstrapParams, setBootstrapParams] = useState<BootstrapParams>(DEFAULT_BOOTSTRAP_PARAMS)
  const [showNoiseParamsModal, setShowNoiseParamsModal] = useState(false)
  const [showBootstrapParamsModal, setShowBootstrapParamsModal] = useState(false)

  const noiseTest = useRobustnessTest('/backtest/montecarlo/noise_ohlc', (lastReq, params: NoiseParams) => ({
    strategy: lastReq.body,
    strategy_name: lastReq.strategyName,
    ...params,
  }))

  const bootstrapTest = useRobustnessTest('/backtest/montecarlo/bootstrap', (lastReq, params: BootstrapParams) => ({
    strategy: lastReq.body,
    strategy_name: lastReq.strategyName,
    ...params,
  }))


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
          {!lastRequest && (
            <div className="metrics-placeholder">Run a strategy first to enable robustness tests.</div>
          )}
          <div className="tests-list">
            <div className="test-item">
              <div className="test-title">Bootstrap CI</div>
              <div className="test-actions">
                <button className="btn small" onClick={() => setShowBootstrapParamsModal(true)}>
                  Adjust params
                </button>
                <button
                  className="btn small"
                  disabled={!lastRequest || bootstrapTest.loading}
                  onClick={() => bootstrapTest.run(lastRequest, bootstrapParams)}
                >
                  {bootstrapTest.loading ? 'Running…' : 'Rerun'}
                </button>
              </div>
              {bootstrapTest.error && <div className="run-error">{bootstrapTest.error}</div>}
              {bootstrapTest.result && <ResultSummary result={bootstrapTest.result} />}
            </div>

            <div className="test-item">
              <div className="test-title">Noise Injection</div>
              <div className="test-actions">
                <button className="btn small" onClick={() => setShowNoiseParamsModal(true)}>
                  Adjust params
                </button>
                <button
                  className="btn small"
                  disabled={!lastRequest || noiseTest.loading}
                  onClick={() => noiseTest.run(lastRequest, noiseParams)}
                >
                  {noiseTest.loading ? 'Running…' : 'Rerun'}
                </button>
              </div>
              {noiseTest.error && <div className="run-error">{noiseTest.error}</div>}
              {noiseTest.result && <ResultSummary result={noiseTest.result} />}
            </div>
          </div>
        </div>
      </div>

      {showBootstrapParamsModal && (
        <Modal onClose={() => setShowBootstrapParamsModal(false)}>
          <h4>Bootstrap CI — parameters</h4>
          <BootstrapParamsForm params={bootstrapParams} onChange={setBootstrapParams} />
        </Modal>
      )}

      {showNoiseParamsModal && (
        <Modal onClose={() => setShowNoiseParamsModal(false)}>
          <h4>Noise Injection — parameters</h4>
          <NoiseParamsForm params={noiseParams} onChange={setNoiseParams} />
        </Modal>
      )}
    </aside>
  )
}
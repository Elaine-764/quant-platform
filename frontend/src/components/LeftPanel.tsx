import React, { useMemo, useState } from 'react'
import { useRegistry } from '../context/StrategyRegistry'
import { useStrategyRun } from '../context/StrategyRunContext'
import { useAssetOptions } from '../hooks/useAssetOptions'
import type { EnhancementMeta, ParamMeta } from '../types'
import './LeftPanel.css'

type ParamValues = Record<string, string | number>

interface EnhancementInstance {
  instanceId: string
  enhancementId: string
  values: ParamValues
}

interface AssetCostInstance {
  instanceId: string
  asset: string
  fixed: number
  pct: number
}

function defaultsFor(params: ParamMeta[]): ParamValues {
  const values: ParamValues = {}
  for (const p of params) {
    if (p.type === 'number') values[p.name] = p.default ?? 0
    else if (p.type === 'asset') values[p.name] = p.default ?? ''
    else values[p.name] = p.default ?? ''
  }
  return values
}

// Renders a single param field, resolving asset params to a fetched dropdown.
function ParamField({
  param,
  value,
  onChange,
}: {
  param: ParamMeta
  value: string | number
  onChange: (name: string, value: string | number) => void
}) {
  if (param.type === 'asset') {
    return <AssetParamField param={param} value={value as string} onChange={onChange} />
  }
  return (
    <label className="param-row">
      <span className="param-label">{param.name}</span>
      <input
        className="full"
        type={param.type === 'number' ? 'number' : 'text'}
        value={value}
        onChange={(e) =>
          onChange(param.name, param.type === 'number' ? Number(e.target.value) : e.target.value)
        }
      />
    </label>
  )
}

function AssetParamField({
  param,
  value,
  onChange,
}: {
  param: Extract<ParamMeta, { type: 'asset' }>
  value: string
  onChange: (name: string, value: string) => void
}) {
  const { options, loading, error } = useAssetOptions(param.assetClass)

  return (
    <label className="param-row">
      <span className="param-label">{param.name}</span>
      {error ? (
        <span className="param-error">{error}</span>
      ) : (
        <select
          className="full"
          value={value}
          disabled={loading}
          onChange={(e) => onChange(param.name, e.target.value)}
        >
          <option value="" disabled>
            {loading ? 'Loading…' : 'Select…'}
          </option>
          {options.map((ticker) => (
            <option key={ticker} value={ticker}>
              {ticker}
            </option>
          ))}
        </select>
      )}
    </label>
  )
}

// One added filter/sizer block: dropdown already chosen, render its own params inline.
function EnhancementBlock({
  meta,
  instance,
  onChangeParam,
  onRemove,
}: {
  meta: EnhancementMeta
  instance: EnhancementInstance
  onChangeParam: (instanceId: string, name: string, value: string | number) => void
  onRemove: (instanceId: string) => void
}) {
  return (
    <div className="enh-block">
      <div className="enh-block-header">
        <span>{meta.title}</span>
        <button className="btn ghost small" onClick={() => onRemove(instance.instanceId)}>
          Remove
        </button>
      </div>
      <div className="enh-block-params">
        {meta.params.map((p) => (
          <ParamField
            key={p.name}
            param={p}
            value={instance.values[p.name]}
            onChange={(name, value) => onChangeParam(instance.instanceId, name, value)}
          />
        ))}
      </div>
    </div>
  )
}

// Shared "pick from dropdown, click add" control for filters and sizers.
function AddEnhancementRow({
  candidates,
  onAdd,
}: {
  candidates: EnhancementMeta[]
  onAdd: (enhancementId: string) => void
}) {
  const [selected, setSelected] = useState(candidates[0]?.id ?? '')

  if (candidates.length === 0) return null

  return (
    <div className="add-enh-row">
      <select className="full" value={selected} onChange={(e) => setSelected(e.target.value)}>
        {candidates.map((c) => (
          <option key={c.id} value={c.id}>
            {c.title}
          </option>
        ))}
      </select>
      <button className="btn ghost small" onClick={() => selected && onAdd(selected)}>
        + Add
      </button>
    </div>
  )
}

// One per-asset transaction-cost override: asset dropdown (from assets chosen in
// the strategy params above) + fixed/pct cost fields.
function AssetCostBlock({
  instance,
  availableAssets,
  onChange,
  onRemove,
}: {
  instance: AssetCostInstance
  availableAssets: string[]
  onChange: (instanceId: string, patch: Partial<AssetCostInstance>) => void
  onRemove: (instanceId: string) => void
}) {
  return (
    <div className="enh-block">
      <div className="enh-block-header">
        <span>Per-asset cost override</span>
        <button className="btn ghost small" onClick={() => onRemove(instance.instanceId)}>
          Remove
        </button>
      </div>
      <div className="enh-block-params">
        <label className="param-row">
          <span className="param-label">asset</span>
          <select
            className="full"
            value={instance.asset}
            onChange={(e) => onChange(instance.instanceId, { asset: e.target.value })}
          >
            <option value="" disabled>
              {availableAssets.length === 0 ? 'Select an asset above first…' : 'Select…'}
            </option>
            {availableAssets.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
        <label className="param-row">
          <span className="param-label">fixed</span>
          <input
            className="full"
            type="number"
            value={instance.fixed}
            onChange={(e) => onChange(instance.instanceId, { fixed: Number(e.target.value) })}
          />
        </label>
        <label className="param-row">
          <span className="param-label">pct</span>
          <input
            className="full"
            type="number"
            step="0.0001"
            value={instance.pct}
            onChange={(e) => onChange(instance.instanceId, { pct: Number(e.target.value) })}
          />
        </label>
      </div>
    </div>
  )
}

let instanceCounter = 0
const nextInstanceId = () => `inst_${++instanceCounter}`

export default function LeftPanel() {
    const { strategies, enhancements } = useRegistry()
    const { loading, error: runError, setLoading, setError: setRunError, setResult } = useStrategyRun()


  const [selectedStrategyId, setSelectedStrategyId] = useState(strategies[0]?.id ?? '')
  const strategy = useMemo(
    () => strategies.find((s) => s.id === selectedStrategyId),
    [strategies, selectedStrategyId]
  )

  const [paramValues, setParamValues] = useState<ParamValues>(() =>
    strategy ? defaultsFor(strategy.params) : {}
  )
  const [filters, setFilters] = useState<EnhancementInstance[]>([])
  const [sizers, setSizers] = useState<EnhancementInstance[]>([])

  // Portfolio state
  const [initialCash, setInitialCash] = useState<number>(100000)
  const [txFixed, setTxFixed] = useState<number>(0)
  const [txPct, setTxPct] = useState<number>(0)
  const [txSlippagePct, setTxSlippagePct] = useState<number>(0)
  const [assetCosts, setAssetCosts] = useState<AssetCostInstance[]>([])

  const filterCandidates = enhancements.filter((e) => e.category === 'filter')
  const sizerCandidates = enhancements.filter((e) => e.category === 'position_sizer')

  // Assets currently chosen in the strategy's own asset-type params (e.g. "equity", "bond").
  // Drives the dropdown options for per-asset cost overrides below.
  const selectedAssets = useMemo(() => {
    if (!strategy) return []
    const assetParamNames = strategy.params.filter((p) => p.type === 'asset').map((p) => p.name)
    const values = assetParamNames.map((name) => paramValues[name]).filter((v): v is string => !!v)
    return Array.from(new Set(values))
  }, [strategy, paramValues])

  function handleStrategyChange(id: string) {
    setSelectedStrategyId(id)
    const next = strategies.find((s) => s.id === id)
    setParamValues(next ? defaultsFor(next.params) : {})
    setAssetCosts([]) // asset choices are about to change; stale overrides would point nowhere
  }

  function handleParamChange(name: string, value: string | number) {
    setParamValues((prev) => ({ ...prev, [name]: value }))
  }

  function addEnhancement(category: 'filter' | 'position_sizer', enhancementId: string) {
    const meta = enhancements.find((e) => e.id === enhancementId)
    if (!meta) return
    const instance: EnhancementInstance = {
      instanceId: nextInstanceId(),
      enhancementId,
      values: defaultsFor(meta.params),
    }
    if (category === 'filter') setFilters((prev) => [...prev, instance])
    else setSizers((prev) => [...prev, instance])
  }

  function removeEnhancement(category: 'filter' | 'position_sizer', instanceId: string) {
    if (category === 'filter') setFilters((prev) => prev.filter((f) => f.instanceId !== instanceId))
    else setSizers((prev) => prev.filter((s) => s.instanceId !== instanceId))
  }

  function updateEnhancementParam(
    category: 'filter' | 'position_sizer',
    instanceId: string,
    name: string,
    value: string | number
  ) {
    const updater = (prev: EnhancementInstance[]) =>
      prev.map((inst) =>
        inst.instanceId === instanceId ? { ...inst, values: { ...inst.values, [name]: value } } : inst
      )
    if (category === 'filter') setFilters(updater)
    else setSizers(updater)
  }

  function addAssetCost() {
    setAssetCosts((prev) => [
      ...prev,
      { instanceId: nextInstanceId(), asset: selectedAssets[0] ?? '', fixed: 0, pct: 0 },
    ])
  }

  function removeAssetCost(instanceId: string) {
    setAssetCosts((prev) => prev.filter((a) => a.instanceId !== instanceId))
  }

  function updateAssetCost(instanceId: string, patch: Partial<AssetCostInstance>) {
    setAssetCosts((prev) => prev.map((a) => (a.instanceId === instanceId ? { ...a, ...patch } : a)))
  }

  function resetParams() {
    if (strategy) setParamValues(defaultsFor(strategy.params))
    setFilters([])
    setSizers([])
    setInitialCash(100000)
    setTxFixed(0)
    setTxPct(0)
    setTxSlippagePct(0)
    setAssetCosts([])
    setRunError(null)
  }

  async function runStrategy() {
    if (!strategy) return

    if (!(initialCash > 0)) {
      setRunError('Initial cash must be a positive number.')
      return
    }

    setLoading(true)
    setRunError(null)
    setResult(null) // clear stale results from a previous run while the new one is in flight
    try {
      const by_asset: Record<string, { fixed: number; pct: number }> = {}
      for (const ac of assetCosts) {
        if (ac.asset) by_asset[ac.asset] = { fixed: ac.fixed, pct: ac.pct }
      }

      const body = {
        params: paramValues,
        enhancements: {
          filters: filters.map((f) => ({ ...f.values, name: f.values.name ?? f.enhancementId })),
          position_sizers: sizers.map((s) => ({ name: s.enhancementId, sizer: s.values })),
        },
        portfolio: {
          initial_cash: initialCash,
          transaction_costs: {
            fixed: txFixed,
            pct: txPct,
            slippage_pct: txSlippagePct,
            by_asset,
          },
        },
      }
      const res = await fetch(`/api${strategy.endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail ? JSON.stringify(err.detail) : `Request failed (${res.status})`)
      }
      const result = await res.json()
      setResult(result)
    } catch (e: any) {
      setRunError(e.message ?? 'Failed to run strategy')
    } finally {
      setLoading(false)
    }
  }

  return (
    <aside className="left-panel">
      <section className="section">
        <h3>Strategy</h3>
        <select className="full" value={selectedStrategyId} onChange={(e) => handleStrategyChange(e.target.value)}>
          {strategies.map((s) => (
            <option key={s.id} value={s.id}>
              {s.title}
            </option>
          ))}
        </select>
      </section>

      <section className="section">
        <h3>Parameters</h3>
        <div className="params">
          {strategy?.params.map((p) => (
            <ParamField key={p.name} param={p} value={paramValues[p.name]} onChange={handleParamChange} />
          ))}
        </div>
      </section>

      <section className="section">
        <h3>Filters</h3>
        <div className="enh-list">
          {filters.map((inst) => {
            const meta = enhancements.find((e) => e.id === inst.enhancementId)
            if (!meta) return null
            return (
              <EnhancementBlock
                key={inst.instanceId}
                meta={meta}
                instance={inst}
                onChangeParam={(id, name, value) => updateEnhancementParam('filter', id, name, value)}
                onRemove={(id) => removeEnhancement('filter', id)}
              />
            )
          })}
        </div>
        <AddEnhancementRow candidates={filterCandidates} onAdd={(id) => addEnhancement('filter', id)} />
      </section>

      <section className="section">
        <h3>Position Sizers</h3>
        <div className="enh-list">
          {sizers.map((inst) => {
            const meta = enhancements.find((e) => e.id === inst.enhancementId)
            if (!meta) return null
            return (
              <EnhancementBlock
                key={inst.instanceId}
                meta={meta}
                instance={inst}
                onChangeParam={(id, name, value) => updateEnhancementParam('position_sizer', id, name, value)}
                onRemove={(id) => removeEnhancement('position_sizer', id)}
              />
            )
          })}
        </div>
        <AddEnhancementRow candidates={sizerCandidates} onAdd={(id) => addEnhancement('position_sizer', id)} />
      </section>

      <section className="section">
        <h3>Portfolio</h3>
        <div className="params">
          <label className="param-row">
            <span className="param-label">initial cash</span>
            <input
              className="full"
              type="number"
              min={0}
              step="any"
              value={initialCash}
              onChange={(e) => setInitialCash(Number(e.target.value))}
            />
          </label>
          {initialCash <= 0 && <span className="param-error">Initial cash must be positive.</span>}

          <label className="param-row">
            <span className="param-label">transaction cost — fixed</span>
            <input className="full" type="number" value={txFixed} onChange={(e) => setTxFixed(Number(e.target.value))} />
          </label>
          <label className="param-row">
            <span className="param-label">transaction cost — pct</span>
            <input
              className="full"
              type="number"
              step="0.0001"
              value={txPct}
              onChange={(e) => setTxPct(Number(e.target.value))}
            />
          </label>
          <label className="param-row">
            <span className="param-label">slippage pct</span>
            <input
              className="full"
              type="number"
              step="0.0001"
              value={txSlippagePct}
              onChange={(e) => setTxSlippagePct(Number(e.target.value))}
            />
          </label>
        </div>

        <h4 className="subsection-label">Per-asset cost overrides</h4>
        <div className="enh-list">
          {assetCosts.map((inst) => (
            <AssetCostBlock
              key={inst.instanceId}
              instance={inst}
              availableAssets={selectedAssets}
              onChange={updateAssetCost}
              onRemove={removeAssetCost}
            />
          ))}
        </div>
        <div className="add-enh-row">
          <button className="btn ghost small" onClick={addAssetCost} disabled={selectedAssets.length === 0}>
            + Add asset override
          </button>
        </div>
        {selectedAssets.length === 0 && (
          <span className="param-error">Select assets in Parameters above to enable per-asset overrides.</span>
        )}
      </section>

      {runError && <div className="run-error">{runError}</div>}

      <div className="panel-actions">
        <button className="btn ghost" onClick={resetParams} disabled={loading}>
          Reset params
        </button>
        <button className="btn primary" onClick={runStrategy} disabled={loading || !strategy}>
          {loading ? 'Running…' : 'Run strategy'}
        </button>
      </div>
    </aside>
  )
}
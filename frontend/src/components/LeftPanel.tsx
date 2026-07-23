import React, { useMemo, useState } from 'react'
import { useRegistry } from '../context/StrategyRegistry'
import { useAssetOptions } from '../hooks/useAssetOptions'
import type { EnhancementMeta, ParamMeta } from '../types'
import './LeftPanel.css'

type ParamValues = Record<string, string | number>

interface EnhancementInstance {
  instanceId: string
  enhancementId: string
  values: ParamValues
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

let instanceCounter = 0
const nextInstanceId = () => `inst_${++instanceCounter}`

export default function LeftPanel() {
  const { strategies, enhancements } = useRegistry()

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
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)

  const filterCandidates = enhancements.filter((e) => e.category === 'filter')
  const sizerCandidates = enhancements.filter((e) => e.category === 'position_sizer')

  function handleStrategyChange(id: string) {
    setSelectedStrategyId(id)
    const next = strategies.find((s) => s.id === id)
    setParamValues(next ? defaultsFor(next.params) : {})
  }

  function handleParamChange(name: string, value: string | number) {
    setParamValues((prev) => ({ ...prev, [name]: value }))
  }

  function addEnhancement(
    category: 'filter' | 'position_sizer',
    enhancementId: string
  ) {
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
        inst.instanceId === instanceId
          ? { ...inst, values: { ...inst.values, [name]: value } }
          : inst
      )
    if (category === 'filter') setFilters(updater)
    else setSizers(updater)
  }

  function resetParams() {
    if (strategy) setParamValues(defaultsFor(strategy.params))
    setFilters([])
    setSizers([])
    setRunError(null)
  }

  async function runStrategy() {
    if (!strategy) return
    setRunning(true)
    setRunError(null)
    try {
      const body = {
        params: paramValues,
        enhancements: {
          filters: filters.map((f) => ({ ...f.values, name: f.values.name ?? f.enhancementId })),
          position_sizers: sizers.map((s) => ({ name: s.enhancementId, sizer: s.values })),
        },
        // TODO: pull real values from a Portfolio panel; stubbed for now.
        portfolio: { initial_cash: 100000 },
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
      console.log('strategy result', result) // TODO: pass this up to a results panel
    } catch (e: any) {
      setRunError(e.message ?? 'Failed to run strategy')
    } finally {
      setRunning(false)
    }
  }

  return (
    <aside className="left-panel">
      <section className="section">
        <h3>Strategy</h3>
        <select
          className="full"
          value={selectedStrategyId}
          onChange={(e) => handleStrategyChange(e.target.value)}
        >
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
            <ParamField
              key={p.name}
              param={p}
              value={paramValues[p.name]}
              onChange={handleParamChange}
            />
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
                onChangeParam={(id, name, value) =>
                  updateEnhancementParam('filter', id, name, value)
                }
                onRemove={(id) => removeEnhancement('filter', id)}
              />
            )
          })}
        </div>
        <AddEnhancementRow
          candidates={filterCandidates}
          onAdd={(id) => addEnhancement('filter', id)}
        />
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
                onChangeParam={(id, name, value) =>
                  updateEnhancementParam('position_sizer', id, name, value)
                }
                onRemove={(id) => removeEnhancement('position_sizer', id)}
              />
            )
          })}
        </div>
        <AddEnhancementRow
          candidates={sizerCandidates}
          onAdd={(id) => addEnhancement('position_sizer', id)}
        />
      </section>

      {runError && <div className="run-error">{runError}</div>}

      <div className="panel-actions">
        <button className="btn ghost" onClick={resetParams} disabled={running}>
          Reset params
        </button>
        <button className="btn primary" onClick={runStrategy} disabled={running || !strategy}>
          {running ? 'Running…' : 'Run strategy'}
        </button>
      </div>
    </aside>
  )
}
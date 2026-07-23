// hooks/useAssetOptions.ts
import { useEffect, useState } from 'react'
import type { AssetClass } from '../types'

const cache: Partial<Record<AssetClass, string[]>> = {}

export function useAssetOptions(assetClass: AssetClass) {
  const [options, setOptions] = useState<string[]>(cache[assetClass] ?? [])
  const [loading, setLoading] = useState(!cache[assetClass])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (cache[assetClass]) {
      setOptions(cache[assetClass]!)
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    fetch(`/api/assets?type=${assetClass}`)
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load ${assetClass} list`)
        return res.json()
      })
      .then((data: { assets: string[] }) => {
        if (cancelled) return
        cache[assetClass] = data.assets
        setOptions(data.assets)
      })
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [assetClass])

  return { options, loading, error }
}
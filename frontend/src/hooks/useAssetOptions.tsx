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
      .then(async (res) => {
        const contentType = res.headers.get('content-type') ?? ''
        if (!res.ok || !contentType.includes('application/json')) {
          // Almost always means the request never reached the API (wrong path,
          // missing dev-server proxy, or backend not running) and got an HTML
          // fallback page instead.
          throw new Error(
            `Expected JSON from /api/assets but got ${res.status} (${contentType || 'unknown content-type'}). Check that the backend is running and the dev server proxy for /api is configured.`
          )
        }
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
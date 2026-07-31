// hooks/useAssetOptions.ts
import { useEffect, useRef, useState } from 'react'
import type { AssetClass } from '../types'

const cache: Partial<Record<AssetClass, string[]>> = {}
const fetching = new Set<string>()

export function clearAssetCache() {
  Object.keys(cache).forEach((key) => {
    delete cache[key as AssetClass]
  })
}

export function useAssetOptions(assetClass: AssetClass) {
  const [options, setOptions] = useState<string[]>(cache[assetClass] ?? [])
  const [loading, setLoading] = useState(!cache[assetClass])
  const [error, setError] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    // Always fetch fresh data to ensure we reflect any changes
    // and to provide visible feedback on strategy selection
    fetching.add(assetClass)
    abortControllerRef.current = new AbortController()
    setLoading(true)
    setError(null)

    fetch(`/api/assets?type=${assetClass}`, { signal: abortControllerRef.current.signal })
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
        cache[assetClass] = data.assets
        setOptions(data.assets)
        setError(null)
      })
      .catch((e) => {
        if (e.name !== 'AbortError') {
          setError(e.message)
        }
      })
      .finally(() => {
        fetching.delete(assetClass)
        setLoading(false)
      })

    return () => {
      abortControllerRef.current?.abort()
    }
  }, [assetClass])

  return { options, loading, error }
}
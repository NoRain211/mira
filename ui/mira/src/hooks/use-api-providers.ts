import { useCallback, useEffect, useState } from "react"

import { api } from "@/lib/api"
import type { ConnectedProvider, ProviderPreset } from "@/lib/api/settings"

// Provider presets plus connected API-key/local providers; refresh also notifies the page.
export function useApiProviders(onChanged?: () => void) {
  const [data, setData] = useState<{
    presets: ProviderPreset[]
    connected: ConnectedProvider[]
  }>({ presets: [], connected: [] })
  const load = useCallback(() => {
    api.getApiProviders().then(setData)
  }, [])
  useEffect(load, [load])
  const refresh = useCallback(() => {
    load()
    onChanged?.()
  }, [load, onChanged])
  return { ...data, refresh }
}

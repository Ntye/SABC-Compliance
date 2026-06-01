import { useCallback, useEffect, useState } from 'react'

export function useApi(apiFn, { deps = [], immediate = true } = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const execute = useCallback(async (...args) => {
    setLoading(true)
    setError(null)
    try {
      const result = await apiFn(...args)
      setData(result)
      return result
    } catch (err) {
      setError(err.message)
      // Do NOT re-throw here — the error is already in state for the UI to
      // display. Re-throwing creates an unhandled Promise rejection that shows
      // Vite's full-page error overlay in dev mode, making the page appear blank.
    } finally {
      setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    if (immediate) execute()
  }, [execute])

  return { data, loading, error, execute, refetch: execute }
}

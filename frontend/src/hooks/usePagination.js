import { useEffect, useMemo, useState } from 'react'

// Client-side pagination for a fully-loaded array. Default page size 20; the
// page clamps back into range when the data shrinks or the page size changes.
export function usePagination(items, { defaultPageSize = 20 } = {}) {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(defaultPageSize)

  const total = items?.length || 0
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  useEffect(() => {
    if (page > totalPages) setPage(totalPages)
  }, [page, totalPages])

  const pageItems = useMemo(() => {
    const from = (page - 1) * pageSize
    return (items || []).slice(from, from + pageSize)
  }, [items, page, pageSize])

  function changePageSize(n) {
    setPageSize(n)
    setPage(1)
  }

  return {
    page,
    setPage,
    pageSize,
    setPageSize: changePageSize,
    pageItems,
    total,
    totalPages,
    start: total === 0 ? 0 : (page - 1) * pageSize + 1,
    end: Math.min(page * pageSize, total),
  }
}

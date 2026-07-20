import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useT } from '../context/LangContext.jsx'

const DEFAULT_SIZES = [10, 20, 50, 100]

// Table footer: editable page size (default 20), prev/next range switching
// (1–20, 21–40, …) and the total element count. Designed so a usePagination
// return value can be spread straight in: `<Pagination {...pager} />`.
export default function Pagination({
  page, pageSize, total, totalPages, start, end,
  setPage, setPageSize, sizes = DEFAULT_SIZES,
}) {
  const t = useT()
  if (!total) return null

  const sizeOptions = sizes.includes(pageSize) ? sizes : [...sizes, pageSize].sort((a, b) => a - b)

  return (
    <div className="flex items-center justify-between gap-4 px-5 py-2.5 border-t border-gray-100 text-[12px] text-gray-500 flex-wrap">
      <div className="flex items-center gap-2">
        <span>{t('common.rowsPerPage')}</span>
        <select
          value={pageSize}
          onChange={(e) => setPageSize(Number(e.target.value))}
          className="border border-gray-200 rounded-lg px-2 py-1 text-[12px] text-gray-700 bg-white focus:outline-none focus:ring-1 focus:ring-brand/40"
        >
          {sizeOptions.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      <div className="flex items-center gap-3">
        <span className="tabular-nums">{t('common.showingRange', { start, end, total })}</span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setPage(page - 1)}
            disabled={page <= 1}
            aria-label={t('common.prevPage')}
            className="p-1 rounded-md border border-gray-200 text-gray-500 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <ChevronLeft size={14} />
          </button>
          <span className="tabular-nums px-1.5">{t('common.pageOf', { page, totalPages })}</span>
          <button
            onClick={() => setPage(page + 1)}
            disabled={page >= totalPages}
            aria-label={t('common.nextPage')}
            className="p-1 rounded-md border border-gray-200 text-gray-500 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}

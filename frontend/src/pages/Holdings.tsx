import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { fetchHoldings } from '../api/portfolio'
import Card from '../components/Card'
import StatusMessage from '../components/StatusMessage'
import AccountFilter from '../components/AccountFilter'
import type { Account, HoldingItem } from '../types'

const fmtGBP = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: 0 })
const fmtPrice = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', minimumFractionDigits: 2, maximumFractionDigits: 2 })
const fmtUnits = (n: number) => parseFloat(n.toPrecision(4)).toLocaleString('en-GB')

type SortCol = 'fund_short_name' | 'units_held' | 'price_gbp' | 'value_gbp' | 'cost_basis_gbp' | 'unrealised_gain_gbp' | 'unrealised_gain_pct' | 'percentage'
type SortDir = 'asc' | 'desc'

function SortIcon({ col, sortCol, sortDir }: { col: SortCol; sortCol: SortCol; sortDir: SortDir }) {
  if (col !== sortCol) return <span className="ml-1 text-gray-700">↕</span>
  return <span className="ml-1 text-indigo-400">{sortDir === 'asc' ? '↑' : '↓'}</span>
}

function SortableHeader({
  col, label, align = 'right', sortCol, sortDir, onSort, className = '',
}: {
  col: SortCol; label: string; align?: 'left' | 'right'
  sortCol: SortCol; sortDir: SortDir; onSort: (col: SortCol) => void
  className?: string
}) {
  return (
    <th
      className={`pb-3 text-${align} cursor-pointer select-none hover:text-gray-300 transition-colors whitespace-nowrap ${className}`}
      onClick={() => onSort(col)}
    >
      {label}<SortIcon col={col} sortCol={sortCol} sortDir={sortDir} />
    </th>
  )
}

export default function Holdings() {
  const [account, setAccount] = useState<Account | undefined>()
  const [sortCol, setSortCol] = useState<SortCol>('value_gbp')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const { data, loading, error } = useApi(() => fetchHoldings(account), [account])

  const totalValue = data?.reduce((s, h) => s + h.value_gbp, 0) ?? 0
  const totalGain = data?.reduce((s, h) => s + h.unrealised_gain_gbp, 0) ?? 0
  const totalCost = data?.reduce((s, h) => s + h.cost_basis_gbp, 0) ?? 0
  const totalGainPct = totalCost > 0 ? (totalGain / totalCost) * 100 : 0

  function handleSort(col: SortCol) {
    if (col === sortCol) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortCol(col)
      setSortDir('desc')
    }
  }

  const sorted = useMemo(() => {
    if (!data) return []
    const funds = data.filter(h => h.holding_type !== 'cash')
    const cash = data.filter(h => h.holding_type === 'cash')
    funds.sort((a, b) => {
      const av = a[sortCol]
      const bv = b[sortCol]
      if (av === null && bv === null) return 0
      if (av === null) return 1
      if (bv === null) return -1
      const cmp = typeof av === 'string'
        ? av.localeCompare(bv as string)
        : (av as number) - (bv as number)
      return sortDir === 'asc' ? cmp : -cmp
    })
    return [...funds, ...cash]
  }, [data, sortCol, sortDir])

  const sharedHeaderProps = { sortCol, sortDir, onSort: handleSort }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold text-white">Current Holdings</h1>
        <AccountFilter value={account} onChange={setAccount} />
      </div>

      {data && data.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Total Value', value: fmtGBP.format(totalValue), colour: 'text-indigo-400' },
            { label: 'Cost Basis', value: fmtGBP.format(totalCost), colour: 'text-gray-300' },
            { label: 'Unrealised Gain', value: fmtGBP.format(totalGain), colour: totalGain >= 0 ? 'text-emerald-400' : 'text-red-400' },
            { label: 'Return', value: `${totalGainPct.toFixed(1)}%`, colour: totalGainPct >= 0 ? 'text-emerald-400' : 'text-red-400' },
          ].map(({ label, value, colour }) => (
            <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
              <p className={`text-xl font-semibold ${colour}`}>{value}</p>
            </div>
          ))}
        </div>
      )}

      <Card>
        {loading || error || !data?.length ? (
          <StatusMessage loading={loading} error={error} empty={!data?.length} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs uppercase border-b border-gray-800">
                  <SortableHeader col="fund_short_name" label="Fund" align="left" {...sharedHeaderProps} />
                  <SortableHeader col="units_held" label="Units" className="hidden sm:table-cell" {...sharedHeaderProps} />
                  <SortableHeader col="price_gbp" label="Price" className="hidden sm:table-cell" {...sharedHeaderProps} />
                  <SortableHeader col="value_gbp" label="Value" {...sharedHeaderProps} />
                  <SortableHeader col="cost_basis_gbp" label="Cost Basis" className="hidden sm:table-cell" {...sharedHeaderProps} />
                  <SortableHeader col="unrealised_gain_gbp" label="Gain / Loss" {...sharedHeaderProps} />
                  <SortableHeader col="unrealised_gain_pct" label="Return" {...sharedHeaderProps} />
                  <SortableHeader col="percentage" label="Weight" className="hidden sm:table-cell" {...sharedHeaderProps} />
                  <th className="pb-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {sorted.map((h, i) => (
                  <HoldingRow key={h.fund_id ?? `cash-${i}`} h={h} />
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-gray-700 text-gray-300 font-semibold">
                  <td className="py-3">Total</td>
                  <td className="py-3 text-right tabular-nums hidden sm:table-cell"><span className="text-gray-700">—</span></td>
                  <td className="py-3 text-right tabular-nums hidden sm:table-cell"><span className="text-gray-700">—</span></td>
                  <td className="py-3 text-right tabular-nums text-gray-200">{fmtGBP.format(totalValue)}</td>
                  <td className="py-3 text-right tabular-nums text-gray-400 hidden sm:table-cell">{fmtGBP.format(totalCost)}</td>
                  <td className={`py-3 text-right tabular-nums ${totalGain >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {totalGain >= 0 ? '+' : ''}{fmtGBP.format(totalGain)}
                  </td>
                  <td className={`py-3 text-right tabular-nums ${totalGainPct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {totalGainPct >= 0 ? '+' : ''}{totalGainPct.toFixed(1)}%
                  </td>
                  <td className="py-3 text-right tabular-nums text-gray-500 hidden sm:table-cell">100.0%</td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

function HoldingRow({ h }: { h: HoldingItem }) {
  const isCash = h.holding_type === 'cash'
  return (
    <tr className="hover:bg-gray-800/40 transition-colors">
      <td className="py-3 text-gray-200 font-medium max-w-[200px] truncate" title={h.fund_name}>
        {isCash
          ? <span className="text-sky-400">{h.fund_short_name}</span>
          : h.fund_short_name}
      </td>
      <td className="py-3 text-right text-gray-400 tabular-nums hidden sm:table-cell">
        {h.units_held !== null ? fmtUnits(h.units_held) : <span className="text-gray-700">—</span>}
      </td>
      <td className="py-3 text-right text-gray-400 tabular-nums hidden sm:table-cell">
        {h.price_gbp !== null ? fmtPrice.format(h.price_gbp) : <span className="text-gray-700">—</span>}
      </td>
      <td className="py-3 text-right text-gray-200 tabular-nums font-medium">{fmtGBP.format(h.value_gbp)}</td>
      <td className="py-3 text-right text-gray-400 tabular-nums hidden sm:table-cell">{fmtGBP.format(h.cost_basis_gbp)}</td>
      <td className={`py-3 text-right tabular-nums font-medium ${h.unrealised_gain_gbp >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
        {isCash
          ? <span className="text-gray-700">—</span>
          : <>{h.unrealised_gain_gbp >= 0 ? '+' : ''}{fmtGBP.format(h.unrealised_gain_gbp)}</>}
      </td>
      <td className={`py-3 text-right tabular-nums ${h.unrealised_gain_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
        {isCash
          ? <span className="text-gray-700">—</span>
          : <>{h.unrealised_gain_pct >= 0 ? '+' : ''}{h.unrealised_gain_pct.toFixed(1)}%</>}
      </td>
      <td className="py-3 text-right text-gray-500 hidden sm:table-cell">{h.percentage.toFixed(1)}%</td>
      <td className="py-3 text-right">
        {!isCash && h.fund_id && (
          <Link to={`/funds/${h.fund_id}`} className="text-indigo-400 hover:text-indigo-300 text-xs">
            Chart →
          </Link>
        )}
      </td>
    </tr>
  )
}

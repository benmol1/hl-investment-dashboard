import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { fetchHoldings } from '../api/portfolio'
import Card from '../components/Card'
import StatusMessage from '../components/StatusMessage'
import AccountFilter from '../components/AccountFilter'
import type { Account, HoldingItem } from '../types'

const fmtGBP = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: 0 })
const fmtPrice = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', minimumFractionDigits: 2, maximumFractionDigits: 4 })
const fmtUnits = (n: number) => n.toLocaleString('en-GB', { maximumFractionDigits: 4 })

type SortCol = 'fund_short_name' | 'units_held' | 'price_gbp' | 'value_gbp' | 'cost_basis_gbp' | 'unrealised_gain_gbp' | 'unrealised_gain_pct' | 'percentage'
type SortDir = 'asc' | 'desc'

function SortIcon({ col, sortCol, sortDir }: { col: SortCol; sortCol: SortCol; sortDir: SortDir }) {
  if (col !== sortCol) return <span className="ml-1 text-gray-700">↕</span>
  return <span className="ml-1 text-indigo-400">{sortDir === 'asc' ? '↑' : '↓'}</span>
}

function SortableHeader({
  col, label, align = 'right', sortCol, sortDir, onSort,
}: {
  col: SortCol; label: string; align?: 'left' | 'right'
  sortCol: SortCol; sortDir: SortDir; onSort: (col: SortCol) => void
}) {
  return (
    <th
      className={`pb-3 text-${align} cursor-pointer select-none hover:text-gray-300 transition-colors whitespace-nowrap`}
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
    return [...data].sort((a, b) => {
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
  }, [data, sortCol, sortDir])

  const sharedHeaderProps = { sortCol, sortDir, onSort: handleSort }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
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
                  <SortableHeader col="units_held" label="Units" {...sharedHeaderProps} />
                  <SortableHeader col="price_gbp" label="Price" {...sharedHeaderProps} />
                  <SortableHeader col="value_gbp" label="Value" {...sharedHeaderProps} />
                  <SortableHeader col="cost_basis_gbp" label="Cost Basis" {...sharedHeaderProps} />
                  <SortableHeader col="unrealised_gain_gbp" label="Gain / Loss" {...sharedHeaderProps} />
                  <SortableHeader col="unrealised_gain_pct" label="Return" {...sharedHeaderProps} />
                  <SortableHeader col="percentage" label="Weight" {...sharedHeaderProps} />
                  <th className="pb-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {sorted.map((h, i) => (
                  <HoldingRow key={h.fund_id ?? `cash-${i}`} h={h} />
                ))}
              </tbody>
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
      <td className="py-3 text-right text-gray-400 tabular-nums">
        {h.units_held !== null ? fmtUnits(h.units_held) : <span className="text-gray-700">—</span>}
      </td>
      <td className="py-3 text-right text-gray-400 tabular-nums">
        {h.price_gbp !== null ? fmtPrice.format(h.price_gbp) : <span className="text-gray-700">—</span>}
      </td>
      <td className="py-3 text-right text-gray-200 tabular-nums font-medium">{fmtGBP.format(h.value_gbp)}</td>
      <td className="py-3 text-right text-gray-400 tabular-nums">{fmtGBP.format(h.cost_basis_gbp)}</td>
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
      <td className="py-3 text-right text-gray-500">{h.percentage.toFixed(1)}%</td>
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

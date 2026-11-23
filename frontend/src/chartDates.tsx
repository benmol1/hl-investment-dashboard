import { ReferenceLine } from 'recharts'

// Shared x-axis conventions for month-end charts: ticks at calendar quarter-ends ("Mar-26"),
// a faint vertical line at each quarter-end and a stronger one at each year-end.

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const monthOf = (d: string) => d.slice(5, 7)

export const fmtQuarterTick = (d: string) => `${MONTHS[parseInt(monthOf(d)) - 1]}-${d.slice(2, 4)}`

export const quarterTicks = (dates: string[]) =>
  dates.filter((d) => ['03', '06', '09', '12'].includes(monthOf(d)))

/** Returns an array, not a component: recharts only draws ReferenceLines that are direct children. */
export const quarterReferenceLines = (dates: string[]) => [
  ...dates
    .filter((d) => ['03', '06', '09'].includes(monthOf(d)))
    .map((d) => <ReferenceLine key={d} x={d} stroke="#1f2937" strokeWidth={1} strokeDasharray="3 3" />),
  ...dates
    .filter((d) => monthOf(d) === '12')
    .map((d) => <ReferenceLine key={d} x={d} stroke="#374151" strokeWidth={1} />),
]

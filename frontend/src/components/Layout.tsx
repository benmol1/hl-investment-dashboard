import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { fetchFreshness } from '../api/portfolio'

const navItems = [
  { to: '/', label: 'Overview', exact: true },
  { to: '/contributions', label: 'Contributions' },
  { to: '/funds', label: 'Fund Performance' },
  { to: '/benchmarks', label: 'Benchmarks' },
  { to: '/holdings', label: 'Current Holdings' },
  { to: '/transactions', label: 'Transactions' },
]

const fmtDate = (iso: string | null) => {
  if (!iso) return '—'
  const d = new Date(iso)
  const date = d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
  const time = d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  return `${date}, ${time}`
}

export default function Layout() {
  const [open, setOpen] = useState(() => window.innerWidth >= 768)
  const { data: freshness } = useApi(fetchFreshness, [])

  return (
    <div className="flex min-h-screen bg-gray-950">
      {/* Mobile backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-20 bg-black/60 md:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Sidebar — fixed overlay on mobile, normal flow on desktop */}
      {open && (
        <nav className="fixed inset-y-0 left-0 z-30 w-56 flex flex-col bg-gray-900 border-r border-gray-800 md:relative md:inset-auto md:z-auto md:shrink-0">
          <div className="px-5 py-5 border-b border-gray-800 flex items-center justify-between">
            <span className="text-sm font-semibold text-indigo-400 uppercase tracking-widest">HL Dashboard</span>
            <button
              onClick={() => setOpen(false)}
              className="text-gray-500 hover:text-gray-200 p-1 -mr-1 rounded"
              aria-label="Close sidebar"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                <path d="M3.293 3.293a1 1 0 011.414 0L8 6.586l3.293-3.293a1 1 0 111.414 1.414L9.414 8l3.293 3.293a1 1 0 01-1.414 1.414L8 9.414l-3.293 3.293a1 1 0 01-1.414-1.414L6.586 8 3.293 4.707a1 1 0 010-1.414z"/>
              </svg>
            </button>
          </div>
          <ul className="flex-1 py-4 space-y-0.5 px-2">
            {navItems.map(({ to, label, exact }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={exact}
                  onClick={() => { if (window.innerWidth < 768) setOpen(false) }}
                  className={({ isActive }) =>
                    `block px-3 py-2 rounded-md text-sm transition-colors ${
                      isActive
                        ? 'bg-indigo-600 text-white font-medium'
                        : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800'
                    }`
                  }
                >
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
          <div className="px-4 py-3 border-t border-gray-800 text-xs text-gray-600">
            Hargreaves Lansdown
          </div>
        </nav>
      )}

      {/* Main content */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Top bar with hamburger */}
        <header className="sticky top-0 z-10 flex items-center px-4 h-12 bg-gray-900 border-b border-gray-800 shrink-0">
          <button
            onClick={() => setOpen(o => !o)}
            className="text-gray-400 hover:text-gray-100 p-1 rounded mr-3"
            aria-label="Toggle sidebar"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
              <rect y="3" width="20" height="2" rx="1"/>
              <rect y="9" width="20" height="2" rx="1"/>
              <rect y="15" width="20" height="2" rx="1"/>
            </svg>
          </button>
          <span className="text-sm font-semibold text-indigo-400 uppercase tracking-widest">HL Dashboard</span>
          {freshness && (
            <div className="ml-auto flex items-center gap-4 text-xs text-gray-500">
              <span>Prices: <span className="text-gray-400">{fmtDate(freshness.price_date)}</span></span>
              <span>Transactions: <span className="text-gray-400">{fmtDate(freshness.transaction_date)}</span></span>
            </div>
          )}
        </header>

        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

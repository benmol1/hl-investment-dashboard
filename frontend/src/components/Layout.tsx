import { NavLink, Outlet } from 'react-router-dom'

const navItems = [
  { to: '/', label: 'Overview', exact: true },
  { to: '/contributions', label: 'Contributions' },
  { to: '/funds', label: 'Fund Performance' },
  { to: '/benchmarks', label: 'Benchmarks' },
  { to: '/holdings', label: 'Holdings' },
  { to: '/transactions', label: 'Transactions' },
]

export default function Layout() {
  return (
    <div className="flex min-h-screen">
      <nav className="w-56 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="px-5 py-5 border-b border-gray-800">
          <span className="text-sm font-semibold text-indigo-400 uppercase tracking-widest">HL Dashboard</span>
        </div>
        <ul className="flex-1 py-4 space-y-0.5 px-2">
          {navItems.map(({ to, label, exact }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={exact}
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
      <main className="flex-1 min-w-0 p-6 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
